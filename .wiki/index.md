# claude-code-review

This repository holds two independent Python CLIs, packaged together under `src/`
(`pyproject.toml`'s `[tool.setuptools.packages.find]`, `where = ["src"]`) but sharing
**zero imports** between them:

- **[code-review-cli](code-review-cli.md)** — `code-review-cli.md`'s subject,
  installed as the `code-review` console script. Validates `--repo`/`--pr`/`--provider`
  input, builds a task prompt, and hands off to a headless Claude Code session that checks
  out a pull request and dispatches the `voltagent-qa-sec:code-reviewer` subagent (or, at
  `--level hard`, five subagents plus a judge) to actually review it.
- **[wiki-cli](wiki-cli.md)** — installed as the `wiki` console script, and the tool
  that generated this knowledge base. Takes no repo/provider arguments; it operates on the
  current checkout, writing `.wiki/` pages under an evidence-discipline prompt, and stops
  without committing.

The only coupling between them is a convention, not code: `code-review-cli.md`'s prompt
instructs the review session to read `.wiki/` (this directory) for context if it exists in
the PR's repository, and to prefer the code over the wiki wherever they disagree.
`design-history.md` covers how both tools' current shape came out of an evolving series of
design proposals — including three second-brain designs that were superseded before being
built.

Both CLIs are invoked the same way: `pip install -e .` from the repo root, then
`python -m code_review_cli.cli ...` or `python -m wiki_cli.cli ...` (equivalently, the
`code-review`/`wiki` console scripts once installed). Full test suite:
`pytest tests/ -v`, from the repo root — `tests/` is flat, with `code_review_cli` tests
named `test_*.py` and `wiki_cli` tests prefixed `test_wiki_*.py`.

No linter or formatter is configured in `pyproject.toml`, and the repository convention is
zero code comments anywhere — both stated in the top-level `CLAUDE.md`.

## Task-routing table

| I want to change... | Page | Source entrypoints | Key symbols | Tests | Validate with |
|---|---|---|---|---|---|
| CLI flags / input validation for the review command | [code-review-cli](code-review-cli.md) | `src/code_review_cli/cli.py`, `src/code_review_cli/validation.py` | `main`, `validate_provider`, `validate_pr`, `validate_repo`, `validate_model`, `validate_level` | `tests/test_cli.py`, `tests/test_validation.py` | `pytest tests/test_cli.py tests/test_validation.py -v` |
| What the review prompt tells Claude Code to do, or the light/standard/hard dispatch tiers | [code-review-cli](code-review-cli.md) | `src/code_review_cli/prompts.py` | `build_prompt`, `_LEVEL_INSTRUCTIONS`, `_RESULT_SCHEMA` | `tests/test_prompts.py` | `pytest tests/test_prompts.py -v` |
| How the SDK session is invoked, workspace lifecycle, or metrics aggregation for review runs | [code-review-cli](code-review-cli.md) | `src/code_review_cli/runner.py` | `run_review`, `_run_review_async` | `tests/test_runner.py` | `pytest tests/test_runner.py -v` |
| What every `.wiki/` page must cover, or the evidence-discipline rules | [wiki-cli](wiki-cli.md) | `src/wiki_cli/prompts.py` | `build_prompt`, `_EVIDENCE_DISCIPLINE`, `_STRUCTURE_RULES` | `tests/test_wiki_prompts.py` | `pytest tests/test_wiki_prompts.py -v` |
| The `create`/`update` workflow the wiki-generation session follows | [wiki-cli](wiki-cli.md) | `src/wiki_cli/prompts.py` | `_CREATE_INSTRUCTIONS`, `_UPDATE_INSTRUCTIONS` | `tests/test_wiki_prompts.py` | `pytest tests/test_wiki_prompts.py -v` |
| How the wiki-generation session is invoked or why it runs in-place instead of a temp workspace | [wiki-cli](wiki-cli.md) | `src/wiki_cli/runner.py` | `run_wiki`, `_run_wiki_async` | `tests/test_wiki_runner.py` | `pytest tests/test_wiki_runner.py -v` |
| CLI flags or stdout/stderr contract for either tool | [code-review-cli](code-review-cli.md) / [wiki-cli](wiki-cli.md) | `src/code_review_cli/cli.py` / `src/wiki_cli/cli.py` | `main`, `_print_metrics` | `tests/test_cli.py` / `tests/test_wiki_cli.py` | `pytest tests/test_cli.py -v` / `pytest tests/test_wiki_cli.py -v` |
| The result/exit-code shape either tool returns | [code-review-cli](code-review-cli.md) | `src/code_review_cli/result.py`, `src/wiki_cli/result.py` | `ReviewResult`, `WikiResult`, `exit_code` | `tests/test_result.py` | `pytest tests/test_result.py -v` |
| Whether a design idea in `docs/` is current or superseded | [design-history](design-history.md) | `docs/superpowers/plans/`, `docs/superpowers/specs/` | — | — | — |

## Backlog

Deliberate deferrals found during this pass, not gaps in coverage:

- **CI/webhook triggering, PR-comment posting, JSON output, and secret/PII redaction for
  `code-review-cli`** are explicitly out of scope per its own `README.md` ("Scope"
  section) — not partially built, not planned in any current doc.
- **`docs/superpowers/specs/*.md`** (three second-brain/PR-memory designs) are
  intentionally undocumented as *current* behavior here, since none of them were built —
  see `design-history.md` for what shipped instead.
- **`second-brain-for-business.md`** is a stakeholder-facing summary of an unshipped,
  more elaborate design than what actually exists (`wiki-cli.md`); flagged as stale in
  `design-history.md` rather than treated as a description of current capability.

## Decisions & rationale

Conversation-captured decisions and rationale, logged via the `wiki-remember` skill.

| Category | Decision | Status | Captured | File |
|---|---|---|---|---|
| wiki-remember-design | Quick, low-risk wiki-remember improvements implemented first; deeper memory tooling deferred | active | 2026-08-27 | [decisions/wiki-remember-design/2026-08-27-roadmap-quick-wins-first.md](decisions/wiki-remember-design/2026-08-27-roadmap-quick-wins-first.md) |
| wiki-remember-design | Category chosen dynamically per finding, not a fixed storage layout | active | 2026-08-27 | [decisions/wiki-remember-design/2026-08-27-dynamic-category-per-finding.md](decisions/wiki-remember-design/2026-08-27-dynamic-category-per-finding.md) |
| wiki-remember-design | Decisions stored as one dated file per category directory, not a flat log or per-page grouping | superseded | 2026-08-27 | [decisions/wiki-remember-design/2026-08-27-decision-storage-layout.md](decisions/wiki-remember-design/2026-08-27-decision-storage-layout.md) |
