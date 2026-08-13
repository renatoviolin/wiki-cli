# Second Brain for Code Review — Design

## Context

`code_review_cli` (planned in `docs/superpowers/plans/2026-08-13-code-review-cli.md`, not yet implemented) invokes headless Claude Code to run the existing `/code-review` skill against a PR, with zero persistent memory between runs — every review starts from a blank slate, re-deriving architecture and conventions from scratch and never accumulating what past reviews already learned.

The goal is a second, complementary skill — `/second-brain` — that creates and maintains a durable, cross-referenced knowledge base per target repository, so both the review agent and human reviewers get better context and inference over time. The design follows Andrej Karpathy's "LLM Wiki" pattern (his April 2026 gist: raw sources → a structured, cross-referenced wiki → a schema contract, maintained by an agent via `ingest`/`query`/`lint` operations) rather than a flat set of summary docs, because the explicit ask is to capture *relations between facts*, not just facts.

This design assumes `code_review_cli`'s validation/prompts/result/runner modules exist, since it generalizes and extends them. If that plan hasn't been implemented yet, do it first.

## Goals

- A skill that builds and incrementally maintains a per-repo knowledge base capturing architecture, conventions, gotchas, and decisions — with explicit, typed relations between entries, not a flat list of facts.
- Consumable by any agent or human as plain files, with no bespoke tooling required to read it.
- Triggerable on-demand from `code_review_cli` as a new subcommand, using the same headless-invocation pattern the review command already uses.
- Feeds into `/code-review` so reviews benefit from accumulated context, without modifying that skill itself.

## Non-goals (deferred)

- A semantic query tool / MCP server over the knowledge base (plain-file consumption is v1; a query layer is an explicit future extension).
- Automatic maintenance on every review run (this is on-demand only, via an explicit CLI command).
- CI/webhook triggering, PR-comment posting, or any UI beyond the files themselves.
- Guarding against concurrent `ingest` runs on the same repo — this is a single-operator, on-demand CLI expected to run one invocation at a time.

## Design

### Storage: `.second-brain/` at the target repo's root, git-tracked

The code and its git history already are the "raw" layer (immutable, single source of truth) — no need to duplicate them. The one external gap is PR descriptions/review comments, which live outside git and can change upstream, so those get an immutable cached snapshot.

```
.second-brain/
├── SCHEMA.md              # relation vocabulary + operating contract (schema layer)
├── raw/
│   └── pr-<n>-<date>.md    # immutable, timestamped snapshot of a PR's description/review comments at ingest time
└── wiki/
    ├── index.md            # master catalog: every page, one-line summary, category, metadata
    ├── log.md              # append-only ops log (ingest/query/lint runs), grep-able
    ├── state.json           # last_processed_commit, last_updated_at — drives incremental ingest
    ├── modules/<name>.md    # entity pages: one per significant module/package
    ├── concepts/<name>.md   # cross-cutting synthesis: patterns, flows, conventions
    └── decisions/<slug>.md  # decisions/gotchas with provenance
```

Every wiki page carries frontmatter:
```yaml
---
type: module | concept | decision
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
Typed relations (`depends_on`, `implements`, `supersedes`, `contradicts`, `about`) live in frontmatter so any agent can parse them mechanically, while page bodies stay human-readable prose. Superseded facts are marked `status: stale` with a `supersedes` link — never silently overwritten — so history survives (mirrors Karpathy's provenance-first rule: no wiki-page-only citations, everything traces back to a raw source). `provenance` is required and must resolve to at least one non-wiki source (a commit SHA, `file:line`, or `raw/*.md` snapshot); `lint` rejects any page citing only other wiki pages. This guarantee is page-level, not claim-level — a `concepts/*.md` page synthesized across many ingests can still drift from what any single cited source says even while its frontmatter `provenance` resolves cleanly. That's a known limitation of this design, not something v1 solves.

What counts as a "significant module" (worth its own `modules/*.md` page) is a judgment call the skill makes, anchored to signals like "a top-level package/directory with its own entry point" or "a directory with enough internal structure to need its own summary" — documented as guidance in `SCHEMA.md`, not a fixed threshold.

Files are plain markdown/JSON — no query tool required to consume them now (any agent, human or LLM, just reads them); a semantic query tool/MCP server over this same folder is an explicit future extension, not part of this design.

### Operations (the `/second-brain` skill)

- **`ingest`** (default; `--full` forces a full rebuild instead of incremental). All of the following — git operations, reading/writing `state.json`, file writes — happens *inside headless Claude Code itself*, the same way it already performs PR checkout for `/code-review`; the Python wrapper only builds the prompt and never touches git/state directly (the existing "wrapper never runs git/gh/aws" constraint, applied consistently to this skill too):
  1. Read `wiki/state.json` (missing → first-run bootstrap). If `last_processed_commit` is no longer reachable from `HEAD` (rebase/force-push), fall back to `--full` automatically and note it in `log.md`.
  2. `git log <last_processed_commit>..HEAD` to scope what changed.
  3. Regenerate `modules/*.md` / `concepts/*.md` for touched areas (or everything, on `--full`). A page whose module/directory was deleted or renamed is marked `status: stale` immediately here — not deferred to `lint`.
  4. Fetch new PR descriptions/review comments since last run (via `gh`/`aws codecommit`, same tool access `/code-review` already has), cache each as an immutable, timestamped snapshot (`raw/pr-<n>-<ingest-date>.md` — re-ingesting a still-open PR adds a new snapshot rather than overwriting or silently skipping), and mine them plus commit messages for `decisions/*.md` entries and gotchas — appending, never rewriting. While doing this, check new content against existing pages for direct contradictions and link them via `contradicts` — this is that relation's only writer.
  5. Update `index.md`, append an entry to `log.md`, update `state.json`, commit `.second-brain/` locally (not pushed — the human running the CLI reviews the diff before pushing). Note this is narrower than Karpathy's "humans review before canonical": pages are locally committed — provisionally canonical in the repo — before a human reads their content; only the *push* is gated, not authorship. Accepted as sufficient for v1 since `ingest` is always human-triggered on demand, never automatic.
- **`lint`**: health check — orphaned pages (nothing links in/out, or they reference deleted modules), stale claims (`last_verified_commit` far behind HEAD for that area), missing cross-references, unresolved `contradicts` links, and any page whose `provenance` is empty or resolves only to other wiki pages (violates the provenance-first rule). Appends a report to `log.md` and flags affected pages `status: needs-review`.
- **`query`** *(stretch goal, not required for v1)*: read `index.md`, walk relevant pages, answer with citations; optionally file the answer back as a new page.

The skill is authored as a **global/personal Claude Code skill** (same install pattern as the existing `/code-review`), not scaffolded per target repo, so it works uniformly across every repo the CLI clones.

### CLI integration (`code_review_cli`)

- Add `run_headless_task(prompt) -> ReviewResult` as a new, *additive* primitive in `runner.py`, carrying the existing workspace-lifecycle and never-raises contract; `run_review(provider, repo, pr)` becomes a thin wrapper — `run_headless_task(build_prompt(provider, repo, pr))` — so its existing signature and all of `test_runner.py` keep working unchanged.
- Extend `prompts.py` with `build_brain_prompt(provider, repo, op, full=False) -> str` (shared preamble + provider checkout fragment, minus the PR-specific step — just clone the default branch — plus an instruction to run `/second-brain <op>` at a fixed effort level, mirroring how the review preamble already pins `medium` rather than exposing it as a flag).
- `cli.py` gains real subcommand structure via `argparse` subparsers: `review` (wrapping the base plan's existing top-level `--repo`/`--pr`/`--provider` behavior, since it has no subcommand today), `brain ingest --repo <repo> --provider <provider> [--full]`, and `brain lint --repo <repo> --provider <provider>` — all reusing `validation.py`'s existing `validate_provider`/`validate_repo`. This is a real restructuring of `cli.py`/`test_cli.py`'s invocation style, not just additive wiring on top of the existing flat parser.

### Closing the loop with `/code-review`

Small addition to the existing review prompt in `prompts.py` (wrapper-owned, not the black-boxed `/code-review` skill itself): after checkout, before invoking `/code-review`, instruct Claude to read `.second-brain/wiki/index.md` and any pages it links to, if the folder exists, and treat that as review context.

## Testing

- Deterministic wrapper-side pieces (prompt building, CLI arg wiring, the `run_review`/`run_headless_task` split) get pytest unit tests, same conventions as `test_validation.py`/`test_prompts.py`/`test_runner.py`. `state.json` read/write and git operations run inside headless Claude Code as part of the skill, not wrapper Python — they're validated by the manual end-to-end runs below, not unit tests.
- The skill's actual content-generation logic is inherently LLM-judgment work, not deterministic code — validate it with a manual end-to-end run against a small real test repo:
  1. `code-review brain ingest --repo <test-repo> --provider github` on a repo with no `.second-brain/` yet → confirm bootstrap creates `wiki/index.md`, `wiki/log.md`, `wiki/state.json`, and at least one `modules/*.md` page with correct frontmatter and provenance.
  2. Make a small commit to the test repo, re-run `ingest` → confirm only the affected page(s) update, `log.md` gets a new entry, `state.json`'s commit pointer advances, and nothing is silently overwritten (check a superseded fact gets `status: stale` + `supersedes`, not deletion).
  3. Run `code-review brain lint` → confirm it correctly flags an orphaned or stale page you seed manually.
  4. Run `code-review review --repo <test-repo> --pr <n> --provider github` and confirm (via `--verbose` on the underlying SDK/CLI trace) that Claude actually reads `.second-brain/wiki/index.md` before invoking `/code-review`.

## Critical files

- `docs/superpowers/plans/2026-08-13-code-review-cli.md` — prerequisite plan/pattern this extends.
- `src/code_review_cli/runner.py`, `prompts.py`, `validation.py` (once they exist) — generalize/extend rather than duplicate.
- New: the `/second-brain` skill's `SKILL.md` (authored per `superpowers:writing-skills` conventions), installed globally alongside `/code-review`.
- New: `review`/`brain ingest`/`brain lint` subparser wiring inside `src/code_review_cli/cli.py`.
