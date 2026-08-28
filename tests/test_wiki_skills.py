import urllib.error
import urllib.request
from pathlib import Path

import wiki_cli.skills as skills


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

    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout=5: FakeResp())
    result = skills.install_skill(skill="wiki-remember", target_dir=str(target))
    assert result.success is True
    assert (target / ".claude" / "skills" / "wiki-remember" / "SKILL.md").read_bytes() == fake_bytes
    assert (target / ".github" / "skills" / "wiki-remember" / "SKILL.md").read_bytes() == fake_bytes


def test_install_github_target_claude_only(tmp_path, monkeypatch):
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

    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout=5: FakeResp())
    result = skills.install_skill(skill="wiki-remember", target_dir=str(target), target="claude")
    assert result.success is True
    assert (target / ".claude" / "skills" / "wiki-remember" / "SKILL.md").exists()
    assert not (target / ".github" / "skills" / "wiki-remember" / "SKILL.md").exists()


def test_install_github_target_copilot_only(tmp_path, monkeypatch):
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

    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout=5: FakeResp())
    result = skills.install_skill(skill="wiki-remember", target_dir=str(target), target="copilot")
    assert result.success is True
    assert (target / ".github" / "skills" / "wiki-remember" / "SKILL.md").exists()
    assert not (target / ".claude" / "skills" / "wiki-remember" / "SKILL.md").exists()


def test_install_github_404_fails(tmp_path, monkeypatch):
    target = tmp_path / "repo"
    target.mkdir()

    def boom(url, timeout=5):
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    result = skills.install_skill(skill="wiki-remember", target_dir=str(target))
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
    result = skills.install_skill(skill="wiki-remember", target_dir=str(target), dry_run=True)
    assert result.success is True
    assert not (target / ".claude" / "skills" / "wiki-remember" / "SKILL.md").exists()
    assert not (target / ".github" / "skills" / "wiki-remember" / "SKILL.md").exists()


def test_install_github_unknown_skill_404(tmp_path, monkeypatch):
    target = tmp_path / "repo"
    target.mkdir()

    def boom(url, timeout=5):
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    result = skills.install_skill(skill="nope", target_dir=str(target))
    assert result.success is False


def test_install_github_already_up_to_date(tmp_path, monkeypatch):
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

    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout=5: FakeResp())
    skills.install_skill(skill="wiki-remember", target_dir=str(target))
    result = skills.install_skill(skill="wiki-remember", target_dir=str(target))
    assert result.success is True
    assert result.skipped is True
    assert "already up to date" in result.message.lower()


def test_install_github_exists_needs_force(tmp_path, monkeypatch):
    target = tmp_path / "repo"
    target.mkdir()
    dest = target / ".claude" / "skills" / "wiki-remember" / "SKILL.md"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"old content")

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"new content"

    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout=5: FakeResp())
    result = skills.install_skill(skill="wiki-remember", target_dir=str(target))
    assert result.success is False
    assert "already exists" in result.error.lower()
    result2 = skills.install_skill(skill="wiki-remember", target_dir=str(target), force=True)
    assert result2.success is True
    assert dest.read_bytes() == b"new content"


def test_install_github_invalid_skill_name(tmp_path):
    target = tmp_path / "repo"
    target.mkdir()
    result = skills.install_skill(skill="../evil", target_dir=str(target))
    assert result.success is False
    assert "invalid" in result.error.lower()
    result2 = skills.install_skill(skill="a/b", target_dir=str(target))
    assert result2.success is False
