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

## Design

### Storage: `.second-brain/` at the target repo's root, git-tracked

The code and its git history already are the "raw" layer (immutable, single source of truth) — no need to duplicate them. The one external gap is PR descriptions/review comments, which live outside git and can change upstream, so those get an immutable cached snapshot.

```
.second-brain/
├── SCHEMA.md              # relation vocabulary + operating contract (schema layer)
├── raw/
│   └── pr-<n>.md           # immutable snapshot of a PR's description/review comments at ingest time
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
provenance: [commit sha / file:line / raw/pr-12.md]
last_verified_commit: <sha>
status: active | stale | superseded
---
```
Typed relations (`depends_on`, `implements`, `supersedes`, `contradicts`, `about`) live in frontmatter so any agent can parse them mechanically, while page bodies stay human-readable prose. Superseded facts are marked `status: stale` with a `supersedes` link — never silently overwritten — so history survives (mirrors Karpathy's provenance-first rule: no wiki-page-only citations, everything traces back to a raw source).

Files are plain markdown/JSON — no query tool required to consume them now (any agent, human or LLM, just reads them); a semantic query tool/MCP server over this same folder is an explicit future extension, not part of this design.

### Operations (the `/second-brain` skill)

- **`ingest`** (default; `--full` forces a full rebuild instead of incremental):
  1. Read `wiki/state.json` (missing → first-run bootstrap).
  2. `git log <last_processed_commit>..HEAD` to scope what changed.
  3. Regenerate `modules/*.md` / `concepts/*.md` for touched areas (or everything, on `--full`).
  4. Fetch new PR descriptions/review comments since last run (via `gh`/`aws codecommit`, same tool access `/code-review` already has), cache them under `raw/`, and mine them plus commit messages for `decisions/*.md` entries and gotchas — appending, never rewriting.
  5. Update `index.md`, append an entry to `log.md`, update `state.json`, commit `.second-brain/` locally (not pushed — the human running the CLI reviews the diff before pushing, satisfying Karpathy's "human reviews before canonical" principle without extra infra).
- **`lint`**: health check — orphaned pages (nothing links in/out, or they reference deleted modules), stale claims (`last_verified_commit` far behind HEAD for that area), missing cross-references. Appends a report to `log.md` and flags affected pages `status: needs-review`.
- **`query`** *(stretch goal, not required for v1)*: read `index.md`, walk relevant pages, answer with citations; optionally file the answer back as a new page.

The skill is authored as a **global/personal Claude Code skill** (same install pattern as the existing `/code-review`), not scaffolded per target repo, so it works uniformly across every repo the CLI clones.

### CLI integration (`code_review_cli`)

- Generalize `runner.py`'s `run_review` into a shared headless-invocation primitive (e.g. `run_headless_task(prompt) -> ReviewResult`), reused by both the existing review flow and the new brain flow.
- Extend `prompts.py` with `build_brain_prompt(provider, repo, op, full=False) -> str` (shared preamble + provider checkout fragment, minus the PR-specific step — just clone the default branch — plus an instruction to run `/second-brain <op>` at the given effort level).
- New CLI subcommands: `code-review brain ingest --repo <repo> --provider <provider> [--full]` and `code-review brain lint --repo <repo> --provider <provider>`, reusing `validation.py`'s existing `validate_provider`/`validate_repo`.

### Closing the loop with `/code-review`

Small addition to the existing review prompt in `prompts.py` (wrapper-owned, not the black-boxed `/code-review` skill itself): after checkout, before invoking `/code-review`, instruct Claude to read `.second-brain/wiki/index.md` and any pages it links to, if the folder exists, and treat that as review context.

## Testing

- Deterministic pieces (`state.json` read/write, prompt building, CLI arg wiring) get pytest unit tests, same conventions as `test_validation.py`/`test_prompts.py`/`test_runner.py`.
- The skill's actual content-generation logic is inherently LLM-judgment work, not deterministic code — validate it with a manual end-to-end run against a small real test repo:
  1. `code-review brain ingest --repo <test-repo> --provider github` on a repo with no `.second-brain/` yet → confirm bootstrap creates `wiki/index.md`, `wiki/log.md`, `wiki/state.json`, and at least one `modules/*.md` page with correct frontmatter and provenance.
  2. Make a small commit to the test repo, re-run `ingest` → confirm only the affected page(s) update, `log.md` gets a new entry, `state.json`'s commit pointer advances, and nothing is silently overwritten (check a superseded fact gets `status: stale` + `supersedes`, not deletion).
  3. Run `code-review brain lint` → confirm it correctly flags an orphaned or stale page you seed manually.
  4. Run `code-review review --repo <test-repo> --pr <n> --provider github` and confirm (via `--verbose` on the underlying SDK/CLI trace) that Claude actually reads `.second-brain/wiki/index.md` before invoking `/code-review`.

## Critical files

- `docs/superpowers/plans/2026-08-13-code-review-cli.md` — prerequisite plan/pattern this extends.
- `src/code_review_cli/runner.py`, `prompts.py`, `validation.py` (once they exist) — generalize/extend rather than duplicate.
- New: the `/second-brain` skill's `SKILL.md` (authored per `superpowers:writing-skills` conventions), installed globally alongside `/code-review`.
- New: `src/code_review_cli/brain_cli.py` or subcommand wiring inside `cli.py`.
