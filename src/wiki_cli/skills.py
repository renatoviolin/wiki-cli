import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SKILLS = ["wiki-remember", "wiki-create", "wiki-update"]
_DEFAULT_REPO = "renatoviolin/wiki-cli"
_DEFAULT_REF = "main"
_REPO_BASES = (".claude/skills", ".github/skills")
_HOME_BASES = (".claude/skills", ".copilot/skills")


@dataclass
class InstallResult:
    success: bool
    message: str | None = None
    error: str | None = None
    skipped: bool = False
    dest: str | None = None


def _github_raw_url(repo: str, ref: str, skill: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{ref}/.claude/skills/{skill}/SKILL.md"


def _fetch_github(repo: str, ref: str, skill: str) -> bytes:
    url = _github_raw_url(repo, ref, skill)
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.read()


def _dests_for_skill(name: str) -> list[Path]:
    repo = Path(os.getcwd())
    home = Path(os.path.expanduser("~"))
    dests = [repo / base / name / "SKILL.md" for base in _REPO_BASES]
    dests.extend(home / base / name / "SKILL.md" for base in _HOME_BASES)
    return dests


def _install_one(name: str, data: bytes) -> InstallResult:
    dests = _dests_for_skill(name)
    dests_str = ", ".join(str(d) for d in dests)
    wrote = 0
    for dest in dests:
        try:
            current = dest.read_bytes() if dest.exists() else None
        except Exception as exc:
            return InstallResult(success=False, error=f"failed to read {dest}: {exc}", dest=str(dest))
        if current == data:
            continue
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        except Exception as exc:
            return InstallResult(success=False, error=f"failed to write {dest}: {exc}", dest=str(dest))
        wrote += 1
    if wrote == 0:
        return InstallResult(success=True, message=f"{name} already up to date", skipped=True, dest=str(dests[0]))
    return InstallResult(success=True, message=f"installed {name} from github {_DEFAULT_REPO}@{_DEFAULT_REF} to {dests_str}", dest=str(dests[0]))


def install_all() -> list[InstallResult]:
    results = []
    for name in DEFAULT_SKILLS:
        url = _github_raw_url(_DEFAULT_REPO, _DEFAULT_REF, name)
        try:
            data = _fetch_github(_DEFAULT_REPO, _DEFAULT_REF, name)
        except urllib.error.HTTPError as exc:
            results.append(InstallResult(success=False, error=f"failed to fetch {name} from github ({exc.code} {exc.reason}) — {url}"))
            continue
        except Exception as exc:
            results.append(InstallResult(success=False, error=f"failed to fetch {name} from github: {exc} — {url}"))
            continue
        results.append(_install_one(name, data))
    return results
