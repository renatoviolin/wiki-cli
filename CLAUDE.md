# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`code-review-cli` is a thin CLI that triggers a **headless** Claude Code review of a pull request. It does not review code itself: it validates input, builds a prompt, and hands off to a headless Claude Code session (via the Claude Agent SDK) which checks out the PR itself and dispatches the `voltagent-qa-sec:code-reviewer` subagent to do the actual review.

```bash
python -m code_review_cli.cli --repo <owner/repo> --pr <N> --provider github|codecommit [--model haiku|sonnet|opus] [--level light|standard|hard] [--verbose]
```

A second, independent CLI (`wiki_cli`) generates and maintains a `.wiki/` knowledge base for **the repository you are currently in**, which the review flow then reads to make better-informed reviews. It takes no repo/provider arguments — it operates on the current checkout, writes files, and stops without committing; the developer commits `.wiki/` alongside their own work. A separate Claude Code Skill, `wiki-remember` (`.claude/skills/wiki-remember/SKILL.md`), also writes into `.wiki/` — interactively, from conversation, capturing decisions under `.wiki/decisions/`; `wiki_cli` is instructed to leave `.wiki/decisions/` and the index's "Decisions & rationale" section alone.

```bash
python -m wiki_cli.cli create|update [--model haiku|sonnet|opus] [--verbose]
```

## Commands

```bash
pip install -e .                      # install (editable), from repo root
pytest tests/ -v                      # run the full suite
pytest tests/test_runner.py -v        # run one test file
pytest tests/test_runner.py::test_run_review_returns_success_result -v   # run a single test
pytest tests/test_wiki_runner.py -v   # wiki_cli's tests are prefixed test_wiki_*
```

There is no linter or formatter configured in `pyproject.toml` — don't add `ruff`/`black`/etc. config unless asked.

## Releasing

Versioning is manual — no CI/automation does this. `README.md`'s install command deliberately has no `@tag` (`pip install git+https://github.com/renatoviolin/wiki-cli.git`), so every install picks up whatever is on `main` right now; there is no way to pin an older version through that command. Tags exist only as a release history, not as an install target.

Whenever a commit is meant to ship as a new release (not every commit — only ones that actually change what a fresh `pip install` from `main` gives a user):

1. Bump `version` in `pyproject.toml` (semantic versioning: `MAJOR.MINOR.PATCH`).
2. Add an entry to `CHANGELOG.md` describing what changed.
3. Commit both together.
4. Tag the commit: `git tag -a vX.Y.Z -m "vX.Y.Z - <short summary>"`.
5. `git push origin main --tags`.

## Architecture

Two independent packages under `src/`, sharing only this repository — **zero imports between them**. `code_review_cli` reviews a pull request; `wiki_cli` maintains the `.wiki/` knowledge base for the current checkout. The only coupling is a convention: the review prompt reads `.wiki/` if it happens to exist.

### `wiki_cli` — six modules (plus `bundled_skills` package data)

- **`prompts.py`** — `build_prompt(mode)` for `create` / `update`, plus the forced `_RESULT_SCHEMA` (`{success, summary, pages_written, failure_reason}`). The prompt has the session resolve the repo root itself (`git rev-parse --show-toplevel`) and, for `update`, find the wiki's last commit (`git log -1 --format=%H -- .wiki/`) and diff it against `HEAD` — so the wrapper still never runs git. The prompt body (~10KB per mode) is assembled from labelled sections — hard constraints, evidence discipline, page contract, structure, style, diagrams, finishing checks — plus one mode-specific workflow. A hard constraint in the shared preamble carves `.wiki/decisions/` out of both modes' regeneration/delete behavior and requires copying `index.md`'s "Decisions & rationale" section forward verbatim. See "Why the wiki prompt is written the way it is" below before editing any of it.
- **`result.py`** — `WikiResult`, mirroring `ReviewResult` plus `pages_written`.
- **`runner.py`** — the one `query()` call. Unlike `code_review_cli.runner` it uses `cwd=os.getcwd()` with **no temp workspace and no cleanup**, because it deliberately writes into the developer's real checkout.
- **`cli.py`** — argparse with subparsers `create`/`update`/`lint`/`install-skill`. `create`/`update` take the single positional mode plus `--model`/`--verbose`; `lint` is model-free; `install-skill` is simple main-only — only `[skill]` positional (default `wiki-remember`), `--force`, `--dry-run`, no `--from`/`--ref` flags. No `validation.py`: argparse `choices` covers the only arguments, and the small model-alias map lives inline.
- **`lint.py`** — pure mechanical checks over `.wiki/` on disk (no Claude call): `## Sources` presence and path existence, pytest-style `` `path::symbol` `` resolution, and advisory header-attributed symbol checks.
- **`skills.py`** — `install_skill()` — fetches `.claude/skills/<name>/SKILL.md` from `raw.githubusercontent.com/renatoviolin/wiki-cli/main` via `urllib`, handles `--force`/`--dry-run`, idempotent "already up to date" vs "already exists (use --force)" reporting, no SDK dependency.
- **`bundled_skills/`** — package data snapshot of `.claude/skills/*` shipped at pip install time (kept in sync via `scripts/sync-bundled-skills.sh`).

### `code_review_cli` — five modules

Five single-responsibility modules under `src/code_review_cli/` (src-layout package), wired together by `cli.py`:

- **`validation.py`** — validates `--repo`/`--pr`/`--provider`/`--model`/`--level` and raises `ValidationError`. All five inputs are validated **before** Claude Code is ever invoked; `cli.py` must never call `run_review` on invalid input (exit code 2).
- **`prompts.py`** — pure string templating, no imports from the rest of the package. `build_prompt()` renders the task Claude receives: check out the PR (provider-specific `gh`/`aws` instructions), dispatch `voltagent-qa-sec:code-reviewer` via the Agent tool, then reply with JSON matching `_RESULT_SCHEMA` (`{success, review, failure_reason}`). Also carries an explicit instruction *not* to substitute a different repo/PR if the named one can't be resolved — fail closed instead.
- **`result.py`** — `ReviewResult` dataclass: `success`, `text`, `error_message`, plus run metrics (`cost_usd`, `duration_ms`, `num_turns`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_creation_tokens`). `exit_code()` maps `success` to 0/1.
- **`runner.py`** — the only module that touches the Claude Agent SDK. Creates a fresh temp workspace per run (`code-review-*`), invokes `query()` with `output_format` forcing the JSON schema above, and parses the streamed messages into a `ReviewResult`. Deletes the workspace on success; leaves it in place on failure for post-mortem debugging.
- **`cli.py`** — argparse entrypoint. Validates, calls `run_review`, prints a `[metrics] ...` summary line to **stderr** (always, regardless of outcome), then the review text to **stdout** on success or the error to stderr on failure. stdout's contract is strictly "review text only, nothing else" — verbose/metrics output must never leak onto stdout.

### Non-obvious invariants (read before touching `runner.py`)

- **The wrapper never runs `git`/`gh`/`aws` itself.** Checkout happens entirely inside the headless Claude Code session, driven by the prompt from `prompts.py`. Credentials are pre-provisioned in the container and never read/validated by this code.
- **`is_error=False` on the SDK's `ResultMessage` does NOT mean the review succeeded.** A session can complete normally (`is_error=False`) while the underlying task failed (bad checkout, unresolvable repo). Real success/failure comes from `structured_output.success` (the forced JSON schema), not from `is_error` alone — this was a real production bug (a failed run reported success, exit 0) fixed by adding `output_format`.
- **`ClaudeAgentOptions(setting_sources=["user", "project"], ...)` is deliberate, not incidental.** Dispatching `voltagent-qa-sec:code-reviewer` requires the SDK to discover that plugin-provided subagent, which needs `"user"`/`"project"` settings scope. Explicitly excluding `"local"` scope isolates the run from the operator's personal permission/hook config. Do not set `setting_sources=[]` — that breaks subagent discovery entirely (confirmed against the SDK's own source, which auto-defaults this only when `skills=[...]` is set and nothing else).
- **`runner.py` duck-types SDK messages via `hasattr()` rather than importing SDK message classes** (`ResultMessage`, `AssistantMessage`, etc.), so an SDK version bump only requires changes in this one file. Tests follow the same convention: fakes are `types.SimpleNamespace` objects shaped like the real dataclasses, not imports of the real SDK classes.
- **Token/cost metrics require summing across `ResultMessage.model_usage`** (a `dict[str, ModelUsage]` keyed by model name — a run can span more than one model, e.g. the orchestrator plus the dispatched subagent). Both `inputTokens`/`outputTokens` *and* `cacheReadInputTokens`/`cacheCreationInputTokens` must be summed — omitting the cache fields produces a cost/token mismatch in the metrics line (a real bug caught from a production run: cost didn't reconcile with reported tokens because cache reads/writes, which dominate cost in multi-turn sessions, weren't counted).

### Why the wiki prompt is written the way it is

`wiki_cli/prompts.py` carries two instructions that look like fussy prose but are load-bearing, and both came from measurement rather than taste. We ran OpenWiki (LangChain's productized version of the same idea) against a real 63.7k-LOC Go repository and checked its output against the source. Architecture and behaviour were substantially accurate — 12 of 14 named symbols correct, the Postgres error-code claim correct and in the cited file. But roughly half the sampled *identifier* detail was invented: a type named `EvidenceFile` that didn't exist (the real one was `Evidence`), a field `sha256_hash` (real: `ContentHash`), a field `mime_type` absent from the repo entirely — all stated in exactly the same confident tone as the correct content. Full evidence in `docs/second-brain-alternatives-review.md`.

Hence the prompt's **evidence discipline** section, which is the load-bearing part: manifests, READMEs and import lines are *discovery* evidence only; before writing a page you must have inspected the entrypoint, the implementation, the public types, one caller upstream and one dependency downstream, and the representative tests. And hence **never name a symbol you haven't read** — describe behaviour instead.

Citations use **repository path plus symbol name** (`internal/api/handler.go` (`HandleUpload`)), deliberately *not* `file:line`. That choice came from LangChain's own production prompt, and the reasoning is sound: line numbers go stale within days, so a stale line reference is itself a false claim, while a path plus symbol stays both checkable and durable. An earlier version of this prompt required `file:line`; don't reintroduce it.

The rest of the prompt's structure — skeleton-first planning into `.wiki/_plan.md`, the task-routing table in `index.md`, decomposition rules, grounded-Mermaid rules, and the finishing self-checks — was adapted from OpenWiki's shipped `dist/agent/prompts/code.js`, which is the same prompt that produced the wiki we evaluated. Worth re-reading that file if you plan substantial changes here.

And hence the review prompt's rule that the code outranks the wiki, with instructions to report contradictions in the review, which is what makes the wiki self-correcting over time.

`docs/superpowers/specs/` contains three superseded designs (`2026-08-13-second-brain-design.md`, `2026-08-19-second-brain-v2-design.md`, `2026-08-25-pr-memory-design.md`) that proposed far more elaborate versions of this — typed relation graphs, provenance ontologies, quote-verification gates, executable convention matchers. They were all cut in favour of the simple thing that exists now. They are kept as history; don't resurrect them without reading why they were dropped.

### Design history

`docs/superpowers/plans/2026-08-13-code-review-cli.md` is the original implementation plan and has been kept in sync with the actual code as it evolved (src-layout, the review mechanism swapping from a built-in `/code-review` skill to explicitly dispatching `voltagent-qa-sec:code-reviewer`, the structured-output fix, etc.). It's the reference for *why* behind decisions that aren't obvious from the code alone.

## Code style

No comments in code, anywhere in this repository — this is an explicit, standing preference, not a default to override with judgment calls.
