import urllib.error
import urllib.request
from pathlib import Path

import wiki_cli.skills as skills


class FakeResp:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._payload


def _fake_urlopen_for(payloads):
    def _open(url, timeout=5):
        for name, data in payloads.items():
            if f"/{name}/SKILL.md" in url:
                return FakeResp(data)
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
    return _open


def _payloads():
    return {name: f"---\nname: {name}\n---\n# {name}".encode() for name in skills.DEFAULT_SKILLS}


def _all_dests(repo: Path, home: Path, name: str):
    return [
        repo / ".claude" / "skills" / name / "SKILL.md",
        repo / ".github" / "skills" / name / "SKILL.md",
        home / ".claude" / "skills" / name / "SKILL.md",
        home / ".copilot" / "skills" / name / "SKILL.md",
    ]


def test_install_all_writes_twelve_files(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen_for(_payloads()))
    results = skills.install_all()
    assert [r.success for r in results] == [True, True, True]
    assert all(r.skipped is False for r in results)
    for name, data in _payloads().items():
        for dest in _all_dests(repo, home, name):
            assert dest.read_bytes() == data


def test_install_all_second_run_reports_up_to_date(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen_for(_payloads()))
    skills.install_all()
    results = skills.install_all()
    assert [r.success for r in results] == [True, True, True]
    assert all(r.skipped is True for r in results)
    assert all("already up to date" in r.message.lower() for r in results)


def test_install_all_overwrites_differs_without_flag(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen_for(_payloads()))
    stale = repo / ".claude" / "skills" / "wiki-remember" / "SKILL.md"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"stale content")
    results = skills.install_all()
    assert all(r.success for r in results)
    assert all(r.skipped is False for r in results)
    assert stale.read_bytes() == _payloads()["wiki-remember"]


def test_install_all_fetch_failure_fails_that_skill_only(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("HOME", str(home))

    def _open(url, timeout=5):
        if "/wiki-remember/SKILL.md" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        for name, data in _payloads().items():
            if f"/{name}/SKILL.md" in url:
                return FakeResp(data)
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

    monkeypatch.setattr(urllib.request, "urlopen", _open)
    results = skills.install_all()
    assert results[0].success is False
    assert "404" in results[0].error
    assert [r.success for r in results[1:]] == [True, True]


def test_install_all_write_failure_fails_that_skill(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen_for(_payloads()))
    real_write = Path.write_bytes

    def _flaky(self, data):
        if "wiki-create" in str(self):
            raise OSError("disk full")
        return real_write(self, data)

    monkeypatch.setattr(Path, "write_bytes", _flaky)
    results = skills.install_all()
    idx = skills.DEFAULT_SKILLS.index("wiki-create")
    assert results[idx].success is False
    assert "failed to write" in results[idx].error.lower()
    for i, r in enumerate(results):
        if i != idx:
            assert r.success is True


def test_install_all_read_failure_fails_that_skill(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen_for(_payloads()))
    skills.install_all()
    real_read = Path.read_bytes

    def _flaky_read(self):
        if "wiki-create" in str(self):
            raise OSError("unreadable")
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", _flaky_read)
    results = skills.install_all()
    idx = skills.DEFAULT_SKILLS.index("wiki-create")
    assert results[idx].success is False
    assert "failed to read" in results[idx].error.lower()
    for i, r in enumerate(results):
        if i != idx:
            assert r.success is True
