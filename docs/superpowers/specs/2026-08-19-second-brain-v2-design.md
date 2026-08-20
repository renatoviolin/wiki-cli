# Second Brain v2 — Isolated Package, Deterministic Compiler Split

## Context

`docs/superpowers/specs/2026-08-13-second-brain-design.md` designed a `/second-brain` skill following Andrej Karpathy's April 2026 "LLM Wiki" gist — raw sources compiled into a structured, cross-referenced Markdown wiki with typed relations, maintained via `ingest`/`lint`/`query` operations. That design wired the new work directly into `code_review_cli` (new `runner.py` primitive, new `prompts.py` schema, `cli.py` restructured into subparsers) and put every step — including purely mechanical bookkeeping — inside the headless Claude Code session.

Two things changed since then, both from research done for this revision:

1. **Community "v2" additions to the base pattern** (confidence scoring, supersession chains, forgetting curves, lifecycle hooks) turned out to mostly already be present in the 2026-08-13 design (`status: stale`/`supersedes`, provenance-required). The one addition worth actually adding is per-page **confidence scoring** — called "the single highest-value v2 idea" by practitioners who've built on the pattern. Community proposals for hybrid vector search and tiered memory scoring are explicitly *not* adopted — irrelevant at wiki scale (50–100K tokens), where "grep plus read finds the note faster."
2. **A sharper critique**: letting an LLM agent do purely mechanical wiki maintenance (parsing frontmatter, detecting orphans/broken links, tracking state) is non-deterministic run-to-run (one practitioner reproduced different link structures from identical input, twice) and burns tokens on organizational work that's actually deterministic. Their fix: a plain-Python compiler for the mechanical 90%, reserving the LLM for the ~10% that's real synthesis (authoring prose, judging contradictions, assessing confidence).

Separately, this project's own next priority shifted: build this as a **fully isolated, independent package** — its own module tree, own CLI entry point, zero imports to/from `code_review_cli` — so the two tools can be worked on without risk of breaking each other, sharing nothing but this git repository. This design supersedes the 2026-08-13 spec's architecture section; its storage format and schema largely carry forward unchanged.

## Goals

- A skill/CLI that builds and incrementally maintains a per-repo knowledge base (architecture, conventions, gotchas, decisions) with explicit typed relations between entries — not a flat list of facts.
- Fully isolated from `code_review_cli`: a new top-level package, own entry point, own tests, no shared modules.
- Deterministic-first: every mechanical operation (cloning, diffing, frontmatter parsing, orphan/broken-link/staleness detection, state/index/log bookkeeping, committing) is plain Python with no LLM call and no run-to-run variance. The LLM is dispatched only for genuine semantic work: authoring/updating wiki pages, confidence-tagging claims, and judging contradictions between new and existing content.
- `lint` requires zero LLM calls, ever — pure Python, instant, free to run as often as wanted.
- `ingest` short-circuits to zero LLM calls when nothing changed since the last run.
- One small, explicitly-scoped touch to `code_review_cli` closes the loop: the review dispatch instructions read `.second-brain/wiki/index.md` (if present) for extra context, with no code-level coupling between the two packages.

## Non-goals (deferred)

- A semantic query tool / MCP server / vector search over the knowledge base — plain-file consumption via `grep`+`Read` is sufficient at this scale, per the v2 research.
- Scheduling or automatic triggering (cron, CI, webhooks). `ingest`/`lint` are explicit, on-demand CLI invocations only in this version. If periodic runs are wanted later, that's "run this CLI command on a schedule" — layered on top externally (e.g. this session's own `/schedule` or `/loop` skills, or a plain cron entry), not something this package's design needs to account for.
- `query` (the original spec's stretch goal) — still out of scope.
- Guarding against concurrent `ingest`/`lint` runs on the same repo — single-operator, on-demand tool, one invocation at a time.
- Any change to `code_review_cli`'s own architecture beyond the one prompt-text addition in Goals above.

## Design

### Package layout

New top-level package, sibling to the existing one:

```
src/second_brain/
├── __init__.py
├── validation.py   # validate_provider/validate_repo — same rules as code_review_cli's, duplicated (not imported)
├── git_ops.py       # ALL deterministic git/gh/aws shell-outs: clone, pull, log, diff, commit
├── wiki.py          # ALL deterministic wiki-file operations: frontmatter parse/write, index/log/state maintenance,
│                    #   orphan/broken-link/staleness detection (this module IS `lint`, in full)
├── prompts.py       # pure string templating for the one LLM dispatch point (ingest's Phase B) — mirrors
│                    #   code_review_cli/prompts.py's pattern but with no checkout instructions (repo's already cloned)
├── runner.py        # the only module that touches the Claude Agent SDK — one query() call, ingest's Phase B only
├── result.py         # IngestResult dataclass — mirrors ReviewResult's shape/conventions
└── cli.py           # argparse entrypoint: `ingest` and `lint` subcommands
```

No file in this tree imports anything from `code_review_cli`, and no file in `code_review_cli` imports anything from `second_brain`. The only thing they share is this git repository and (eventually) the prompt-text convention described in "Closing the loop" below.

### Storage: `.second-brain/` at the target repo's root, git-tracked (unchanged from 2026-08-13 spec)

```
.second-brain/
├── SCHEMA.md              # relation vocabulary + operating contract
├── raw/
│   └── pr-<n>-<date>.md    # immutable, timestamped snapshot of a PR's description/comments, fetched deterministically
└── wiki/
    ├── index.md            # master catalog — regenerated deterministically from every page's frontmatter + first body line
    ├── log.md              # append-only ops log (ingest/lint runs), grep-able
    ├── state.json           # last_processed_commit, last_updated_at — drives incremental ingest
    ├── modules/<name>.md    # entity pages: one per significant module/package
    ├── concepts/<name>.md   # cross-cutting synthesis: patterns, flows, conventions
    └── decisions/<slug>.md  # decisions/gotchas with provenance
```

Frontmatter (one field added versus the 2026-08-13 spec):
```yaml
---
type: module | concept | decision
confidence: stated | high | low   # NEW — is this a direct quote, a high-confidence inference, or a weaker synthesis?
depends_on: [[other-page]]
implements: [[other-page]]
supersedes: [[older-page]]
contradicts: [[conflicting-page]]
about: [[subject-page]]
provenance: [commit sha / file:line / raw/pr-12.md]   # required, non-empty, at least one non-wiki path
last_verified_commit: <sha>
status: active | stale | needs-review | superseded
---
```
`confidence` is authored by the LLM in Phase B (it's a judgment call — genuine semantic work). Everything else about the frontmatter contract (provenance-required, `stale`+`supersedes` instead of silent overwrite, `status` lifecycle) carries forward from the 2026-08-13 design unchanged.

### `ingest` — three-phase pipeline

**Phase A — deterministic (`git_ops.py` + `wiki.py`, zero LLM calls):**
1. Create a temp workspace (`tempfile.mkdtemp`, same convention as `code_review_cli.runner`).
2. Clone/pull the target repo directly: `gh repo clone` (github) or `git clone codecommit://...` (codecommit), then subsequent runs `git -C workspace pull`. **This is the one deliberate divergence from `code_review_cli`'s "wrapper never touches git" rule** — `second_brain`'s own process needs `gh`/AWS credentials available in its environment, not just inside a headless container. Called out explicitly as a requirement, same way `code_review_cli`'s README documents its own credential requirements.
3. Read `wiki/state.json` (missing → first-run bootstrap, treat as `--full`). If `last_processed_commit` isn't reachable from `HEAD` (rebase/force-push), fall back to `--full` automatically, noted in `log.md`.
4. `git log <last_processed_commit>..HEAD --name-only` (or every tracked file, on `--full`) → the changed-file/commit list. Purely mechanical.
5. Fetch PR descriptions/comments merged since the last run via `gh pr list`/`aws codecommit list-pull-requests` equivalents, write each as an immutable `raw/pr-<n>-<ingest-date>.md` snapshot (re-ingesting a still-open PR adds a new snapshot, never overwrites).
6. **Short-circuit:** if step 4 found no new commits and step 5 found no new PR activity, and `--full` wasn't passed, stop here. Report success with `pages_changed: []` and never invoke Claude. Zero cost for a no-op run.

**Phase B — one headless Claude Code call (only reached if Phase A found work):**
- `cwd` = the already-cloned workspace. No checkout instructions in the prompt at all — the repo is already there, which is a real simplification versus the 2026-08-13 design's prompt (which had to teach Claude how to clone).
- The prompt hands Claude: the exact changed-file/commit list from Phase A, the raw snapshot paths just written, and instructions to read `SCHEMA.md` plus any existing pages relevant to what changed, then write/update `modules/*.md`/`concepts/*.md`/`decisions/*.md` pages — including the new `confidence` field, marking any fact a change supersedes as `status: stale` + `supersedes` (never deleting), and checking new content against existing pages for direct contradictions (`contradicts` — this relation's only writer). Also carries the anti-hallucination instruction the v2 research flagged as commonly missing: re-read `index.md` and linked pages before claiming a topic isn't covered yet, to avoid spurious duplicate pages.
- Claude replies with structured JSON: `{success: bool, pages_changed: [string], summary: string, failure_reason: string}`. It does **not** touch `state.json`, `index.md`, or `log.md` — those are Phase C's job. This is the change that most directly answers the non-determinism finding: the files most prone to agent-introduced drift are never agent-written.

**Phase C — deterministic (`wiki.py`, zero LLM calls):**
1. Regenerate `index.md`'s catalog by parsing every page's frontmatter plus its first non-empty body line as the one-line summary — mechanical extraction, not synthesis.
2. Update `state.json` (`last_processed_commit` = new HEAD, `last_updated_at`).
3. Append one entry to `log.md` (commit range, files touched, `pages_changed` count from Phase B's reply).
4. `git add .second-brain/ && git commit` locally — not pushed; the human running the CLI reviews the diff before pushing, same as the 2026-08-13 design's rule, just deterministically executed now instead of trusted to the agent's memory.

### `lint` — fully deterministic, zero LLM calls

1. Clone/pull the target repo (same `git_ops.py` call as Phase A.2).
2. Parse every `wiki/**/*.md`'s frontmatter (`wiki.py`).
3. Checks, all pure Python: orphaned pages (nothing links in or out), broken cross-references (a `[[link]]` to a page that doesn't exist), stale claims (`last_verified_commit` more than a configurable commit-distance behind current `HEAD`), unresolved `contradicts` links, and the provenance rule (non-empty, and not *only* other wiki pages — this checks the field's structural shape, not that the cited fact is actually true; same known limitation the 2026-08-13 design already accepted).
4. Writes findings to `log.md`, flips affected pages' `status: needs-review` directly via frontmatter edit.
5. Reports a summary and exits 0 (clean) or 1 (findings) — no Claude Code invocation anywhere in this command, so it's free and instant to run as often as wanted.

### Closing the loop with the review flow (the one touch to `code_review_cli`)

A small addition to `src/code_review_cli/prompts.py`'s existing per-level dispatch blocks (`_STANDARD_DISPATCH`/`_LIGHT_DISPATCH`/`_HARD_DISPATCH`): before dispatching the reviewer subagent(s), instruct the orchestrating session to check whether `.second-brain/wiki/index.md` exists in the checked-out repo, and if so, read it (and pages it links to) and pass a summary as extra context in the subagent's task description. Prompt-text only — no new Python logic, no import of `second_brain`, no change to `_RESULT_SCHEMA` or any other file. `code_review_cli` doesn't know `second_brain` exists as a package; it just conditionally reads a folder if present. This is the only line item from this spec that touches `code_review_cli`.

## Testing

- `second_brain`'s deterministic modules (`git_ops.py`, `wiki.py`) get pytest unit tests against real files on `tmp_path` — fixture wiki directories with known-good and known-bad frontmatter, real `git` operations against a throwaway local repo fixture (no SDK mocking needed, since none of this touches Claude). This is the majority of the test surface, and it's exactly the kind of deterministic, fast, reliable testing the compiler-split makes possible that the original all-LLM design couldn't have had.
- `runner.py`'s one `query()` call (Phase B only) reuses `code_review_cli.runner`'s duck-typed-fake convention (`types.SimpleNamespace` fakes shaped like SDK messages, no import of real SDK classes) — same reasoning: an SDK version bump only touches this one file.
- `cli.py` gets `test_cli.py`-style argument-parsing and subcommand-wiring tests, following `code_review_cli`'s existing conventions for consistency across the two packages (same testing *style*, zero shared *code*).
- `code_review_cli`: one new assertion in `test_prompts.py` per level, confirming the dispatch instructions mention conditionally reading `.second-brain/wiki/index.md`.

## Critical files

- New: `src/second_brain/{validation,git_ops,wiki,prompts,runner,result,cli}.py`.
- New: `tests/test_second_brain_{validation,git_ops,wiki,prompts,runner,cli}.py` — flat, in the existing `tests/` directory, prefixed to disambiguate from `code_review_cli`'s same-named test files (`tests/test_validation.py` stays `code_review_cli`'s; `second_brain`'s equivalent is `tests/test_second_brain_validation.py`). Keeps one `pytest tests/ -v` running both packages' suites, matching this repo's existing single flat `tests/` convention — no new subdirectory.
- Modify: `pyproject.toml` — `second_brain` is declared as a second package under the same src-layout (`src/second_brain/`), discovered alongside `code_review_cli`; one `pip install -e .` installs both. Not a second distributable package with its own `pyproject.toml` — isolation here means independent module trees and zero cross-imports, not independent packaging/versioning.
- Modify: `src/code_review_cli/prompts.py` — the one closing-the-loop addition described above, plus its corresponding `tests/test_prompts.py` assertions.
- Reference only, not modified: `docs/superpowers/specs/2026-08-13-second-brain-design.md` — this spec supersedes its architecture section; its storage/schema section is still the reference for *why* the frontmatter contract looks the way it does.
