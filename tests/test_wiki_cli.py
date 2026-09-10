import os

import pytest

import wiki_cli.cli as cli_module
from wiki_cli.lint import LintFinding


def test_main_rejects_create_mode():
    with pytest.raises(SystemExit) as exc:
        cli_module.main(["create"])

    assert exc.value.code == 2


def test_main_rejects_update_mode():
    with pytest.raises(SystemExit) as exc:
        cli_module.main(["update"])

    assert exc.value.code == 2


def test_main_rejects_generate_skills_mode():
    with pytest.raises(SystemExit) as exc:
        cli_module.main(["generate-skills"])

    assert exc.value.code == 2


def test_main_rejects_unknown_mode():
    with pytest.raises(SystemExit) as exc:
        cli_module.main(["destroy"])

    assert exc.value.code == 2


def test_main_requires_a_mode():
    with pytest.raises(SystemExit) as exc:
        cli_module.main([])

    assert exc.value.code == 2


def test_main_lint_rejects_model_flag():
    with pytest.raises(SystemExit) as exc:
        cli_module.main(["lint", "--model", "opus"])

    assert exc.value.code == 2


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
