import os

import pytest

import wiki_cli.cli as cli_module
from wiki_cli.lint import LintFinding
from wiki_cli.result import WikiResult


def _fake(captured=None):
    sink = captured if captured is not None else {}

    def _run_wiki(mode, verbose=False, model=None):
        sink["mode"] = mode
        sink["verbose"] = verbose
        sink["model"] = model
        return WikiResult(success=True, text="wrote 3 pages")

    return _run_wiki


def test_main_create_prints_summary_and_returns_zero(monkeypatch, capsys):
    monkeypatch.setattr(cli_module, "run_wiki", _fake())

    exit_code = cli_module.main(["create"])

    assert exit_code == 0
    assert "wrote 3 pages" in capsys.readouterr().out


def test_main_threads_create_mode(monkeypatch, capsys):
    captured = {}
    monkeypatch.setattr(cli_module, "run_wiki", _fake(captured))

    cli_module.main(["create"])

    assert captured["mode"] == "create"


def test_main_threads_update_mode(monkeypatch, capsys):
    captured = {}
    monkeypatch.setattr(cli_module, "run_wiki", _fake(captured))

    cli_module.main(["update"])

    assert captured["mode"] == "update"


def test_main_rejects_unknown_mode(monkeypatch, capsys):
    called = False

    def _fail_if_called(mode, verbose=False, model=None):
        nonlocal called
        called = True
        return WikiResult(success=True, text="should not happen")

    monkeypatch.setattr(cli_module, "run_wiki", _fail_if_called)

    with pytest.raises(SystemExit) as exc:
        cli_module.main(["destroy"])

    assert exc.value.code == 2
    assert called is False


def test_main_requires_a_mode(monkeypatch):
    monkeypatch.setattr(cli_module, "run_wiki", _fake())

    with pytest.raises(SystemExit) as exc:
        cli_module.main([])

    assert exc.value.code == 2


def test_main_threads_verbose_flag(monkeypatch, capsys):
    captured = {}
    monkeypatch.setattr(cli_module, "run_wiki", _fake(captured))

    cli_module.main(["create", "--verbose"])

    assert captured["verbose"] is True


def test_main_defaults_verbose_to_false(monkeypatch, capsys):
    captured = {}
    monkeypatch.setattr(cli_module, "run_wiki", _fake(captured))

    cli_module.main(["create"])

    assert captured["verbose"] is False


def test_main_resolves_model_alias(monkeypatch, capsys):
    captured = {}
    monkeypatch.setattr(cli_module, "run_wiki", _fake(captured))

    cli_module.main(["create", "--model", "opus"])

    assert captured["model"] == "claude-opus-5"


def test_main_defaults_model_to_sonnet(monkeypatch, capsys):
    captured = {}
    monkeypatch.setattr(cli_module, "run_wiki", _fake(captured))

    cli_module.main(["create"])

    assert captured["model"] == "claude-sonnet-5"


def test_main_rejects_unknown_model(monkeypatch, capsys):
    called = False

    def _fail_if_called(mode, verbose=False, model=None):
        nonlocal called
        called = True
        return WikiResult(success=True, text="should not happen")

    monkeypatch.setattr(cli_module, "run_wiki", _fail_if_called)

    exit_code = cli_module.main(["create", "--model", "gpt4"])

    assert exit_code == 2
    assert called is False
    assert "model" in capsys.readouterr().err.lower()


def test_main_prints_error_and_returns_one_on_failure(monkeypatch, capsys):
    monkeypatch.setattr(
        cli_module,
        "run_wiki",
        lambda mode, verbose=False, model=None: WikiResult(
            success=False, text="", error_message="not a git repository"
        ),
    )

    exit_code = cli_module.main(["create"])

    assert exit_code == 1
    assert "not a git repository" in capsys.readouterr().err


def test_main_prints_metrics_to_stderr_and_pages_to_stdout(monkeypatch, capsys):
    monkeypatch.setattr(
        cli_module,
        "run_wiki",
        lambda mode, verbose=False, model=None: WikiResult(
            success=True,
            text="wrote 2 pages",
            pages_written=[".wiki/index.md", ".wiki/api.md"],
            cost_usd=0.02,
            duration_ms=1500,
            num_turns=5,
            input_tokens=900,
            output_tokens=120,
        ),
    )

    exit_code = cli_module.main(["create"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "mode=create" in captured.err
    assert "cost=$" in captured.err
    assert "input_tokens=900" in captured.err
    assert ".wiki/index.md" in captured.out
    assert "cost=$" not in captured.out


def test_main_lint_mode_does_not_invoke_run_wiki(monkeypatch, tmp_path):
    called = False

    def _fail_if_called(mode, verbose=False, model=None):
        nonlocal called
        called = True
        return WikiResult(success=True, text="should not happen")

    monkeypatch.setattr(cli_module, "run_wiki", _fail_if_called)
    monkeypatch.setattr(cli_module, "lint_wiki", lambda repo_root: [])
    monkeypatch.chdir(tmp_path)

    exit_code = cli_module.main(["lint"])

    assert called is False
    assert exit_code == 0


def test_main_lint_passes_cwd_as_repo_root(monkeypatch, tmp_path):
    captured = {}

    def _fake_lint(repo_root):
        captured["repo_root"] = repo_root
        return []

    monkeypatch.setattr(cli_module, "lint_wiki", _fake_lint)
    monkeypatch.chdir(tmp_path)

    cli_module.main(["lint"])

    assert captured["repo_root"] == os.getcwd()


def test_main_lint_reports_errors_and_returns_one(monkeypatch, capsys):
    monkeypatch.setattr(
        cli_module,
        "lint_wiki",
        lambda repo_root: [
            LintFinding(
                file=".wiki/page.md",
                line=3,
                severity="error",
                message="missing `## Sources` section",
            )
        ],
    )

    exit_code = cli_module.main(["lint"])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert ".wiki/page.md" in out
    assert "missing `## Sources` section" in out


def test_main_lint_advisory_only_returns_zero(monkeypatch, capsys):
    monkeypatch.setattr(
        cli_module,
        "lint_wiki",
        lambda repo_root: [
            LintFinding(
                file=".wiki/page.md",
                line=5,
                severity="advisory",
                message="possible stale reference",
            )
        ],
    )

    exit_code = cli_module.main(["lint"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "possible stale reference" in out


def test_main_lint_clean_wiki_prints_summary(monkeypatch, capsys):
    monkeypatch.setattr(cli_module, "lint_wiki", lambda repo_root: [])

    exit_code = cli_module.main(["lint"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "0 error" in out
