import os
from pathlib import Path
import wiki_cli.skills as skills


def test_install_bundled_creates_skill_in_target(tmp_path):
    target = tmp_path / "repo"
    target.mkdir()
    result = skills.install_skill(skill="wiki-remember", target_dir=str(target), source="bundled", force=False, dry_run=False)
    assert result.success is True
    dest = target / ".claude" / "skills" / "wiki-remember" / "SKILL.md"
    assert dest.exists()
    assert dest.read_text().startswith("---")


def test_install_bundled_is_idempotent_without_force(tmp_path):
    target = tmp_path / "repo"
    target.mkdir()
    skills.install_skill(skill="wiki-remember", target_dir=str(target), source="bundled")
    result2 = skills.install_skill(skill="wiki-remember", target_dir=str(target), source="bundled", force=False)
    assert result2.success is False or "already" in (result2.message or "").lower() or result2.skipped


def test_install_bundled_force_overwrites(tmp_path):
    target = tmp_path / "repo"
    target.mkdir()
    dest = target / ".claude" / "skills" / "wiki-remember" / "SKILL.md"
    skills.install_skill(skill="wiki-remember", target_dir=str(target), source="bundled")
    dest.write_text("corrupted")
    result = skills.install_skill(skill="wiki-remember", target_dir=str(target), source="bundled", force=True)
    assert result.success is True
    assert dest.read_text().startswith("---")


def test_install_bundled_dry_run_writes_nothing(tmp_path):
    target = tmp_path / "repo"
    target.mkdir()
    result = skills.install_skill(skill="wiki-remember", target_dir=str(target), source="bundled", dry_run=True)
    assert result.success is True
    assert not (target / ".claude" / "skills" / "wiki-remember" / "SKILL.md").exists()


def test_install_unknown_skill_fails(tmp_path):
    target = tmp_path / "repo"
    target.mkdir()
    result = skills.install_skill(skill="no-such-skill", target_dir=str(target), source="bundled")
    assert result.success is False
    assert "unknown" in result.error.lower() or "not found" in result.error.lower()


def test_install_all_copies_every_bundled_skill(tmp_path):
    target = tmp_path / "repo"
    target.mkdir()
    result = skills.install_skill(skill=None, target_dir=str(target), source="bundled", all_skills=True)
    assert result.success is True
    assert (target / ".claude" / "skills" / "wiki-remember" / "SKILL.md").exists()
