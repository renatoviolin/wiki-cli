# Review Levels — Design

## Context

`code_review_cli` currently runs one fixed review shape regardless of the PR: a single headless Claude Code session checks out the PR and dispatches exactly one subagent, `voltagent-qa-sec:code-reviewer`, then replies with `{success, review, failure_reason}` via a strict `output_format` JSON schema (`src/code_review_cli/prompts.py`, `_SHARED_PREAMBLE`). Every run gets the same depth and the same cost, whether the PR is a one-line typo fix or a risky change to the credit/payments path.

The goal is a `--level` flag with three tiers — `light`, `standard` (today's unchanged behavior), `hard` — so cheap, low-risk PRs can get a narrower/cheaper pass and risky PRs can get a multi-agent review with adversarial verification, without changing the CLI's external contract (`{success, review, failure_reason}` stays identical across all three levels).

This design builds on the actual current implementation (`src/code_review_cli/{validation,prompts,result,runner,cli}.py`), not a hypothetical rewrite.

## Goals

- A `--level light|standard|hard` flag, default `standard`, validated before Claude Code is ever invoked (same fail-fast pattern as `--repo`/`--pr`/`--provider`/`--model`).
- `standard` is byte-for-byte today's behavior — existing callers who never pass `--level` see zero change.
- `light`: single `code-reviewer` dispatch, task description narrowed to high-confidence correctness/security bugs only (skip style/best-practice/low-confidence nits), and defaults `--model` to haiku when the caller didn't explicitly set one.
- `hard`: fans out to five specialized subagents (`code-reviewer`, `security-auditor`, `performance-engineer`, `architect-reviewer`, `qa-expert`), each scoped to the PR, then a final judge subagent merges/dedupes their findings and adversarially re-questions each one — findings that don't survive that check are dropped — before the judge's synthesis becomes the final `review` text.
- All orchestration (fan-out, waiting for subagent reports, judging) happens *inside* the single headless Claude Code session, driven entirely by the prompt — consistent with the existing "wrapper never runs git/gh/aws itself" invariant. `runner.py` still makes exactly one `query()` call per run, for every level.

## Non-goals (deferred)

- Any change to `_RESULT_SCHEMA` — `review` stays a single string for all levels; there's no structured per-agent breakdown returned to the caller.
- Per-agent cost/token attribution — `model_usage` is already summed across every model a run touches (orchestrator + all dispatched subagents combined); this design doesn't add a way to see hard mode's cost broken out by which of the five agents spent it.
- Parallelizing the five hard-mode subagent dispatches at the SDK/code level (Approach B, rejected) — the orchestrating session decides for itself how to sequence its own Agent tool calls; this design doesn't add Python-level concurrency (e.g. `asyncio.gather` across multiple `query()` calls).
- A middle ground between "five fixed agents" and "single agent" — `hard` always dispatches the same five, there's no way to pick a custom subset from the CLI.

## Design

### CLI interface (`cli.py`, `validation.py`)

- New `validate_level(level: str | None) -> str` in `validation.py`, mirroring `validate_provider`'s pattern: valid values are `{"light", "standard", "hard"}`; `None` resolves to `"standard"`; anything else raises `ValidationError` (exit code 2, same as every other invalid input).
- New `parser.add_argument("--level", default=None)` in `cli.py`. `main()` validates it alongside the other four inputs, before `run_review` is ever called.
- Light-mode model default: after validating both `level` and `model`, if `level == "light"` and the caller didn't pass `--model` (i.e. `validate_model(args.model)` returned `None`), `cli.py` resolves `model` to `"claude-haiku-4-5"` before calling `run_review`. `standard` and `hard` are unaffected — `model` stays whatever `validate_model` returned (including `None`, letting the SDK pick its own default), exactly as today.
- `_print_metrics` gains one more line item, `level={level}`, always printed (not conditional) so every run's metrics are attributable to a level in logs.

### `prompts.py`

- `build_prompt(provider: str, repo: str, pr: int, level: str = "standard") -> str` — new `level` parameter.
- The "dispatch subagent(s)" instruction (today hardcoded as step 2 of `_SHARED_PREAMBLE`) is extracted into a `_LEVEL_INSTRUCTIONS: dict[str, str]` keyed by level, interpolated into `_SHARED_PREAMBLE` in place of the current fixed step 2 text:
  - **`standard`**: the existing instruction, verbatim — dispatch `voltagent-qa-sec:code-reviewer`, wait for its report, use it as `review`. No behavioral change from today.
  - **`light`**: dispatch only `voltagent-qa-sec:code-reviewer`, with an added instruction in its task description to report only high-confidence correctness and security bugs, explicitly excluding style, best-practice, and low-confidence/nit-level findings.
  - **`hard`**: dispatch all five subagents in turn — `voltagent-qa-sec:code-reviewer`, `voltagent-qa-sec:security-auditor`, `voltagent-qa-sec:performance-engineer`, `voltagent-qa-sec:architect-reviewer`, `voltagent-qa-sec:qa-expert` — each with a task description scoped to this PR's changes, and wait for all five reports. Then dispatch one more subagent (no specific `subagent_type`, i.e. the default agent) as judge, giving it all five reports and instructing it to: merge overlapping/duplicate findings into one coherent list; for each remaining finding, adversarially ask whether it's a genuine issue or a false positive, and drop it if it doesn't survive that check; produce the final merged, verified report. The judge's report becomes `review` in the final JSON reply.
- `_RESULT_SCHEMA` is untouched — identical shape for every level.
- `_CHECKOUT_TEMPLATES` (provider-specific checkout instructions) is unaffected by this change; `level` only varies the post-checkout dispatch step.

### `runner.py` / `result.py`

- `_run_review_async` and `run_review` gain `level: str = "standard"`, threaded straight into `build_prompt(provider, repo, pr, level)`. No other change to the SDK call shape — one `ClaudeAgentOptions`, one `query()` call, for every level.
- `_MAX_TURNS = 60` was sized around a single-subagent run. Hard mode drives six subagent dispatches (five reviewers + judge) plus the orchestrator's own checkout/coordination turns instead of one, so this constant needs raising — recommendation: bump the shared constant to `150` (applies to all levels; harmless for light/standard, which will simply finish in far fewer turns than the cap).
- `ReviewResult`'s fields are unchanged. No new fields are added for level or per-agent breakdown (see Non-goals).

### Testing

- `tests/test_validation.py`: add cases for `validate_level` — each valid value round-trips, `None` resolves to `"standard"`, an invalid string raises `ValidationError`.
- `tests/test_prompts.py`: one fixture per level — `standard`'s output must match today's existing fixture exactly (regression guard for the "zero change to existing callers" goal); `light`'s output must mention only `code-reviewer` and the narrowed-scope language; `hard`'s output must mention all five agent names plus the judge/merge/adversarial-verification instruction.
- `tests/test_runner.py`: assert `level` is forwarded from `run_review`/`_run_review_async` into `build_prompt` (following the existing fakes-based convention, no real SDK calls).
- `tests/test_cli.py`: cover `--level` argument parsing and its default; invalid `--level` value exits with code 2 (same path as other validation errors); the light-mode implicit haiku default is applied only when `--model` wasn't explicitly given, and is not applied for `standard`/`hard`.

## Open questions

None outstanding — all decisions in this design were confirmed during brainstorming (level count, judge behavior, hard-mode agent roster, light-mode scope-plus-model-default).
