import urllib.error
import urllib.request
from pathlib import Path

import pytest

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


def _fake_urlopen_for(payloads, fail_names=()):
    def _open(url, timeout=5):
        for name in fail_names:
            if f"/{name}/SKILL.md" in url:
                raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        for name, data in payloads.items():
            if f"/{name}/SKILL.md" in url:
                return FakeResp(data)
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
    return _open


def _payloads():
    return {name: f"---\nname: {name}\n---\n# {name}".encode() for name in skills.DEFAULT_SKILLS}


def _all_dests(repo: Path, home: Path, name: str):
    dests = [repo / base / name / skills._SKILL_FILENAME for base in skills._REPO_BASES]
    dests.extend(home / base / name / skills._SKILL_FILENAME for base in skills._HOME_BASES)
    return dests


def _break_path_method(monkeypatch, method_name, message, marker="wiki-create"):
    real = getattr(Path, method_name)

    def _broken(self, *args, **kwargs):
        if marker in str(self):
            raise OSError(message)
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, method_name, _broken)


@pytest.fixture
def isolated_repo_home(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen_for(_payloads()))
    return repo, home


def test_install_all_writes_twelve_files(isolated_repo_home):
    repo, home = isolated_repo_home
    results = skills.install_all()
    assert [r.success for r in results] == [True, True, True]
    assert all(r.skipped is False for r in results)
    count = 0
    for name, data in _payloads().items():
        for dest in _all_dests(repo, home, name):
            assert dest.read_bytes() == data
            count += 1
    assert count == 12


def test_install_all_second_run_reports_up_to_date(isolated_repo_home):
    skills.install_all()
    results = skills.install_all()
    assert [r.success for r in results] == [True, True, True]
    assert all(r.skipped is True for r in results)
    assert all("already up to date" in r.message.lower() for r in results)


def test_install_all_overwrites_differs_without_flag(isolated_repo_home):
    repo, _ = isolated_repo_home
    stale = repo / ".claude" / "skills" / "wiki-remember" / skills._SKILL_FILENAME
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"stale content")
    results = skills.install_all()
    assert all(r.success for r in results)
    assert all(r.skipped is False for r in results)
    assert stale.read_bytes() == _payloads()["wiki-remember"]


def test_install_all_fetch_failure_fails_that_skill_only(isolated_repo_home, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen_for(_payloads(), fail_names=("wiki-remember",)))
    results = skills.install_all()
    assert results[0].success is False
    assert "404" in results[0].error
    assert [r.success for r in results[1:]] == [True, True]


def test_install_all_write_failure_fails_that_skill(isolated_repo_home, monkeypatch):
    _break_path_method(monkeypatch, "write_bytes", "disk full")
    results = skills.install_all()
    idx = skills.DEFAULT_SKILLS.index("wiki-create")
    assert results[idx].success is False
    assert "failed to write" in results[idx].error.lower()
    for i, r in enumerate(results):
        if i != idx:
            assert r.success is True


def test_install_all_read_failure_fails_that_skill(isolated_repo_home, monkeypatch):
    skills.install_all()
    _break_path_method(monkeypatch, "read_bytes", "unreadable")
    results = skills.install_all()
    idx = skills.DEFAULT_SKILLS.index("wiki-create")
    assert results[idx].success is False
    assert "failed to read" in results[idx].error.lower()
    for i, r in enumerate(results):
        if i != idx:
            assert r.success is True
