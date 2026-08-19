# Review Levels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `--level light|standard|hard` flag to `code_review_cli` that controls review depth — `light` narrows the existing single-agent review to high-confidence findings on a cheaper model, `standard` is today's unchanged behavior, and `hard` fans out to five specialized subagents plus a judge that merges and adversarially verifies their findings.

**Architecture:** All new behavior is prompt-driven inside the single existing headless Claude Code session — `runner.py` still makes exactly one `query()` call per run, for every level. `validation.py` gets a new `validate_level`, `prompts.py`'s `build_prompt` gains a `level` parameter that selects a dispatch-instruction block, and `cli.py` wires the flag through (including defaulting `--model` to haiku for `light` when the caller didn't set one, and printing `level=` in the metrics line).

**Tech Stack:** Python 3, `claude_agent_sdk`, `argparse`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-08-19-review-levels-design.md`

## Global Constraints

- `standard` must produce byte-for-byte the same prompt text as `build_prompt` produces today — zero behavior change for existing callers who never pass `--level`.
- `_RESULT_SCHEMA` (`{success, review, failure_reason}`) is unchanged for every level — no new fields, no per-agent breakdown.
- All orchestration (fan-out, waiting for subagent reports, judging) happens inside the prompt, executed by the one existing headless session — do not add a second `query()` call or any Python-level concurrency across subagent dispatches.
- No comments in code, anywhere in this repository — standing project convention, not a default to override with judgment calls.
- Every new/changed public function keeps type hints consistent with the surrounding module's existing style (`str | None`, etc.).

---

### Task 1: `validate_level` in `validation.py`

**Files:**
- Modify: `src/code_review_cli/validation.py`
- Test: `tests/test_validation.py`

**Interfaces:**
- Produces: `validate_level(level: str | None) -> str` — returns `"standard"` when `level is None`; returns `level` unchanged when it's one of `{"light", "standard", "hard"}`; raises `ValidationError` otherwise. Later tasks (`cli.py`) call this exactly like the existing `validate_model`/`validate_provider`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_validation.py`. First, update the import block at the top of the file:

```python
import pytest

from code_review_cli.validation import (
    ValidationError,
    validate_level,
    validate_model,
    validate_pr,
    validate_provider,
    validate_repo,
)
```

Then append these test functions at the end of the file:

```python
def test_validate_level_accepts_light():
    assert validate_level("light") == "light"


def test_validate_level_accepts_standard():
    assert validate_level("standard") == "standard"


def test_validate_level_accepts_hard():
    assert validate_level("hard") == "hard"


def test_validate_level_defaults_to_standard_when_none():
    assert validate_level(None) == "standard"


def test_validate_level_rejects_unknown_value():
    with pytest.raises(ValidationError):
        validate_level("extreme")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_validation.py -v`
Expected: FAIL — `ImportError: cannot import name 'validate_level'`

- [ ] **Step 3: Implement `validate_level`**

In `src/code_review_cli/validation.py`, add near the other module-level constants (after `_MODEL_ALIASES`):

```python
VALID_LEVELS = {"light", "standard", "hard"}
```

Add the function after `validate_model`:

```python
def validate_level(level: str | None) -> str:
    if level is None:
        return "standard"
    if level not in VALID_LEVELS:
        raise ValidationError(
            f"--level must be one of {sorted(VALID_LEVELS)}, got {level!r}"
        )
    return level
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_validation.py -v`
Expected: PASS (all tests, including the five new ones)

- [ ] **Step 5: Commit**

```bash
git add src/code_review_cli/validation.py tests/test_validation.py
git commit -m "feat: add validate_level for --level light/standard/hard"
```

---

### Task 2: Level-specific dispatch instructions in `prompts.py`

**Files:**
- Modify: `src/code_review_cli/prompts.py`
- Test: `tests/test_prompts.py`

**Interfaces:**
- Consumes: nothing new from Task 1 (pure module, no cross-import).
- Produces: `build_prompt(provider: str, repo: str, pr: int, level: str = "standard") -> str`. Later tasks (`runner.py`) call this with a `level` argument threaded from `run_review`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_prompts.py`:

```python
def test_build_prompt_standard_matches_default_output():
    default_prompt = build_prompt("github", "renatoviolin/purabackend", 29)
    explicit_prompt = build_prompt(
        "github", "renatoviolin/purabackend", 29, level="standard"
    )
    assert default_prompt == explicit_prompt


def test_build_prompt_light_narrows_scope_to_single_agent():
    prompt = build_prompt("github", "renatoviolin/purabackend", 29, level="light")
    assert "voltagent-qa-sec:code-reviewer" in prompt
    assert "high-confidence" in prompt.lower()
    assert "voltagent-qa-sec:security-auditor" not in prompt


def test_build_prompt_hard_dispatches_all_five_agents_and_a_judge():
    prompt = build_prompt("github", "renatoviolin/purabackend", 29, level="hard")
    assert "voltagent-qa-sec:code-reviewer" in prompt
    assert "voltagent-qa-sec:security-auditor" in prompt
    assert "voltagent-qa-sec:performance-engineer" in prompt
    assert "voltagent-qa-sec:architect-reviewer" in prompt
    assert "voltagent-qa-sec:qa-expert" in prompt
    assert "adversarially question" in prompt.lower()
    assert "judge" in prompt.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_prompts.py -v`
Expected: FAIL — `TypeError: build_prompt() got an unexpected keyword argument 'level'` for the light/hard tests; the standard-match test errors the same way.

- [ ] **Step 3: Implement level-specific dispatch blocks**

In `src/code_review_cli/prompts.py`, replace the `_SHARED_PREAMBLE` constant and `build_prompt` function with:

```python
_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "review": {"type": "string"},
        "failure_reason": {"type": "string"},
    },
    "required": ["success", "review", "failure_reason"],
    "additionalProperties": False,
}

_SHARED_PREAMBLE = """You are running headless, with full read/write access to this \
container's filesystem, network, and installed CLI tools (git, gh, aws). Do the \
following:

1. Check out pull request #{pr} of the repository "{repo}" using the instructions below.
{dispatch_instructions}
3. Reply with a JSON object matching this exact shape:
   - On success: {{"success": true, "review": "<{review_source}>", "failure_reason": ""}}
   - On failure: {{"success": false, "review": "", "failure_reason": "<a short, \
specific explanation of what went wrong>"}}

If the named repository or pull request cannot be resolved exactly as given — it \
does not exist, the name is wrong, the PR number is wrong, or checkout fails for any \
reason — do not search for or substitute a different repository or pull request. Stop \
immediately and reply with the failure JSON shape above.

{checkout_instructions}
"""

_STANDARD_DISPATCH = """2. Once checked out, use the Agent tool to dispatch a subagent with `subagent_type` \
set to `voltagent-qa-sec:code-reviewer`. Give it a clear task description instructing \
it to review the code changes introduced by this pull request for code quality, \
security vulnerabilities, correctness bugs, and best practices, and to report back its \
complete findings. Wait for the subagent's full report before continuing."""

_LIGHT_DISPATCH = """2. Once checked out, use the Agent tool to dispatch a subagent with `subagent_type` \
set to `voltagent-qa-sec:code-reviewer`. Give it a clear task description instructing \
it to review the code changes introduced by this pull request, but to report ONLY \
high-confidence correctness bugs and security vulnerabilities — explicitly instruct it \
to skip style issues, best-practice suggestions, and any low-confidence or nit-level \
findings. Wait for the subagent's full report before continuing."""

_HARD_DISPATCH = """2. Once checked out, use the Agent tool to dispatch each of the following five \
subagents in turn, each with a clear task description instructing it to review the \
code changes introduced by this pull request from its own area of focus, and to \
report back its complete findings. Wait for each subagent's full report before \
dispatching the next:
   - `voltagent-qa-sec:code-reviewer` — code quality, security vulnerabilities, \
correctness bugs, and best practices.
   - `voltagent-qa-sec:security-auditor` — security vulnerabilities and compliance gaps.
   - `voltagent-qa-sec:performance-engineer` — performance bottlenecks in the changed code.
   - `voltagent-qa-sec:architect-reviewer` — design and architectural fit of the change.
   - `voltagent-qa-sec:qa-expert` — test coverage and quality-assurance gaps.
   Once all five reports are in hand, use the Agent tool once more to dispatch a \
final subagent (no specific `subagent_type`) as judge. Give the judge all five \
reports verbatim and instruct it to: merge overlapping or duplicate findings into \
one coherent list; for each remaining finding, adversarially question whether it is \
a genuine issue or a false positive, and drop it if it does not survive that check; \
and produce a final merged, verified report. Wait for the judge's full report before \
continuing."""

_LEVEL_INSTRUCTIONS = {
    "light": _LIGHT_DISPATCH,
    "standard": _STANDARD_DISPATCH,
    "hard": _HARD_DISPATCH,
}

_REVIEW_SOURCE = {
    "light": "the subagent's complete report, verbatim",
    "standard": "the subagent's complete report, verbatim",
    "hard": "the judge subagent's final merged and verified report, verbatim",
}

_GITHUB_CHECKOUT = """This PR is hosted on GitHub. To check it out:
1. Clone the repository: `gh repo clone {repo} ./workspace`
2. Run all subsequent commands with the working directory set to `./workspace`.
3. Check out the pull request: `gh pr checkout {pr}` (run inside `./workspace`)
"""

_CODECOMMIT_CHECKOUT = """This PR is hosted on AWS CodeCommit. To check it out:
1. Resolve the pull request's refs: `aws codecommit get-pull-request \
--pull-request-id {pr}`
2. Clone the repository via the CodeCommit git remote: `git clone codecommit://{repo} \
./workspace`
3. Run all subsequent commands with the working directory set to `./workspace`, and \
check out the source commit id reported by step 1: `git checkout <source-commit-id>` \
(run inside `./workspace`)

AWS region and credentials are already configured in this environment.
"""

_CHECKOUT_TEMPLATES = {
    "github": _GITHUB_CHECKOUT,
    "codecommit": _CODECOMMIT_CHECKOUT,
}


def build_prompt(provider: str, repo: str, pr: int, level: str = "standard") -> str:
    checkout_instructions = _CHECKOUT_TEMPLATES[provider].format(repo=repo, pr=pr)
    return _SHARED_PREAMBLE.format(
        pr=pr,
        repo=repo,
        dispatch_instructions=_LEVEL_INSTRUCTIONS[level],
        review_source=_REVIEW_SOURCE[level],
        checkout_instructions=checkout_instructions,
    )
```

Note: only `_SHARED_PREAMBLE`'s step-2 line and `build_prompt` actually change shape; `_RESULT_SCHEMA`, `_GITHUB_CHECKOUT`, `_CODECOMMIT_CHECKOUT`, and `_CHECKOUT_TEMPLATES` are reproduced above unchanged so the whole file is shown in one place — copy them verbatim if your editor is doing a partial replace instead of a full-file rewrite.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_prompts.py -v`
Expected: PASS (all tests, including the three new ones). The pre-existing tests (`test_build_prompt_includes_pr_and_repo`, `test_build_prompt_dispatches_code_reviewer_subagent_explicitly`, etc.) must still pass unchanged — they exercise the default `level="standard"` path.

- [ ] **Step 5: Commit**

```bash
git add src/code_review_cli/prompts.py tests/test_prompts.py
git commit -m "feat: add level-specific dispatch instructions to build_prompt"
```

---

### Task 3: Thread `level` through `runner.py`, raise `_MAX_TURNS`

**Files:**
- Modify: `src/code_review_cli/runner.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Consumes: `build_prompt(provider, repo, pr, level)` from Task 2.
- Produces: `run_review(provider, repo, pr, verbose=False, model=None, level="standard") -> ReviewResult`. Task 4 (`cli.py`) calls this with `level=level`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_runner.py`, right after `test_run_review_threads_model_through_to_options`:

```python
def test_run_review_threads_level_through_to_build_prompt(monkeypatch, tmp_path):
    captured = {}

    def _fake_build_prompt(provider, repo, pr, level):
        captured["level"] = level
        return "prompt text"

    async def _fake_query(prompt, options):
        yield types.SimpleNamespace(
            is_error=False,
            result="all good",
            structured_output={
                "success": True,
                "review": "all good",
                "failure_reason": "",
            },
            total_cost_usd=0.0,
            duration_ms=100,
            num_turns=1,
        )

    monkeypatch.setattr(runner_module, "build_prompt", _fake_build_prompt)
    monkeypatch.setattr(runner_module, "query", _fake_query)
    monkeypatch.setattr(
        runner_module.tempfile, "mkdtemp", lambda prefix: str(tmp_path)
    )

    runner_module.run_review("github", "org/repo", 29, level="hard")

    assert captured["level"] == "hard"


def test_run_review_defaults_level_to_standard(monkeypatch, tmp_path):
    captured = {}

    def _fake_build_prompt(provider, repo, pr, level):
        captured["level"] = level
        return "prompt text"

    async def _fake_query(prompt, options):
        yield types.SimpleNamespace(
            is_error=False,
            result="all good",
            structured_output={
                "success": True,
                "review": "all good",
                "failure_reason": "",
            },
            total_cost_usd=0.0,
            duration_ms=100,
            num_turns=1,
        )

    monkeypatch.setattr(runner_module, "build_prompt", _fake_build_prompt)
    monkeypatch.setattr(runner_module, "query", _fake_query)
    monkeypatch.setattr(
        runner_module.tempfile, "mkdtemp", lambda prefix: str(tmp_path)
    )

    runner_module.run_review("github", "org/repo", 29)

    assert captured["level"] == "standard"


def test_run_review_max_turns_raised_above_60(monkeypatch, tmp_path):
    captured = {}

    async def _fake_query(prompt, options):
        captured["options"] = options
        yield types.SimpleNamespace(
            is_error=False,
            result="all good",
            structured_output={
                "success": True,
                "review": "all good",
                "failure_reason": "",
            },
            total_cost_usd=0.0,
            duration_ms=100,
            num_turns=1,
        )

    monkeypatch.setattr(runner_module, "query", _fake_query)
    monkeypatch.setattr(
        runner_module.tempfile, "mkdtemp", lambda prefix: str(tmp_path)
    )

    runner_module.run_review("github", "org/repo", 29, level="hard")

    assert captured["options"].max_turns == 150
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_runner.py -v`
Expected: FAIL — `test_run_review_threads_level_through_to_build_prompt` and `test_run_review_defaults_level_to_standard` fail with `TypeError: run_review() got an unexpected keyword argument 'level'`; `test_run_review_max_turns_raised_above_60` fails with `assert 60 == 150`.

- [ ] **Step 3: Implement level threading and raise `_MAX_TURNS`**

In `src/code_review_cli/runner.py`, change:

```python
_MAX_TURNS = 60
```

to:

```python
_MAX_TURNS = 150
```

Change `_run_review_async`'s signature and body:

```python
async def _run_review_async(
    provider: str,
    repo: str,
    pr: int,
    verbose: bool,
    model: str | None = None,
    level: str = "standard",
) -> ReviewResult:
    try:
        workspace = Path(tempfile.mkdtemp(prefix="code-review-"))
        prompt = build_prompt(provider, repo, pr, level)
        options = ClaudeAgentOptions(
            cwd=str(workspace),
            permission_mode="bypassPermissions",
            max_turns=_MAX_TURNS,
            setting_sources=["user", "project"],
            output_format={"type": "json_schema", "schema": _RESULT_SCHEMA},
            model=model,
        )
```

(the rest of `_run_review_async`'s body is unchanged)

Change `run_review`:

```python
def run_review(
    provider: str,
    repo: str,
    pr: int,
    verbose: bool = False,
    model: str | None = None,
    level: str = "standard",
) -> ReviewResult:
    try:
        return asyncio.run(
            _run_review_async(provider, repo, pr, verbose, model, level)
        )
    except Exception as exc:
        return ReviewResult(success=False, text="", error_message=str(exc))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_runner.py -v`
Expected: PASS (all tests, including the three new ones)

- [ ] **Step 5: Commit**

```bash
git add src/code_review_cli/runner.py tests/test_runner.py
git commit -m "feat: thread level through run_review and raise max_turns for multi-agent levels"
```

---

### Task 4: `--level` CLI flag, light-mode haiku default, metrics line

**Files:**
- Modify: `src/code_review_cli/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `validate_level(level)` from Task 1, `run_review(..., level=...)` from Task 3.
- Produces: `main(argv)` behavior — `--level` flag parsed and validated before `run_review` is called (same fail-closed pattern as the other three inputs); nothing downstream of `cli.py` consumes its output.

- [ ] **Step 1: Write the failing tests**

Replace the entire contents of `tests/test_cli.py` with:

```python
import types

import code_review_cli.cli as cli_module
import code_review_cli.runner as runner_module
from code_review_cli.result import ReviewResult


def test_main_prints_review_text_and_returns_zero_on_success(monkeypatch, capsys):
    monkeypatch.setattr(
        cli_module,
        "run_review",
        lambda provider, repo, pr, verbose=False, model=None, level="standard": ReviewResult(
            success=True, text="all good"
        ),
    )

    exit_code = cli_module.main(
        ["--repo", "org/repo", "--pr", "29", "--provider", "github"]
    )

    assert exit_code == 0
    assert "all good" in capsys.readouterr().out


def test_main_prints_error_and_returns_nonzero_on_review_failure(
    monkeypatch, capsys
):
    monkeypatch.setattr(
        cli_module,
        "run_review",
        lambda provider, repo, pr, verbose=False, model=None, level="standard": ReviewResult(
            success=False, text="", error_message="timed out"
        ),
    )

    exit_code = cli_module.main(
        ["--repo", "org/repo", "--pr", "29", "--provider", "github"]
    )

    assert exit_code == 1
    assert "timed out" in capsys.readouterr().err


def test_main_prints_metrics_to_stderr_and_leaves_stdout_untouched(
    monkeypatch, capsys
):
    monkeypatch.setattr(
        cli_module,
        "run_review",
        lambda provider, repo, pr, verbose=False, model=None, level="standard": ReviewResult(
            success=True,
            text="all good",
            cost_usd=0.05,
            duration_ms=3000,
            num_turns=3,
            input_tokens=1500,
            output_tokens=300,
            cache_read_tokens=7000,
            cache_creation_tokens=400,
        ),
    )

    exit_code = cli_module.main(
        ["--repo", "org/repo", "--pr", "29", "--provider", "github"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "cost=$" in captured.err
    assert "input_tokens=1500" in captured.err
    assert "output_tokens=300" in captured.err
    assert "cache_read_tokens=7000" in captured.err
    assert "cache_creation_tokens=400" in captured.err
    assert captured.out.strip() == "all good"


def test_main_rejects_invalid_provider_without_invoking_claude(monkeypatch, capsys):
    called = False

    def _fail_if_called(provider, repo, pr, verbose=False, model=None, level="standard"):
        nonlocal called
        called = True
        return ReviewResult(success=True, text="should not happen")

    monkeypatch.setattr(cli_module, "run_review", _fail_if_called)

    exit_code = cli_module.main(
        ["--repo", "org/repo", "--pr", "29", "--provider", "bitbucket"]
    )

    assert exit_code == 2
    assert called is False
    assert "provider" in capsys.readouterr().err.lower()


def test_main_rejects_invalid_pr_without_invoking_claude(monkeypatch, capsys):
    called = False

    def _fail_if_called(provider, repo, pr, verbose=False, model=None, level="standard"):
        nonlocal called
        called = True
        return ReviewResult(success=True, text="should not happen")

    monkeypatch.setattr(cli_module, "run_review", _fail_if_called)

    exit_code = cli_module.main(
        ["--repo", "org/repo", "--pr", "abc", "--provider", "github"]
    )

    assert exit_code == 2
    assert called is False
    assert "pr" in capsys.readouterr().err.lower()


def test_main_rejects_invalid_repo_without_invoking_claude(monkeypatch, capsys):
    called = False

    def _fail_if_called(provider, repo, pr, verbose=False, model=None, level="standard"):
        nonlocal called
        called = True
        return ReviewResult(success=True, text="should not happen")

    monkeypatch.setattr(cli_module, "run_review", _fail_if_called)

    exit_code = cli_module.main(
        ["--repo", "not a valid repo!!", "--pr", "29", "--provider", "github"]
    )

    assert exit_code == 2
    assert called is False
    assert "repo" in capsys.readouterr().err.lower()


def test_main_end_to_end_success_through_faked_sdk_query(monkeypatch, capsys, tmp_path):
    final_message = types.SimpleNamespace(
        is_error=False,
        result="No issues found.",
        structured_output={
            "success": True,
            "review": "No issues found.",
            "failure_reason": "",
        },
        total_cost_usd=0.01,
        duration_ms=1000,
        num_turns=2,
    )

    async def _fake_query(prompt, options):
        yield final_message

    monkeypatch.setattr(runner_module, "query", _fake_query)
    monkeypatch.setattr(
        runner_module.tempfile, "mkdtemp", lambda prefix: str(tmp_path)
    )

    exit_code = cli_module.main(
        ["--repo", "org/repo", "--pr", "29", "--provider", "github"]
    )

    assert exit_code == 0
    assert "No issues found." in capsys.readouterr().out


def test_main_threads_verbose_flag_through_to_run_review(monkeypatch, capsys):
    captured = {}

    def _fake_run_review(provider, repo, pr, verbose=False, model=None, level="standard"):
        captured["verbose"] = verbose
        return ReviewResult(success=True, text="all good")

    monkeypatch.setattr(cli_module, "run_review", _fake_run_review)

    exit_code = cli_module.main(
        ["--repo", "org/repo", "--pr", "29", "--provider", "github", "--verbose"]
    )

    assert exit_code == 0
    assert captured["verbose"] is True


def test_main_defaults_verbose_to_false_when_flag_is_not_given(monkeypatch, capsys):
    captured = {}

    def _fake_run_review(provider, repo, pr, verbose=False, model=None, level="standard"):
        captured["verbose"] = verbose
        return ReviewResult(success=True, text="all good")

    monkeypatch.setattr(cli_module, "run_review", _fake_run_review)

    exit_code = cli_module.main(
        ["--repo", "org/repo", "--pr", "29", "--provider", "github"]
    )

    assert exit_code == 0
    assert captured["verbose"] is False


def test_main_threads_resolved_model_through_to_run_review(monkeypatch, capsys):
    captured = {}

    def _fake_run_review(provider, repo, pr, verbose=False, model=None, level="standard"):
        captured["model"] = model
        return ReviewResult(success=True, text="all good")

    monkeypatch.setattr(cli_module, "run_review", _fake_run_review)

    exit_code = cli_module.main(
        ["--repo", "org/repo", "--pr", "29", "--provider", "github", "--model", "opus"]
    )

    assert exit_code == 0
    assert captured["model"] == "claude-opus-5"


def test_main_defaults_model_to_none_when_flag_is_not_given(monkeypatch, capsys):
    captured = {}

    def _fake_run_review(provider, repo, pr, verbose=False, model=None, level="standard"):
        captured["model"] = model
        return ReviewResult(success=True, text="all good")

    monkeypatch.setattr(cli_module, "run_review", _fake_run_review)

    exit_code = cli_module.main(
        ["--repo", "org/repo", "--pr", "29", "--provider", "github"]
    )

    assert exit_code == 0
    assert captured["model"] is None


def test_main_rejects_invalid_model_without_invoking_claude(monkeypatch, capsys):
    called = False

    def _fail_if_called(provider, repo, pr, verbose=False, model=None, level="standard"):
        nonlocal called
        called = True
        return ReviewResult(success=True, text="should not happen")

    monkeypatch.setattr(cli_module, "run_review", _fail_if_called)

    exit_code = cli_module.main(
        [
            "--repo",
            "org/repo",
            "--pr",
            "29",
            "--provider",
            "github",
            "--model",
            "gpt4",
        ]
    )

    assert exit_code == 2
    assert called is False
    assert "model" in capsys.readouterr().err.lower()


def test_main_rejects_invalid_level_without_invoking_claude(monkeypatch, capsys):
    called = False

    def _fail_if_called(provider, repo, pr, verbose=False, model=None, level="standard"):
        nonlocal called
        called = True
        return ReviewResult(success=True, text="should not happen")

    monkeypatch.setattr(cli_module, "run_review", _fail_if_called)

    exit_code = cli_module.main(
        [
            "--repo",
            "org/repo",
            "--pr",
            "29",
            "--provider",
            "github",
            "--level",
            "extreme",
        ]
    )

    assert exit_code == 2
    assert called is False
    assert "level" in capsys.readouterr().err.lower()


def test_main_threads_level_through_to_run_review(monkeypatch, capsys):
    captured = {}

    def _fake_run_review(provider, repo, pr, verbose=False, model=None, level="standard"):
        captured["level"] = level
        return ReviewResult(success=True, text="all good")

    monkeypatch.setattr(cli_module, "run_review", _fake_run_review)

    exit_code = cli_module.main(
        ["--repo", "org/repo", "--pr", "29", "--provider", "github", "--level", "hard"]
    )

    assert exit_code == 0
    assert captured["level"] == "hard"


def test_main_defaults_level_to_standard_when_flag_is_not_given(monkeypatch, capsys):
    captured = {}

    def _fake_run_review(provider, repo, pr, verbose=False, model=None, level="standard"):
        captured["level"] = level
        return ReviewResult(success=True, text="all good")

    monkeypatch.setattr(cli_module, "run_review", _fake_run_review)

    exit_code = cli_module.main(
        ["--repo", "org/repo", "--pr", "29", "--provider", "github"]
    )

    assert exit_code == 0
    assert captured["level"] == "standard"


def test_main_defaults_model_to_haiku_for_light_level_when_model_not_given(
    monkeypatch, capsys
):
    captured = {}

    def _fake_run_review(provider, repo, pr, verbose=False, model=None, level="standard"):
        captured["model"] = model
        return ReviewResult(success=True, text="all good")

    monkeypatch.setattr(cli_module, "run_review", _fake_run_review)

    exit_code = cli_module.main(
        ["--repo", "org/repo", "--pr", "29", "--provider", "github", "--level", "light"]
    )

    assert exit_code == 0
    assert captured["model"] == "claude-haiku-4-5"


def test_main_does_not_override_explicit_model_for_light_level(monkeypatch, capsys):
    captured = {}

    def _fake_run_review(provider, repo, pr, verbose=False, model=None, level="standard"):
        captured["model"] = model
        return ReviewResult(success=True, text="all good")

    monkeypatch.setattr(cli_module, "run_review", _fake_run_review)

    exit_code = cli_module.main(
        [
            "--repo",
            "org/repo",
            "--pr",
            "29",
            "--provider",
            "github",
            "--level",
            "light",
            "--model",
            "opus",
        ]
    )

    assert exit_code == 0
    assert captured["model"] == "claude-opus-5"


def test_main_does_not_default_model_to_haiku_for_standard_level(monkeypatch, capsys):
    captured = {}

    def _fake_run_review(provider, repo, pr, verbose=False, model=None, level="standard"):
        captured["model"] = model
        return ReviewResult(success=True, text="all good")

    monkeypatch.setattr(cli_module, "run_review", _fake_run_review)

    exit_code = cli_module.main(
        ["--repo", "org/repo", "--pr", "29", "--provider", "github"]
    )

    assert exit_code == 0
    assert captured["model"] is None


def test_main_prints_level_in_metrics_line(monkeypatch, capsys):
    monkeypatch.setattr(
        cli_module,
        "run_review",
        lambda provider, repo, pr, verbose=False, model=None, level="standard": ReviewResult(
            success=True, text="all good"
        ),
    )

    exit_code = cli_module.main(
        ["--repo", "org/repo", "--pr", "29", "--provider", "github", "--level", "hard"]
    )

    assert exit_code == 0
    assert "level=hard" in capsys.readouterr().err
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: pre-existing tests (fakes updated with an unused `level="standard"` default) still PASS. The five new tests FAIL — `--level` isn't a recognized argument yet (`error: unrecognized arguments: --level ...`), and `test_main_prints_level_in_metrics_line` fails because `"level=hard"` never appears in stderr.

- [ ] **Step 3: Implement the `--level` flag, light-mode default, and metrics line**

Replace the entire contents of `src/code_review_cli/cli.py` with:

```python
import argparse
import sys

from .result import ReviewResult
from .runner import run_review
from .validation import (
    ValidationError,
    validate_level,
    validate_model,
    validate_pr,
    validate_provider,
    validate_repo,
)


def _print_metrics(result: ReviewResult, level: str) -> None:
    parts = [f"level={level}"]
    if result.cost_usd is not None:
        parts.append(f"cost=${result.cost_usd:.4f}")
    if result.duration_ms is not None:
        parts.append(f"duration={result.duration_ms}ms")
    if result.num_turns is not None:
        parts.append(f"turns={result.num_turns}")
    if result.input_tokens is not None:
        parts.append(f"input_tokens={result.input_tokens}")
    if result.output_tokens is not None:
        parts.append(f"output_tokens={result.output_tokens}")
    if result.cache_read_tokens is not None:
        parts.append(f"cache_read_tokens={result.cache_read_tokens}")
    if result.cache_creation_tokens is not None:
        parts.append(f"cache_creation_tokens={result.cache_creation_tokens}")
    print(f"[metrics] {' '.join(parts)}", file=sys.stderr)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="code-review",
        description="Run a headless Claude Code review against a pull request.",
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("--level", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        provider = validate_provider(args.provider)
        pr = validate_pr(args.pr)
        repo = validate_repo(provider, args.repo)
        model = validate_model(args.model)
        level = validate_level(args.level)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if level == "light" and model is None:
        model = validate_model("haiku")

    result: ReviewResult = run_review(
        provider, repo, pr, verbose=args.verbose, model=model, level=level
    )
    _print_metrics(result, level)

    if result.success:
        print(result.text)
        return 0

    print(f"error: {result.error_message}", file=sys.stderr)
    return result.exit_code()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (all tests, including the five new ones)

- [ ] **Step 5: Run the full suite**

Run: `pytest tests/ -v`
Expected: PASS — every test file (`test_validation.py`, `test_prompts.py`, `test_runner.py`, `test_cli.py`, `test_result.py`) passes.

- [ ] **Step 6: Commit**

```bash
git add src/code_review_cli/cli.py tests/test_cli.py
git commit -m "feat: add --level flag with light/standard/hard review tiers"
```

---

## Self-Review Notes

- **Spec coverage:** `validate_level` (Task 1) → goal "a `--level` flag ... validated before Claude Code is ever invoked". `standard` byte-identical output (Task 2, `test_build_prompt_standard_matches_default_output`) → goal "byte-for-byte today's behavior". `light` narrowed scope + haiku default (Task 2 + Task 4) → goal "single `code-reviewer` dispatch ... defaults `--model` to haiku". `hard` five-agent fan-out + judge (Task 2) → goal "fans out to five specialized subagents ... adversarially re-questions". Single `query()` call preserved, `_MAX_TURNS` raised (Task 3) → goal "orchestration ... happens inside the single headless Claude Code session". Metrics `level=` line (Task 4) → not an explicit goal bullet but called out in the spec's CLI interface section.
- **Placeholder scan:** none found — every step shows complete, runnable code.
- **Type consistency:** `level: str = "standard"` is consistent across `build_prompt` (Task 2), `_run_review_async`/`run_review` (Task 3), and every fake in `test_cli.py`/`test_runner.py` (Task 4). `validate_level(level: str | None) -> str` (Task 1) matches how `cli.py` calls it (Task 4: `validate_level(args.level)`, where `args.level` is `str | None` from `argparse`'s `default=None`).
