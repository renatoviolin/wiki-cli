import wiki_cli.cli as cli_module
from wiki_cli.skills import InstallResult


def test_cli_install_skill_calls_github_main_by_default(monkeypatch, tmp_path, capsys):
    captured = {}

    def fake_install(skill=None, target_dir=None, force=False, dry_run=False, target="all"):
        captured.update(dict(skill=skill, target_dir=target_dir, force=force, dry_run=dry_run, target=target))
        return InstallResult(success=True, message="installed wiki-remember from github", dest=str(tmp_path / ".claude/skills/wiki-remember/SKILL.md"))

    monkeypatch.setattr(cli_module, "install_skill", fake_install)
    monkeypatch.chdir(tmp_path)
    code = cli_module.main(["install-skill"])
    assert code == 0
    assert captured["skill"] is None
    assert captured["force"] is False
    assert captured["dry_run"] is False
    assert captured["target"] == "all"
    assert "installed" in capsys.readouterr().out.lower()


def test_cli_install_skill_explicit_name(monkeypatch, tmp_path):
    captured = {}

    def fake_install(skill=None, target_dir=None, force=False, dry_run=False, target="all"):
        captured["skill"] = skill
        return InstallResult(success=True, message="ok", dest="x")

    monkeypatch.setattr(cli_module, "install_skill", fake_install)
    monkeypatch.chdir(tmp_path)
    cli_module.main(["install-skill", "wiki-remember"])
    assert captured["skill"] == "wiki-remember"


def test_cli_install_skill_force_flag(monkeypatch, tmp_path):
    captured = {}

    def fake_install(skill=None, target_dir=None, force=False, dry_run=False, target="all"):
        captured["force"] = force
        return InstallResult(success=True, message="ok", dest="x")

    monkeypatch.setattr(cli_module, "install_skill", fake_install)
    monkeypatch.chdir(tmp_path)
    cli_module.main(["install-skill", "--force"])
    assert captured["force"] is True


def test_cli_install_skill_dry_run(monkeypatch, tmp_path):
    captured = {}

    def fake_install(skill=None, target_dir=None, force=False, dry_run=False, target="all"):
        captured["dry_run"] = dry_run
        return InstallResult(success=True, message="would install", dest="x")

    monkeypatch.setattr(cli_module, "install_skill", fake_install)
    monkeypatch.chdir(tmp_path)
    cli_module.main(["install-skill", "--dry-run"])
    assert captured["dry_run"] is True


def test_cli_install_skill_target_flag(monkeypatch, tmp_path):
    captured = {}

    def fake_install(skill=None, target_dir=None, force=False, dry_run=False, target="all"):
        captured["target"] = target
        return InstallResult(success=True, message="ok", dest="x")

    monkeypatch.setattr(cli_module, "install_skill", fake_install)
    monkeypatch.chdir(tmp_path)
    cli_module.main(["install-skill", "--target", "claude"])
    assert captured["target"] == "claude"
    cli_module.main(["install-skill", "--target", "copilot"])
    assert captured["target"] == "copilot"


def test_cli_install_skill_reports_error_and_exits_one(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli_module, "install_skill", lambda skill=None, target_dir=None, force=False, dry_run=False, target="all": InstallResult(success=False, error="already exists (use --force)"))
    monkeypatch.chdir(tmp_path)
    code = cli_module.main(["install-skill"])
    assert code == 1
    assert "already exists" in capsys.readouterr().err.lower()
