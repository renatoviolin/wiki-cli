import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

_BUNDLED_ROOT = "bundled_skills"
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


def _bundled_skills_root():
    return files("wiki_cli") / _BUNDLED_ROOT


def _list_bundled_skills() -> list[str]:
    root = _bundled_skills_root()
    if not root.is_dir():
        return []
    return sorted([p.name for p in root.iterdir() if p.is_dir()])


def _read_bundled(skill: str) -> bytes | None:
    target = _bundled_skills_root() / skill / "SKILL.md"
    if not target.is_file():
        return None
    return target.read_bytes()


def _target_root(target_dir: str | None) -> Path:
    if target_dir:
        return Path(target_dir)
    return Path(os.getcwd())


def install_skill(skill: str | None = None, target_dir: str | None = None, source: str = "bundled", ref: str | None = None, repo: str | None = None, force: bool = False, dry_run: bool = False, all_skills: bool = False) -> InstallResult:
    if source not in ("bundled", "github"):
        return InstallResult(success=False, error=f"--from must be bundled or github, got {source!r}")
    if source == "github":
        return _install_from_github(skill, target_dir, ref, repo, force, dry_run, all_skills)
    skills_to_install: list[str]
    if all_skills:
        skills_to_install = _list_bundled_skills()
        if not skills_to_install:
            return InstallResult(success=False, error="no bundled skills found")
    else:
        name = skill or _DEFAULT_SKILL
        data = _read_bundled(name)
        if data is None:
            return InstallResult(success=False, error=f"unknown skill {name!r}")
        skills_to_install = [name]
    root = _target_root(target_dir)
    last_dest = None
    skipped_count = 0
    for name in skills_to_install:
        data = _read_bundled(name)
        if data is None:
            return InstallResult(success=False, error=f"unknown skill {name!r}")
        dest = root / ".claude" / "skills" / name / "SKILL.md"
        last_dest = str(dest)
        if dest.exists() and not force and not dry_run:
            existing = dest.read_bytes()
            if existing == data:
                skipped_count += 1
                continue
            return InstallResult(success=False, error=f"{dest} already exists (use --force to overwrite)", skipped=True, dest=str(dest))
        if dry_run:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    if dry_run:
        return InstallResult(success=True, message=f"would install {', '.join(skills_to_install)} to {root / '.claude' / 'skills'}", dest=last_dest)
    if skipped_count == len(skills_to_install):
        return InstallResult(success=True, message=f"{', '.join(skills_to_install)} already up to date", skipped=True, dest=last_dest)
    return InstallResult(success=True, message=f"installed {', '.join(skills_to_install)} to {root / '.claude' / 'skills'}", dest=last_dest)


def _github_raw_url(repo: str, ref: str, skill: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{ref}/.claude/skills/{skill}/SKILL.md"


def _fetch_github(repo: str, ref: str, skill: str) -> bytes:
    url = _github_raw_url(repo, ref, skill)
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.read()


def _install_from_github(skill, target_dir, ref, repo, force, dry_run, all_skills):
    repo = repo or _DEFAULT_REPO
    ref = ref or _DEFAULT_REF
    if all_skills:
        return InstallResult(success=False, error="--all not supported with --from github (specify a skill)")
    name = skill or _DEFAULT_SKILL
    try:
        data = _fetch_github(repo, ref, name)
    except urllib.error.HTTPError as exc:
        return InstallResult(success=False, error=f"failed to fetch {name} from github ({exc.code} {exc.reason}) — {_github_raw_url(repo, ref, name)}")
    except Exception as exc:
        return InstallResult(success=False, error=f"failed to fetch {name} from github: {exc}")
    root = _target_root(target_dir)
    dest = root / ".claude" / "skills" / name / "SKILL.md"
    if dest.exists() and not force and not dry_run:
        if dest.read_bytes() == data:
            return InstallResult(success=True, message=f"{dest} already up to date", skipped=True, dest=str(dest))
        return InstallResult(success=False, error=f"{dest} already exists (use --force to overwrite)", skipped=True, dest=str(dest))
    if dry_run:
        return InstallResult(success=True, message=f"would install {name} from github {repo}@{ref} to {dest}", dest=str(dest))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return InstallResult(success=True, message=f"installed {name} from github {repo}@{ref} to {dest}", dest=str(dest))
