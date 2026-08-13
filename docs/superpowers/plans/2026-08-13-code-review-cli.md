# Headless Code-Review CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a thin CLI (`code-review.py --repo <repo> --pr <N> --provider <github|codecommit>`) that invokes headless Claude Code, via the Claude Agent SDK, to review a pull request using Claude Code's own existing `/code-review` skill — and relays the result back to whoever ran the command.

**Architecture:** A small Python package with one responsibility per module: validate CLI input, build the prompt Claude receives (a shared preamble plus a provider-specific checkout fragment), invoke headless Claude Code in an isolated per-run workspace via the Claude Agent SDK, and map the SDK's result into a plain success/failure report. Claude Code — not the wrapper — performs the actual `git`/`gh`/`aws` checkout, using its own tool access inside the container.

**Tech Stack:** Python 3.11+, `claude-agent-sdk` (Python), `pytest`, standard library only otherwise (`argparse`, `tempfile`, `dataclasses`, `asyncio`).

## Global Constraints

- CLI accepts exactly three required arguments: `--repo`, `--pr`, `--provider` (enum: `github`, `codecommit`). No other target modes (branch/diff/path) in this plan.
- All three inputs are validated and rejected with a clear error, before any Claude Code invocation, if malformed — no wrapper-constructed prompt is ever sent on invalid input.
- Claude Code performs the PR checkout itself (via its own Bash tool calls, `gh`/`git`/`aws`) inside the container. The wrapper never runs git/gh/aws commands directly.
- Credentials (`ANTHROPIC_API_KEY`, git/gh/aws auth, AWS region) are pre-provisioned in the container. The wrapper never reads, validates, or references them.
- Skill content is out of scope: the wrapper references the existing `/code-review` skill **by name only**. No SKILL.md authoring happens in this plan.
- No CI/webhook triggering, no SCM PR-comment posting, no structured/JSON output, no secrets/PII redaction in this plan — all explicitly deferred to future work.
- Output in this plan is plain text to stdout plus a process exit code. The internal result object is structured (cost, duration, turn count, error flag) so a later JSON/gating feature is a new consumer of that object, not a rework.
- Each run uses a fresh temporary workspace; deleted on success, left in place on failure for post-mortem debugging (inside the container only).
- The **container itself is long-lived and shared across CLI invocations** — only the per-run temp workspace is isolated per run. `bypassPermissions` therefore grants trust per-run, not per-container-lifetime; a shared, long-lived container is why leftover failed-run workspaces and prompt-injection hardening (both explicitly deferred here) matter more before this sits behind any future CI/webhook trigger.

---

## File Structure

```
src/
  code_review_cli/
    __init__.py
    validation.py    # CLI input validation
    prompts.py       # shared preamble + per-provider checkout fragments
    result.py        # ReviewResult dataclass + exit-code mapping
    runner.py        # per-run workspace lifecycle + Claude Agent SDK invocation
    cli.py           # argparse entrypoint wiring everything together
tests/
  test_validation.py
  test_prompts.py
  test_result.py
  test_runner.py
  test_cli.py
pyproject.toml
README.md
```

**Note:** the package lives under `src/` (src layout). `pyproject.toml` must declare
`[build-system]` (setuptools>=68, `setuptools.build_meta`) and
`[tool.setuptools.packages.find]` with `where = ["src"]` so `pip install -e .` and
pytest resolve `code_review_cli` correctly. The importable package name is always
`code_review_cli` regardless of its physical path under `src/`.

---

### Task 1: Input validation + project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/code_review_cli/__init__.py`
- Create: `src/code_review_cli/validation.py`
- Test: `tests/test_validation.py`

**Interfaces:**
- Produces: `ValidationError(ValueError)`, `validate_provider(provider: str) -> str`, `validate_pr(pr: str) -> int`, `validate_repo(provider: str, repo: str) -> str`.

- [ ] **Step 1: Create the project scaffold**

`pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "code-review-cli"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`.gitignore`:

```
__pycache__/
*.pyc
.venv/
*.egg-info/
build/
dist/
.pytest_cache/
```

`src/code_review_cli/__init__.py`:

```python
```

- [ ] **Step 2: Write the failing tests**

`tests/test_validation.py`:

```python
import pytest

from code_review_cli.validation import (
    ValidationError,
    validate_pr,
    validate_provider,
    validate_repo,
)


def test_validate_provider_accepts_github():
    assert validate_provider("github") == "github"


def test_validate_provider_accepts_codecommit():
    assert validate_provider("codecommit") == "codecommit"


def test_validate_provider_rejects_unknown_value():
    with pytest.raises(ValidationError):
        validate_provider("bitbucket")


def test_validate_pr_accepts_positive_integer_string():
    assert validate_pr("42") == 42


def test_validate_pr_rejects_non_numeric():
    with pytest.raises(ValidationError):
        validate_pr("abc")


def test_validate_pr_rejects_zero():
    with pytest.raises(ValidationError):
        validate_pr("0")


def test_validate_pr_rejects_negative():
    with pytest.raises(ValidationError):
        validate_pr("-5")


def test_validate_repo_accepts_github_owner_slash_repo():
    assert validate_repo("github", "renatoviolin/purabackend") == "renatoviolin/purabackend"


def test_validate_repo_accepts_github_full_url_form():
    repo = "github.com/renatoviolin/purabackend"
    assert validate_repo("github", repo) == repo


def test_validate_repo_rejects_malformed_github_repo():
    with pytest.raises(ValidationError):
        validate_repo("github", "not a repo; rm -rf /")


def test_validate_repo_accepts_codecommit_repo_name():
    assert validate_repo("codecommit", "pura-backend") == "pura-backend"


def test_validate_repo_rejects_codecommit_repo_with_slash():
    with pytest.raises(ValidationError):
        validate_repo("codecommit", "org/pura-backend")


def test_validate_repo_rejects_trailing_newline():
    with pytest.raises(ValidationError):
        validate_repo("github", "renatoviolin/purabackend\n")


def test_validate_repo_rejects_github_leading_dash_segment():
    with pytest.raises(ValidationError):
        validate_repo("github", "--foo/--bar")


def test_validate_repo_rejects_codecommit_leading_dash():
    with pytest.raises(ValidationError):
        validate_repo("codecommit", "--profile")


def test_validate_repo_rejects_unrecognized_provider():
    with pytest.raises(ValidationError):
        validate_repo("bitbucket", "org/repo")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_validation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'code_review_cli.validation'`

- [ ] **Step 4: Write the implementation**

`code_review_cli/validation.py`:

```python
import re

VALID_PROVIDERS = {"github", "codecommit"}

_SEGMENT = r"[A-Za-z0-9_][\w.-]*"
_GITHUB_REPO_RE = re.compile(rf"^(github\.com/)?{_SEGMENT}/{_SEGMENT}$")
_CODECOMMIT_REPO_RE = re.compile(rf"^{_SEGMENT}$")


class ValidationError(ValueError):
    """Raised when a CLI input fails validation before Claude Code is invoked."""


def validate_provider(provider: str) -> str:
    if provider not in VALID_PROVIDERS:
        raise ValidationError(
            f"--provider must be one of {sorted(VALID_PROVIDERS)}, got {provider!r}"
        )
    return provider


def validate_pr(pr: str) -> int:
    try:
        value = int(pr)
    except ValueError as exc:
        raise ValidationError(f"--pr must be an integer, got {pr!r}") from exc
    if value <= 0:
        raise ValidationError(f"--pr must be a positive integer, got {value}")
    return value


_REPO_PATTERNS = {
    "github": _GITHUB_REPO_RE,
    "codecommit": _CODECOMMIT_REPO_RE,
}


def validate_repo(provider: str, repo: str) -> str:
    pattern = _REPO_PATTERNS.get(provider)
    if pattern is None:
        raise ValidationError(
            f"--repo cannot be validated: unrecognized provider {provider!r}"
        )
    if not pattern.fullmatch(repo):
        raise ValidationError(
            f"--repo {repo!r} is not a valid {provider} repository identifier"
        )
    return repo
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_validation.py -v`
Expected: PASS (16 passed)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore src/code_review_cli/__init__.py src/code_review_cli/validation.py tests/test_validation.py
git commit -m "feat: add CLI input validation for repo/pr/provider"
```

---

### Task 2: Prompt construction

**Files:**
- Create: `src/code_review_cli/prompts.py`
- Test: `tests/test_prompts.py`

**Interfaces:**
- Consumes: nothing from Task 1 (pure string templating, takes already-validated values).
- Produces: `build_prompt(provider: str, repo: str, pr: int) -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_prompts.py`:

```python
from code_review_cli.prompts import build_prompt


def test_build_prompt_includes_pr_and_repo():
    prompt = build_prompt("github", "renatoviolin/purabackend", 29)
    assert "renatoviolin/purabackend" in prompt
    assert "29" in prompt


def test_build_prompt_invokes_code_review_skill_explicitly():
    prompt = build_prompt("github", "renatoviolin/purabackend", 29)
    assert "/code-review" in prompt


def test_build_prompt_github_uses_gh_pr_checkout():
    prompt = build_prompt("github", "renatoviolin/purabackend", 29)
    assert "gh pr checkout 29" in prompt


def test_build_prompt_codecommit_uses_aws_codecommit():
    prompt = build_prompt("codecommit", "pura-backend", 7)
    assert "aws codecommit get-pull-request" in prompt
    assert "pull-request-id 7" in prompt


def test_build_prompt_states_final_message_is_the_deliverable():
    prompt = build_prompt("github", "renatoviolin/purabackend", 29)
    assert "final message" in prompt.lower()


def test_build_prompt_pins_an_explicit_effort_level():
    prompt = build_prompt("github", "renatoviolin/purabackend", 29)
    assert "effort level `medium`" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_prompts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'code_review_cli.prompts'`

- [ ] **Step 3: Write the implementation**

`src/code_review_cli/prompts.py`:

```python
_SHARED_PREAMBLE = """You are running headless, with full read/write access to this \
container's filesystem, network, and installed CLI tools (git, gh, aws). Do the \
following:

1. Check out pull request #{pr} of the repository "{repo}" using the instructions below.
2. Once checked out, run `/code-review` explicitly against the current diff, at \
effort level `medium`. Do not omit the target or the effort level — this is a fresh \
headless session with no prior invocation to inherit a default from.
3. Your final message must be the complete code review produced by that skill, and \
nothing else — it will be shown to a user verbatim.

{checkout_instructions}
"""

_GITHUB_CHECKOUT = """This PR is hosted on GitHub. To check it out:
1. Clone the repository: `gh repo clone {repo} ./workspace`
2. Enter the cloned directory: `cd ./workspace`
3. Check out the pull request: `gh pr checkout {pr}`
"""

_CODECOMMIT_CHECKOUT = """This PR is hosted on AWS CodeCommit. To check it out:
1. Resolve the pull request's refs: `aws codecommit get-pull-request \
--pull-request-id {pr}`
2. Clone the repository via the CodeCommit git remote: `git clone codecommit://{repo} \
./workspace`
3. Enter the cloned directory and check out the source commit id reported by step 1: \
`cd ./workspace && git checkout <source-commit-id>`

AWS region and credentials are already configured in this environment.
"""

_CHECKOUT_TEMPLATES = {
    "github": _GITHUB_CHECKOUT,
    "codecommit": _CODECOMMIT_CHECKOUT,
}


def build_prompt(provider: str, repo: str, pr: int) -> str:
    checkout_instructions = _CHECKOUT_TEMPLATES[provider].format(repo=repo, pr=pr)
    return _SHARED_PREAMBLE.format(
        pr=pr, repo=repo, checkout_instructions=checkout_instructions
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_prompts.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/code_review_cli/prompts.py tests/test_prompts.py
git commit -m "feat: build headless review prompt from shared preamble + provider fragment"
```

---

### Task 3: Result type

**Files:**
- Create: `src/code_review_cli/result.py`
- Test: `tests/test_result.py`

**Interfaces:**
- Produces: `ReviewResult` dataclass with fields `success: bool`, `text: str`, `cost_usd: float | None`, `duration_ms: int | None`, `num_turns: int | None`, `error_message: str | None`, and method `exit_code(self) -> int`.

- [ ] **Step 1: Write the failing tests**

`tests/test_result.py`:

```python
from code_review_cli.result import ReviewResult


def test_successful_result_has_exit_code_zero():
    result = ReviewResult(success=True, text="looks good")
    assert result.exit_code() == 0


def test_failed_result_has_exit_code_one():
    result = ReviewResult(success=False, text="", error_message="boom")
    assert result.exit_code() == 1


def test_result_carries_optional_metadata():
    result = ReviewResult(
        success=True,
        text="looks good",
        cost_usd=0.12,
        duration_ms=4500,
        num_turns=6,
    )
    assert result.cost_usd == 0.12
    assert result.duration_ms == 4500
    assert result.num_turns == 6
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_result.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'code_review_cli.result'`

- [ ] **Step 3: Write the implementation**

`src/code_review_cli/result.py`:

```python
from dataclasses import dataclass


@dataclass
class ReviewResult:
    success: bool
    text: str
    cost_usd: float | None = None
    duration_ms: int | None = None
    num_turns: int | None = None
    error_message: str | None = None

    def exit_code(self) -> int:
        return 0 if self.success else 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_result.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/code_review_cli/result.py tests/test_result.py
git commit -m "feat: add ReviewResult type with exit-code mapping"
```

---

### Task 4: Headless invocation via the Claude Agent SDK

**Files:**
- Modify: `pyproject.toml` (add `claude-agent-sdk` dependency)
- Create: `src/code_review_cli/runner.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Consumes: `build_prompt(provider, repo, pr)` from Task 2; `ReviewResult` from Task 3.
- Produces: `run_review(provider: str, repo: str, pr: int) -> ReviewResult`.

**Note for the implementer:** the exact attribute names on the SDK's final message (`is_error`, `total_cost_usd`, `duration_ms`, `num_turns`, `result`) mirror the documented `claude --output-format json` schema, and `ClaudeAgentOptions`'s constructor arguments (`cwd`, `permission_mode`, `max_turns`) are assumed rather than confirmed against the installed package. If `pytest` (Step 2/4 below) fails because the installed `claude-agent-sdk` version names any of these differently, adjust `runner.py` to match — the runner deliberately duck-types on the result-message attributes (see the code comment) rather than importing the SDK's message classes, specifically so this kind of version drift only touches one file.

- [ ] **Step 1: Add the dependency**

Edit `pyproject.toml`, change:

```toml
dependencies = []
```

to:

```toml
dependencies = ["claude-agent-sdk"]
```

Run: `pip install -e .`

- [ ] **Step 2: Write the failing tests**

`tests/test_runner.py`:

```python
import types

import pytest

import code_review_cli.runner as runner_module
from code_review_cli.result import ReviewResult


def _fake_query_factory(final_message):
    async def _fake_query(prompt, options):
        yield final_message

    return _fake_query


def test_run_review_returns_success_result(monkeypatch, tmp_path):
    final_message = types.SimpleNamespace(
        is_error=False,
        result="No issues found.",
        total_cost_usd=0.05,
        duration_ms=3200,
        num_turns=4,
    )
    monkeypatch.setattr(
        runner_module, "query", _fake_query_factory(final_message)
    )
    monkeypatch.setattr(
        runner_module.tempfile, "mkdtemp", lambda prefix: str(tmp_path)
    )

    result = runner_module.run_review("github", "org/repo", 29)

    assert isinstance(result, ReviewResult)
    assert result.success is True
    assert result.text == "No issues found."
    assert result.cost_usd == 0.05
    assert result.duration_ms == 3200
    assert result.num_turns == 4


def test_run_review_returns_failure_result_when_claude_reports_error(
    monkeypatch, tmp_path
):
    final_message = types.SimpleNamespace(
        is_error=True,
        result="hit max turns before finishing",
        total_cost_usd=0.20,
        duration_ms=9000,
        num_turns=20,
    )
    monkeypatch.setattr(
        runner_module, "query", _fake_query_factory(final_message)
    )
    monkeypatch.setattr(
        runner_module.tempfile, "mkdtemp", lambda prefix: str(tmp_path)
    )

    result = runner_module.run_review("github", "org/repo", 29)

    assert result.success is False
    assert result.error_message == "hit max turns before finishing"


def test_run_review_returns_failure_result_when_no_message_is_produced(
    monkeypatch, tmp_path
):
    async def _empty_query(prompt, options):
        return
        yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(runner_module, "query", _empty_query)
    monkeypatch.setattr(
        runner_module.tempfile, "mkdtemp", lambda prefix: str(tmp_path)
    )

    result = runner_module.run_review("github", "org/repo", 29)

    assert result.success is False
    assert "no result" in result.error_message.lower()


def test_run_review_keeps_workspace_on_failure(monkeypatch, tmp_path):
    final_message = types.SimpleNamespace(
        is_error=True,
        result="boom",
        total_cost_usd=0.0,
        duration_ms=100,
        num_turns=1,
    )
    monkeypatch.setattr(
        runner_module, "query", _fake_query_factory(final_message)
    )
    monkeypatch.setattr(
        runner_module.tempfile, "mkdtemp", lambda prefix: str(tmp_path)
    )

    runner_module.run_review("github", "org/repo", 29)

    assert tmp_path.exists()


def test_run_review_removes_workspace_on_success(monkeypatch, tmp_path):
    final_message = types.SimpleNamespace(
        is_error=False,
        result="all good",
        total_cost_usd=0.0,
        duration_ms=100,
        num_turns=1,
    )
    monkeypatch.setattr(
        runner_module, "query", _fake_query_factory(final_message)
    )
    monkeypatch.setattr(
        runner_module.tempfile, "mkdtemp", lambda prefix: str(tmp_path)
    )

    runner_module.run_review("github", "org/repo", 29)

    assert not tmp_path.exists()


def test_run_review_returns_failure_result_when_workspace_creation_fails(
    monkeypatch
):
    def _boom(prefix):
        raise OSError("disk full")

    monkeypatch.setattr(runner_module.tempfile, "mkdtemp", _boom)

    result = runner_module.run_review("github", "org/repo", 29)

    assert result.success is False
    assert "disk full" in result.error_message


def test_run_review_still_succeeds_if_cleanup_fails(monkeypatch, tmp_path, capsys):
    final_message = types.SimpleNamespace(
        is_error=False,
        result="all good",
        total_cost_usd=0.0,
        duration_ms=100,
        num_turns=1,
    )
    monkeypatch.setattr(
        runner_module, "query", _fake_query_factory(final_message)
    )
    monkeypatch.setattr(
        runner_module.tempfile, "mkdtemp", lambda prefix: str(tmp_path)
    )

    def _boom(path):
        raise OSError("permission denied")

    monkeypatch.setattr(runner_module.shutil, "rmtree", _boom)

    result = runner_module.run_review("github", "org/repo", 29)

    assert result.success is True
    assert "permission denied" in capsys.readouterr().err
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'code_review_cli.runner'`

- [ ] **Step 4: Write the implementation**

`src/code_review_cli/runner.py`:

```python
import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

from .prompts import build_prompt
from .result import ReviewResult

_MAX_TURNS = 40


async def _run_review_async(provider: str, repo: str, pr: int) -> ReviewResult:
    try:
        workspace = Path(tempfile.mkdtemp(prefix="code-review-"))
        prompt = build_prompt(provider, repo, pr)
        options = ClaudeAgentOptions(
            cwd=str(workspace),
            permission_mode="bypassPermissions",
            max_turns=_MAX_TURNS,
        )

        last_message = None
        async for message in query(prompt=prompt, options=options):
            last_message = message
    except Exception as exc:
        return ReviewResult(success=False, text="", error_message=str(exc))

    if last_message is None or not hasattr(last_message, "is_error"):
        return ReviewResult(
            success=False,
            text="",
            error_message="Claude Code produced no result message",
        )

    cost_usd = getattr(last_message, "total_cost_usd", None)
    duration_ms = getattr(last_message, "duration_ms", None)
    num_turns = getattr(last_message, "num_turns", None)

    if last_message.is_error:
        return ReviewResult(
            success=False,
            text="",
            cost_usd=cost_usd,
            duration_ms=duration_ms,
            num_turns=num_turns,
            error_message=getattr(last_message, "result", None)
            or "Claude Code reported an error",
        )

    try:
        shutil.rmtree(workspace)
    except OSError as exc:
        print(
            f"warning: failed to clean up workspace {workspace}: {exc}",
            file=sys.stderr,
        )

    return ReviewResult(
        success=True,
        text=last_message.result or "",
        cost_usd=cost_usd,
        duration_ms=duration_ms,
        num_turns=num_turns,
    )


def run_review(provider: str, repo: str, pr: int) -> ReviewResult:
    return asyncio.run(_run_review_async(provider, repo, pr))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_runner.py -v`
Expected: PASS (7 passed)

If a test fails because the installed `claude-agent-sdk` uses different constructor arguments for `ClaudeAgentOptions` or different attribute names on the result message, adjust `runner.py` accordingly and re-run — this is expected verification, not a plan defect.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/code_review_cli/runner.py tests/test_runner.py
git commit -m "feat: invoke headless Claude Code via the Agent SDK in an isolated workspace"
```

---

### Task 5: CLI entrypoint

**Files:**
- Create: `src/code_review_cli/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `ValidationError`, `validate_provider`, `validate_pr`, `validate_repo` from Task 1; `run_review` from Task 4; `ReviewResult` from Task 3.
- Produces: `build_arg_parser() -> argparse.ArgumentParser`, `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:

```python
import code_review_cli.cli as cli_module
from code_review_cli.result import ReviewResult


def test_main_prints_review_text_and_returns_zero_on_success(monkeypatch, capsys):
    monkeypatch.setattr(
        cli_module,
        "run_review",
        lambda provider, repo, pr: ReviewResult(success=True, text="all good"),
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
        lambda provider, repo, pr: ReviewResult(
            success=False, text="", error_message="timed out"
        ),
    )

    exit_code = cli_module.main(
        ["--repo", "org/repo", "--pr", "29", "--provider", "github"]
    )

    assert exit_code == 1
    assert "timed out" in capsys.readouterr().err


def test_main_rejects_invalid_provider_without_invoking_claude(monkeypatch, capsys):
    called = False

    def _fail_if_called(provider, repo, pr):
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'code_review_cli.cli'`

- [ ] **Step 3: Write the implementation**

`src/code_review_cli/cli.py`:

```python
import argparse
import sys

from .result import ReviewResult
from .runner import run_review
from .validation import ValidationError, validate_pr, validate_provider, validate_repo


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="code-review",
        description="Run a headless Claude Code review against a pull request.",
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True)
    parser.add_argument("--provider", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        provider = validate_provider(args.provider)
        pr = validate_pr(args.pr)
        repo = validate_repo(provider, args.repo)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result: ReviewResult = run_review(provider, repo, pr)

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
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/code_review_cli/cli.py tests/test_cli.py
git commit -m "feat: add CLI entrypoint wiring validation, prompt, and headless invocation"
```

---

### Task 6: README and manual end-to-end verification

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: `main` from Task 5 (documents its usage).
- Produces: nothing consumed by other tasks — this is the terminal task.

- [ ] **Step 1: Write the README**

`README.md`:

```markdown
# code-review-cli

Headless code review for pull requests, powered entirely by Claude Code's own
`/code-review` skill. This CLI does not review code itself — it validates
input, builds a task prompt, and hands off to headless Claude Code, which
checks out the PR itself (via `gh`/`git`/`aws`) and runs the review.

## Requirements

- Python 3.11+
- The `claude` CLI installed and authenticated (`ANTHROPIC_API_KEY` set) in
  this environment
- `gh` authenticated (for `--provider github`) or AWS credentials/region
  configured (for `--provider codecommit`)

## Install

\`\`\`bash
pip install -e .
\`\`\`

## Usage

\`\`\`bash
python -m code_review_cli.cli --repo renatoviolin/purabackend --pr 29 --provider github
\`\`\`

On success, the review text is printed to stdout and the process exits 0.
On failure (invalid input, or Claude Code failing to complete the review),
an error is printed to stderr and the process exits non-zero (`2` for input
validation failures, `1` for a failed review run).

## Scope

This CLI intentionally does not: trigger from CI, post PR comments, produce
structured/JSON output, redact secrets/PII, or define the review skill's
actual criteria (it invokes the pre-existing `/code-review` skill by name).
These are deferred to future work.
\`\`\`
```

- [ ] **Step 2: Manually verify end-to-end against a real PR**

Run, for a real test PR on each provider:

```bash
python -m code_review_cli.cli --repo <test-repo> --pr <N> --provider github
python -m code_review_cli.cli --repo <test-repo> --pr <N> --provider codecommit
```

Confirm for each: the temp workspace is created and cleaned up on success, the
correct checkout fragment reached Claude (visible in its tool-use trace if run
with `--verbose` on the underlying SDK/CLI), the review text prints to stdout,
and the exit code is 0.

Then run once with a deliberately invalid input, e.g.:

```bash
python -m code_review_cli.cli --repo "not a repo" --pr 29 --provider github
```

Confirm the error is printed immediately (no delay from an API call) and the
process exits with code `2`.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add README covering install, usage, and scope"
```
