# Second Brain v2 — Isolated Package, Deterministic Compiler Split

## Context

`docs/superpowers/specs/2026-08-13-second-brain-design.md` designed a `/second-brain` skill following Andrej Karpathy's April 2026 "LLM Wiki" gist — raw sources compiled into a structured, cross-referenced Markdown wiki with typed relations, maintained via `ingest`/`lint`/`query` operations. That design wired the new work directly into `code_review_cli` (new `runner.py` primitive, new `prompts.py` schema, `cli.py` restructured into subparsers) and put every step — including purely mechanical bookkeeping — inside the headless Claude Code session.

Two things changed since then, both from research done for this revision:

1. **Community "v2" additions to the base pattern** (confidence scoring, supersession chains, forgetting curves, lifecycle hooks) turned out to mostly already be present in the 2026-08-13 design (`status: stale`/`supersedes`, provenance-required). The one addition worth actually adding is per-page **confidence scoring** — called "the single highest-value v2 idea" by practitioners who've built on the pattern. Community proposals for hybrid vector search and tiered memory scoring are explicitly *not* adopted — irrelevant at wiki scale (50–100K tokens), where "grep plus read finds the note faster."
2. **A sharper critique**: letting an LLM agent do purely mechanical wiki maintenance (parsing frontmatter, detecting orphans/broken links, tracking state) is non-deterministic run-to-run (one practitioner reproduced different link structures from identical input, twice) and burns tokens on organizational work that's actually deterministic. Their fix: a plain-Python compiler for the mechanical 90%, reserving the LLM for the ~10% that's real synthesis (authoring prose, judging contradictions, assessing confidence).

Separately, this project's own next priority shifted: build this as a **fully isolated, independent package** — its own module tree, own CLI entry point, zero imports to/from `code_review_cli` — so the two tools can be worked on without risk of breaking each other, sharing nothing but this git repository. This design supersedes the 2026-08-13 spec's architecture section; its storage format and schema largely carry forward unchanged.

This revision also incorporates findings from a four-lens subagent review of the first draft of this spec (architecture/feasibility, security/ops, consistency-vs-original, clarity/testability) — the fixes below (persistent workspace, deleted-module staleness, exact schemas/flags, restored E2E testing, honest CodeCommit description) came directly out of that review, along with three decisions the reviews flagged as requiring a human call rather than an implementer's default (credential scope, secrets/PII handling, audit logging — see "Requirements and accepted risks" below).

## Goals

- A skill/CLI that builds and incrementally maintains a per-repo knowledge base (architecture, conventions, gotchas, decisions) with explicit typed relations between entries — not a flat list of facts.
- Fully isolated from `code_review_cli`: a new top-level package, own entry point, own tests, no shared modules.
- Deterministic-first: every mechanical operation (cloning, diffing, frontmatter parsing, orphan/broken-link/staleness detection, deleted-module detection, state/index/log bookkeeping, committing) is plain Python with no LLM call and no run-to-run variance. The LLM is dispatched only for genuine semantic work: authoring/updating wiki pages, confidence-tagging claims, and judging contradictions between new and existing content.
- `lint` requires zero LLM calls, ever — pure Python, instant, free to run as often as wanted.
- `ingest` short-circuits to zero LLM calls when nothing changed since the last run.
- One small, explicitly-scoped touch to `code_review_cli` closes the loop: the review dispatch instructions read `.second-brain/wiki/index.md` (if present) for extra context, with no code-level coupling between the two packages.

## Non-goals (deferred)

- A semantic query tool / MCP server / vector search over the knowledge base — plain-file consumption via `grep`+`Read` is sufficient at this scale, per the v2 research.
- Scheduling or automatic triggering (cron, CI, webhooks). `ingest`/`lint` are explicit, on-demand CLI invocations only in this version. If periodic runs are wanted later, that's "run this CLI command on a schedule" — layered on top externally (e.g. this session's own `/schedule` or `/loop` skills, or a plain cron entry), not something this package's design needs to account for.
- `query` (the original spec's stretch goal) — still out of scope.
- Guarding against concurrent `ingest`/`lint` runs on the same repo — single-operator, on-demand tool, one invocation at a time.
- Any change to `code_review_cli`'s own architecture beyond the one prompt-text addition in Goals above.
- An automated secrets/PII scan on wiki content before commit — explicitly decided against for this version; see "Requirements and accepted risks" below for why this is a deliberate, flagged risk rather than an oversight.
- A dedicated, scoped credential/service-account for `second_brain` — explicitly decided against for this version; it reuses whatever `gh`/AWS credentials are already configured in the operator's environment. See "Requirements and accepted risks" below.
- A `SKILL.md` / `/second-brain` slash-command construct. The 2026-08-13 design made this a first-class global skill; v2 doesn't need it, because Phase B (the only LLM-dispatched step) is now a single, narrow, directly-built prompt — the same pattern `code_review_cli` itself already uses for its own review dispatch, which also has no reusable skill wrapping it. `prompts.py` builds that prompt directly; there is no slash command to install.

## Design

### Package layout

New top-level package, sibling to the existing one:

```
src/second_brain/
├── __init__.py
├── validation.py   # validate_provider/validate_repo — same rules as code_review_cli's, duplicated (not imported)
├── git_ops.py      # ALL git/gh/aws shell-outs: clone, pull, log, diff, commit — and the ONLY module that runs them.
│                   #   Every command it runs is appended to .second-brain/audit.log (command, args with secrets
│                   #   redacted, exit code, timestamp) before execution and its result after — see "Requirements
│                   #   and accepted risks" below for why this exists.
├── wiki.py         # ALL deterministic wiki-CONTENT operations: frontmatter parse/write, index/log/state
│                   #   maintenance, orphan/broken-link/staleness/deleted-module detection (this module IS
│                   #   `lint`, in full). Never shells out to git — that's git_ops.py's job exclusively.
├── prompts.py      # pure string templating for the one LLM dispatch point (ingest's Phase B) — mirrors
│                   #   code_review_cli/prompts.py's pattern but with no checkout instructions (repo's already cloned)
├── runner.py       # the only module that touches the Claude Agent SDK — one query() call, ingest's Phase B only
├── result.py       # IngestResult dataclass — see exact shape below
└── cli.py          # argparse entrypoint: `ingest` and `lint` subcommands, console-script name `second-brain`
```

No file in this tree imports anything from `code_review_cli`, and no file in `code_review_cli` imports anything from `second_brain`. The only thing they share is this git repository and (eventually) the prompt-text convention described in "Closing the loop" below.

### Storage: `.second-brain/` at the target repo's root, git-tracked

```
.second-brain/
├── SCHEMA.md              # relation vocabulary + operating contract; initial content authored at implementation
│                          #   time (bootstrapped by the first `ingest` run), not specified in this design doc —
│                          #   same treatment as the 2026-08-13 design gave it.
├── audit.log              # NEW — append-only, one line per git_ops.py command: timestamp, command (secrets
│                          #   redacted), exit code. Committed alongside the rest of `.second-brain/`, so the
│                          #   audit trail travels with the wiki and is visible in the same diff a human reviews
│                          #   before pushing.
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

Frontmatter (two fields added versus the 2026-08-13 spec):
```yaml
---
type: module | concept | decision
confidence: stated | high | low   # NEW — is this a direct quote, a high-confidence inference, or a weaker synthesis?
depends_on: [[other-page]]
implements: [[other-page]]
supersedes: [[older-page]]
contradicts: [[conflicting-page]]
about: [[subject-page]]
subject_path: <path/to/file/or/directory>   # NEW, modules/concepts pages only — the real repo path this page
                                             #   documents, used by Phase A's deleted-module check to mechanically
                                             #   tell whether the thing this page is about still exists
provenance: [commit sha / file:line / raw/pr-12.md]   # required, non-empty, at least one non-wiki path
last_verified_commit: <sha>
status: active | stale | needs-review | superseded
---
```
`confidence` is authored by the LLM in Phase B (it's a judgment call — genuine semantic work). `about` keeps its original meaning unchanged — a typed wiki-to-wiki relation. `subject_path` is new and separate: a plain repo-relative path, present only on `modules/*.md`/`concepts/*.md` pages, existing specifically so Phase A can mechanically check path existence without needing to resolve a wiki link first. Everything else about the frontmatter contract (provenance-required, `stale`+`supersedes` instead of silent overwrite, `status` lifecycle) carries forward from the 2026-08-13 design unchanged.

### Workspace lifecycle (persistent, not ephemeral — diverges from `code_review_cli.runner`'s per-run temp dir)

`code_review_cli` creates a fresh `tempfile.mkdtemp` workspace per run and deletes it on success, because every review is a one-shot PR checkout. `second_brain` needs the opposite: incremental `ingest` only works if there's a prior clone to `git pull` into, and `ingest`'s local commit must survive after the process exits so a human can review and push it. So:

- Workspace path is deterministic per target repo: `<workspace-root>/<provider>__<repo-with-slashes-as-dashes>/` (e.g. `~/.cache/second-brain/workspaces/github__renatoviolin-purabackend/`). `<workspace-root>` defaults to `~/.cache/second-brain/workspaces` and is overridable via `--workspace-dir` (useful in CI where `$HOME` may not persist between runs).
- First `ingest`/`lint` for a repo: `git_ops.py` clones into that path. Every subsequent run: `git_ops.py` runs `git pull` in place instead of re-cloning.
- The workspace is **never deleted** by this tool. `ingest`'s final report (see Phase C below) prints the workspace path so the operator knows exactly where to go review/push the local commit.
- This is a real divergence from `code_review_cli`'s convention and is documented as one, not silently different.

### `ingest` — three-phase pipeline

**Phase A — deterministic (`git_ops.py` + `wiki.py`, zero LLM calls):**
1. Resolve the persistent workspace path (above); clone if absent, `git pull` if present.
2. Read `wiki/state.json` (missing → first-run bootstrap, treat as `--full`). If `last_processed_commit` isn't reachable from `HEAD` (rebase/force-push), fall back to `--full` automatically, noted in `log.md`.
3. `git log <last_processed_commit>..HEAD --name-status` (or every tracked file, on `--full`) → the changed-file/commit list, including which files were deleted. Purely mechanical.
4. **Deleted-module check (`wiki.py`):** for every existing `wiki/modules/*.md`/`concepts/*.md` page whose frontmatter `subject_path` no longer exists in the current tree (per step 3's deletions, or a direct existence check on `--full`), mark it `status: stale` immediately — this is mechanical (a path either exists or it doesn't), so it happens here, not deferred to Phase B or `lint`.
5. Fetch PR activity since the last run:
   - **GitHub:** `gh pr list --search "is:merged merged:>=<last-run-date>"` — a single, real, scriptable call.
   - **CodeCommit:** no equivalent single call exists. `aws codecommit list-pull-requests --pull-request-status CLOSED` returns all closed PRs with no merge-date filter, so `git_ops.py` must then call `aws codecommit get-pull-request` per result to read its merge timestamp (filtering client-side against `state.json`'s `last_updated_at`) and `aws codecommit get-comments-for-pull-request` for its comments. More calls, and slower than the GitHub path — documented honestly here rather than described as an "equivalent."
   - Each fetched PR is written as an immutable `raw/pr-<n>-<ingest-date>.md` snapshot (re-ingesting a still-open PR adds a new snapshot, never overwrites).
6. **Short-circuit:** if step 3 found no new commits, step 4 found no newly-stale pages, and step 5 found no new PR activity, and `--full` wasn't passed, stop here. Report success with `pages_changed: []`, print the workspace path, and never invoke Claude. Zero cost for a no-op run.

**Phase B — one headless Claude Code call (only reached if Phase A found work):**
- `cwd` = the already-cloned, already-pulled workspace. No checkout instructions in the prompt at all — the repo is already there, which is a real simplification versus the 2026-08-13 design's prompt (which had to teach Claude how to clone).
- The prompt hands Claude: the exact changed-file/commit list from Phase A, the raw snapshot paths just written, and instructions to read `SCHEMA.md` plus any existing pages relevant to what changed, then write/update `modules/*.md`/`concepts/*.md`/`decisions/*.md` pages — including the new `confidence` field, marking any fact a change supersedes as `status: stale` + `supersedes` (never deleting), and checking new content against existing pages for direct contradictions (`contradicts` — this relation's only writer). Also carries the anti-hallucination instruction the v2 research flagged as commonly missing: re-read `index.md` and linked pages before claiming a topic isn't covered yet, to avoid spurious duplicate pages.
- The session is invoked with `output_format={"type": "json_schema", "schema": _INGEST_SCHEMA}` (`ClaudeAgentOptions`, same mechanism `code_review_cli.runner` uses for `_RESULT_SCHEMA`) — this is the exact fix `CLAUDE.md` documents as a real prior production bug (`is_error=False` does not mean the task succeeded; only the forced structured output does), reaffirmed here rather than left implicit.
- `_INGEST_SCHEMA` (in `prompts.py`, `additionalProperties: false`, every field required):
  ```python
  _INGEST_SCHEMA = {
      "type": "object",
      "properties": {
          "success": {"type": "boolean"},
          "pages_changed": {"type": "array", "items": {"type": "string"}},
          "summary": {"type": "string"},
          "failure_reason": {"type": "string"},
      },
      "required": ["success", "pages_changed", "summary", "failure_reason"],
      "additionalProperties": False,
  }
  ```
- Claude replies with that shape. It does **not** touch `state.json`, `index.md`, or `log.md` — those are Phase C's job. This is the change that most directly answers the non-determinism finding: the files most prone to agent-introduced drift are never agent-written.

**Phase C — deterministic (`wiki.py` for content, `git_ops.py` for the commit — zero LLM calls):**
1. `wiki.py` regenerates `index.md`'s catalog by parsing every page's frontmatter plus its first non-empty body line as the one-line summary — mechanical extraction, not synthesis.
2. `wiki.py` updates `state.json` (`last_processed_commit` = new HEAD, `last_updated_at`).
3. `wiki.py` appends one entry to `log.md` (commit range, files touched, `pages_changed` count from Phase B's reply, any pages marked stale by the Phase A.4 deleted-module check).
4. `git_ops.py` runs `git add .second-brain/ && git commit` locally — not pushed; the human reviews the diff (in the persistent workspace, whose path was printed) before pushing. This is a deliberate, accepted risk — see "Requirements and accepted risks" below.

`IngestResult` (in `result.py`, mirrors `ReviewResult`'s conventions):
```python
@dataclass
class IngestResult:
    success: bool
    pages_changed: list[str] = field(default_factory=list)
    summary: str = ""
    error_message: str = ""
    workspace_path: str = ""
    cost_usd: float | None = None
    duration_ms: int | None = None
    num_turns: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None

    def exit_code(self) -> int:
        return 0 if self.success else 1
```
Cost/token fields stay `None` on a short-circuited (Phase-A-only) run, since no `query()` call happened — same convention `ReviewResult` already follows when a field genuinely doesn't apply.

### `lint` — fully deterministic, zero LLM calls

1. Resolve/clone/pull the persistent workspace (same `git_ops.py` call Phase A.1 uses).
2. Parse every `wiki/**/*.md`'s frontmatter (`wiki.py`).
3. Checks, all pure Python:
   - Orphaned pages (nothing links in or out).
   - Broken cross-references (a `[[link]]` to a page that doesn't exist) — the scan explicitly excludes fenced code blocks (` ``` `) so a literal `[[example]]` used as documentation inside a code sample doesn't false-positive.
   - Stale claims: `last_verified_commit` more than `--stale-after` commits behind current `HEAD` (CLI flag on `lint`, default `500`).
   - Unresolved `contradicts` links.
   - Provenance rule: non-empty, and not *only* other wiki pages — this checks the field's structural shape (does it look like a commit SHA / `file:line` / `raw/*.md` path), not that the cited fact is actually true; same known limitation the 2026-08-13 design already accepted.
4. Writes findings to `log.md`, flips affected pages' `status: needs-review` directly via frontmatter edit.
5. Reports a summary and exits 0 (clean) or 1 (findings) — no Claude Code invocation anywhere in this command, so it's free and instant to run as often as wanted.

### `cli.py` — flags and exit codes

Mirrors `code_review_cli`'s conventions for consistency across the two packages:

```bash
second-brain ingest --repo <owner/repo> --provider github|codecommit [--full] [--workspace-dir <path>] [--verbose]
second-brain lint --repo <owner/repo> --provider github|codecommit [--stale-after <N>] [--workspace-dir <path>] [--verbose]
```

- Exit `0`: success (for `ingest`, `IngestResult.success`; for `lint`, no findings).
- Exit `1`: `ingest` failed to complete, or `lint` found issues (matches `code_review_cli`'s "1 for a failed run" convention).
- Exit `2`: input validation failure (bad `--repo`/`--provider`/`--stale-after`) — validated before any git/gh/aws call, same fail-closed pattern `code_review_cli.validation` uses.
- Console-script entry point name: `second-brain` (declared in `pyproject.toml`'s `[project.scripts]`).

### Closing the loop with the review flow (the one touch to `code_review_cli`)

A small addition to `src/code_review_cli/prompts.py`'s existing per-level dispatch blocks (`_STANDARD_DISPATCH`/`_LIGHT_DISPATCH`/`_HARD_DISPATCH`): before dispatching the reviewer subagent(s), instruct the orchestrating session to check whether `.second-brain/wiki/index.md` exists in the checked-out repo, and if so, read it (and pages it links to) and pass a summary as extra context in the subagent's task description. Prompt-text only — no new Python logic, no import of `second_brain`, no change to `_RESULT_SCHEMA` or any other file. `code_review_cli` doesn't know `second_brain` exists as a package; it just conditionally reads a folder if present. This is the only line item from this spec that touches `code_review_cli`.

## Requirements and accepted risks

Three operational questions came out of the subagent review specifically because they're judgment calls, not implementation details — resolved here explicitly so they're visible, not defaults an implementer picked silently:

- **Credentials:** `second_brain`'s wrapper process runs `gh`/`git`/`aws` directly and therefore needs those credentials available in its own environment (not isolated inside a headless container, unlike `code_review_cli`). **Decision: reuse whatever `gh`/AWS credentials are already configured in the operator's/CI's environment** — no dedicated scoped service account for this tool. Accepted tradeoff: a bug in `git_ops.py` runs with whatever access that credential already has, with no additional sandboxing. Document this as a `Requirements` item in `second_brain`'s own README, the same way `code_review_cli`'s README documents its credential requirements.
- **Secrets/PII in committed content:** PR descriptions/comments are cached verbatim into `raw/*.md` and may be quoted into `decisions/*.md`; both get locally committed to the target repo's own git history by Phase C. **Decision: no automated secrets/PII scan for this version** — the human reviewing the local diff before pushing is the only gate, matching the 2026-08-13 design's original approach. Given this organization treats internal code and data as confidential, this is flagged explicitly as an accepted risk rather than an oversight: **anyone deploying this tool should have their security/compliance function review this decision before rollout to repos that may contain customer PII or credentials in PR discussion history.**
- **Audit logging:** because `git_ops.py` takes real actions against a real repo/PR-provider account directly (not LLM-mediated, so there's no SDK transcript recording them for free), **every command it runs is appended to `.second-brain/audit.log`** (timestamp, command with any embedded secrets redacted, exit code) before/after execution, as described in "Package layout" and "Storage" above. This log is committed alongside the rest of `.second-brain/`, so it travels with the same diff a human reviews before pushing.

## Testing

- `second_brain`'s deterministic modules (`git_ops.py`, `wiki.py`) get pytest unit tests against real files on `tmp_path` — fixture wiki directories with known-good and known-bad frontmatter, real local `git` plumbing (`log`, `diff`, `commit`) against a throwaway local repo fixture (no mocking needed for these, since they're pure local git operations with no network/credentials involved). `git_ops.py`'s `gh`/`aws` calls specifically (clone, PR listing) are tested via `subprocess.run`/`check_output` mocking — no live network or credentials in CI, same reasoning `code_review_cli` already applies to the SDK's `query()`. This is the majority of the test surface, and it's exactly the kind of deterministic, fast, reliable testing the compiler-split makes possible that the original all-LLM design couldn't have had.
- `runner.py`'s one `query()` call (Phase B only) reuses `code_review_cli.runner`'s duck-typed-fake convention (`types.SimpleNamespace` fakes shaped like SDK messages, no import of real SDK classes) — same reasoning: an SDK version bump only touches this one file.
- `cli.py` gets `test_cli.py`-style argument-parsing and subcommand-wiring tests, following `code_review_cli`'s existing conventions for consistency across the two packages (same testing *style*, zero shared *code*).
- **Manual end-to-end validation** (restored from the 2026-08-13 design — Phase B is still inherently LLM-judgment work, so the rationale for this still applies even though most of the codebase is now unit-testable):
  1. `second-brain ingest --repo <test-repo> --provider github` on a repo with no `.second-brain/` yet → confirm bootstrap creates `wiki/index.md`, `wiki/log.md`, `wiki/state.json`, `audit.log`, and at least one `modules/*.md` page with correct frontmatter (including `confidence`) and provenance.
  2. Make a small commit to the test repo, re-run `ingest` → confirm only the affected page(s) update, `log.md` gets a new entry, `state.json`'s commit pointer advances, and a superseded fact gets `status: stale` + `supersedes`, not deletion.
  3. Delete a module the test repo's wiki has a page for, re-run `ingest` → confirm Phase A's deleted-module check marks that page `status: stale` without needing Claude's involvement (verify via `--verbose` that no `query()` call happened if that was the only change).
  4. Run `second-brain lint` → confirm it correctly flags an orphaned or stale page seeded manually, with zero `query()` calls (verify via `--verbose`).
  5. Run `code-review review --repo <test-repo> --pr <n> --provider github --verbose` (the *other* package) and confirm, from the streamed message log, that Claude actually reads `.second-brain/wiki/index.md` before dispatching the reviewer subagent(s).
- `code_review_cli`: one new assertion in `test_prompts.py` per level, confirming the dispatch instructions mention conditionally reading `.second-brain/wiki/index.md`.

## Critical files

- New: `src/second_brain/{validation,git_ops,wiki,prompts,runner,result,cli}.py`.
- New: `tests/test_second_brain_{validation,git_ops,wiki,prompts,runner,cli}.py` — flat, in the existing `tests/` directory, prefixed to disambiguate from `code_review_cli`'s same-named test files (`tests/test_validation.py` stays `code_review_cli`'s; `second_brain`'s equivalent is `tests/test_second_brain_validation.py`). Keeps one `pytest tests/ -v` running both packages' suites, matching this repo's existing single flat `tests/` convention — no new subdirectory.
- Modify: `pyproject.toml` — `second_brain` is declared as a second package under the same src-layout (`src/second_brain/`), discovered alongside `code_review_cli`, plus a `[project.scripts]` entry for `second-brain`; one `pip install -e .` installs both. Not a second distributable package with its own `pyproject.toml` — isolation here means independent module trees and zero cross-imports, not independent packaging/versioning.
- Modify: `src/code_review_cli/prompts.py` — the one closing-the-loop addition described above, plus its corresponding `tests/test_prompts.py` assertions.
- Reference only, not modified: `docs/superpowers/specs/2026-08-13-second-brain-design.md` — this spec supersedes its architecture section; its storage/schema section is still the reference for *why* the frontmatter contract looks the way it does.
