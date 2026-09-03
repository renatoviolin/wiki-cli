import wiki_cli.cli as cli_module
from wiki_cli.skills import DEFAULT_SKILLS, InstallResult


def test_cli_install_skill_bare_installs_default_bundle(monkeypatch, tmp_path, capsys):
    calls = []

    def fake_install(skill=None, target_dir=None, force=False, dry_run=False, target="all"):
        calls.append(dict(skill=skill, target_dir=target_dir, force=force, dry_run=dry_run, target=target))
        return InstallResult(success=True, message=f"installed {skill} from github", dest=str(tmp_path / f".claude/skills/{skill}/SKILL.md"))

    monkeypatch.setattr(cli_module, "install_skill", fake_install)
    monkeypatch.chdir(tmp_path)
    code = cli_module.main(["install-skill"])
    assert code == 0
    assert [c["skill"] for c in calls] == list(DEFAULT_SKILLS)
    assert all(c["force"] is False and c["dry_run"] is False and c["target"] == "all" for c in calls)
    assert "installed" in capsys.readouterr().out.lower()


def test_cli_install_skill_explicit_name_installs_only_that_one(monkeypatch, tmp_path):
    calls = []

    def fake_install(skill=None, target_dir=None, force=False, dry_run=False, target="all"):
        calls.append(skill)
        return InstallResult(success=True, message="ok", dest="x")

    monkeypatch.setattr(cli_module, "install_skill", fake_install)
    monkeypatch.chdir(tmp_path)
    cli_module.main(["install-skill", "wiki-remember"])
    assert calls == ["wiki-remember"]


def test_cli_install_skill_force_flag_applies_to_bundle(monkeypatch, tmp_path):
    calls = []

    def fake_install(skill=None, target_dir=None, force=False, dry_run=False, target="all"):
        calls.append(force)
        return InstallResult(success=True, message="ok", dest="x")

    monkeypatch.setattr(cli_module, "install_skill", fake_install)
    monkeypatch.chdir(tmp_path)
    cli_module.main(["install-skill", "--force"])
    assert calls == [True] * len(DEFAULT_SKILLS)


def test_cli_install_skill_dry_run_applies_to_bundle(monkeypatch, tmp_path):
    calls = []

    def fake_install(skill=None, target_dir=None, force=False, dry_run=False, target="all"):
        calls.append(dry_run)
        return InstallResult(success=True, message="would install", dest="x")

    monkeypatch.setattr(cli_module, "install_skill", fake_install)
    monkeypatch.chdir(tmp_path)
    cli_module.main(["install-skill", "--dry-run"])
    assert calls == [True] * len(DEFAULT_SKILLS)


def test_cli_install_skill_target_flag_applies_to_bundle(monkeypatch, tmp_path):
    calls = []

    def fake_install(skill=None, target_dir=None, force=False, dry_run=False, target="all"):
        calls.append(target)
        return InstallResult(success=True, message="ok", dest="x")

    monkeypatch.setattr(cli_module, "install_skill", fake_install)
    monkeypatch.chdir(tmp_path)
    cli_module.main(["install-skill", "--target", "claude"])
    assert calls == ["claude"] * len(DEFAULT_SKILLS)
    calls.clear()
    cli_module.main(["install-skill", "--target", "copilot"])
    assert calls == ["copilot"] * len(DEFAULT_SKILLS)


def test_cli_install_skill_reports_error_and_exits_one_but_continues_bundle(monkeypatch, tmp_path, capsys):
    calls = []

    def fake_install(skill=None, target_dir=None, force=False, dry_run=False, target="all"):
        calls.append(skill)
        if skill == DEFAULT_SKILLS[0]:
            return InstallResult(success=False, error="already exists (use --force)")
        return InstallResult(success=True, message=f"installed {skill}", dest="x")

    monkeypatch.setattr(cli_module, "install_skill", fake_install)
    monkeypatch.chdir(tmp_path)
    code = cli_module.main(["install-skill"])
    assert code == 1
    assert calls == list(DEFAULT_SKILLS)
    assert "already exists" in capsys.readouterr().err.lower()
