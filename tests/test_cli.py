import types

import code_review_cli.cli as cli_module
import code_review_cli.runner as runner_module
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


def test_main_rejects_invalid_pr_without_invoking_claude(monkeypatch, capsys):
    called = False

    def _fail_if_called(provider, repo, pr):
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

    def _fail_if_called(provider, repo, pr):
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
