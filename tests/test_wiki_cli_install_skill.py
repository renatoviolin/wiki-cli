import pytest

import wiki_cli.cli as cli_module
from wiki_cli.skills import DEFAULT_SKILLS, InstallResult


def _ok(name):
    return InstallResult(success=True, message=f"installed {name} from github", dest=f"/tmp/{name}")


def test_cli_install_skill_bare_calls_install_all_with_no_args(monkeypatch, tmp_path, capsys):
    calls = []

    def fake_install_all():
        calls.append(True)
        return [_ok(n) for n in DEFAULT_SKILLS]

    monkeypatch.setattr(cli_module, "install_all", fake_install_all)
    monkeypatch.chdir(tmp_path)
    code = cli_module.main(["install-skill"])
    assert code == 0
    assert calls == [True]
    assert "installed" in capsys.readouterr().out.lower()


def test_cli_install_skill_rejects_positional_and_old_flags():
    for argv in (
        ["install-skill", "wiki-remember"],
        ["install-skill", "--force"],
        ["install-skill", "--dry-run"],
        ["install-skill", "--target", "claude"],
    ):
        with pytest.raises(SystemExit) as exc:
            cli_module.main(argv)
        assert exc.value.code == 2


def test_cli_install_skill_reports_error_and_exits_one_but_continues(monkeypatch, tmp_path, capsys):
    def fake_install_all():
        return [
            InstallResult(success=False, error="failed to fetch wiki-remember from github (404 Not Found)"),
            _ok(DEFAULT_SKILLS[1]),
            _ok(DEFAULT_SKILLS[2]),
        ]

    monkeypatch.setattr(cli_module, "install_all", fake_install_all)
    monkeypatch.chdir(tmp_path)
    code = cli_module.main(["install-skill"])
    assert code == 1
    captured = capsys.readouterr()
    assert "404" in captured.err
    assert "installed" in captured.out.lower()
