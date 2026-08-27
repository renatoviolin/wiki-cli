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


import urllib.request
import urllib.error


def test_install_github_fetches_and_writes(tmp_path, monkeypatch):
    target = tmp_path / "repo"
    target.mkdir()
    fake_bytes = b"---\nname: wiki-remember\n---\n# fake"

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return fake_bytes

        def getcode(self):
            return 200

    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout=5: FakeResp())
    result = skills.install_skill(skill="wiki-remember", target_dir=str(target), source="github", ref="main", repo="renatoviolin/wiki-cli")
    assert result.success is True
    assert (target / ".claude" / "skills" / "wiki-remember" / "SKILL.md").read_bytes() == fake_bytes


def test_install_github_404_fails(tmp_path, monkeypatch):
    target = tmp_path / "repo"
    target.mkdir()

    def boom(url, timeout=5):
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    result = skills.install_skill(skill="wiki-remember", target_dir=str(target), source="github")
    assert result.success is False
    assert "404" in result.error or "not found" in result.error.lower()


def test_install_github_dry_run_does_not_write(tmp_path, monkeypatch):
    target = tmp_path / "repo"
    target.mkdir()

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"content"

    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout=5: FakeResp())
    result = skills.install_skill(skill="wiki-remember", target_dir=str(target), source="github", dry_run=True)
    assert result.success is True
    assert not (target / ".claude" / "skills" / "wiki-remember" / "SKILL.md").exists()


def test_install_github_unknown_skill_404(tmp_path, monkeypatch):
    target = tmp_path / "repo"
    target.mkdir()

    def boom(url, timeout=5):
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    result = skills.install_skill(skill="nope", target_dir=str(target), source="github")
    assert result.success is False
