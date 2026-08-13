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
