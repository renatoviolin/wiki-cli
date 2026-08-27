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


def test_install_github_unknown_skill_404(tmp_path, monkeypatch):
    target = tmp_path / "repo"
    target.mkdir()

    def boom(url, timeout=5):
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    result = skills.install_skill(skill="nope", target_dir=str(target))
    assert result.success is False
