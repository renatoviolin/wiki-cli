import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_SKILL = "wiki-remember"
_DEFAULT_REPO = "renatoviolin/wiki-cli"
_DEFAULT_REF = "main"


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


def _target_root(target_dir: str | None) -> Path:
    if target_dir:
        return Path(target_dir)
    return Path(os.getcwd())


def install_skill(skill: str | None = None, target_dir: str | None = None, force: bool = False, dry_run: bool = False) -> InstallResult:
    name = skill or _DEFAULT_SKILL
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        return InstallResult(success=False, error=f"invalid skill name {name!r}")
    try:
        data = _fetch_github(_DEFAULT_REPO, _DEFAULT_REF, name)
    except urllib.error.HTTPError as exc:
        return InstallResult(success=False, error=f"failed to fetch {name} from github ({exc.code} {exc.reason}) — {_github_raw_url(_DEFAULT_REPO, _DEFAULT_REF, name)}")
    except Exception as exc:
        return InstallResult(success=False, error=f"failed to fetch {name} from github: {exc} — {_github_raw_url(_DEFAULT_REPO, _DEFAULT_REF, name)}")
    root = _target_root(target_dir)
    dest = root / ".claude" / "skills" / name / "SKILL.md"
    if dest.exists() and not force and not dry_run:
        if dest.read_bytes() == data:
            return InstallResult(success=True, message=f"{dest} already up to date", skipped=True, dest=str(dest))
        return InstallResult(success=False, error=f"{dest} already exists (use --force to overwrite)", skipped=True, dest=str(dest))
    if dry_run:
        return InstallResult(success=True, message=f"would install {name} from github {_DEFAULT_REPO}@{_DEFAULT_REF} to {dest}", dest=str(dest))
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    except Exception as exc:
        return InstallResult(success=False, error=f"failed to write {dest}: {exc}", dest=str(dest))
    return InstallResult(success=True, message=f"installed {name} from github {_DEFAULT_REPO}@{_DEFAULT_REF} to {dest}", dest=str(dest))
