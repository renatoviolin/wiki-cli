import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_SKILL = "wiki-remember"
DEFAULT_SKILLS = ["wiki-remember", "wiki-create", "wiki-update"]
_DEFAULT_REPO = "renatoviolin/wiki-cli"
_DEFAULT_REF = "main"
_CLAUDE_BASE = ".claude/skills"
_COPILOT_BASE = ".github/skills"


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


def install_skill(skill: str | None = None, target_dir: str | None = None, force: bool = False, dry_run: bool = False, target: str = "all") -> InstallResult:
    name = skill or _DEFAULT_SKILL
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        return InstallResult(success=False, error=f"invalid skill name {name!r}")
    if target not in ("claude", "copilot", "all"):
        return InstallResult(success=False, error=f"invalid target {target!r} — must be claude, copilot, or all")
    bases = []
    if target in ("claude", "all"):
        bases.append(_CLAUDE_BASE)
    if target in ("copilot", "all"):
        bases.append(_COPILOT_BASE)
    url = _github_raw_url(_DEFAULT_REPO, _DEFAULT_REF, name)
    try:
        data = _fetch_github(_DEFAULT_REPO, _DEFAULT_REF, name)
    except urllib.error.HTTPError as exc:
        return InstallResult(success=False, error=f"failed to fetch {name} from github ({exc.code} {exc.reason}) — {url}")
    except Exception as exc:
        return InstallResult(success=False, error=f"failed to fetch {name} from github: {exc} — {url}")
    root = _target_root(target_dir)
    dests = [root / base / name / "SKILL.md" for base in bases]
    dests_str = ", ".join(str(d) for d in dests)
    states = []
    for dest in dests:
        if not dest.exists():
            states.append("missing")
        elif dest.read_bytes() == data:
            states.append("up_to_date")
        else:
            states.append("differs")
    if any(s == "differs" for s in states) and not force and not dry_run:
        for dest, state in zip(dests, states):
            if state == "differs":
                return InstallResult(success=False, error=f"{dest} already exists (use --force to overwrite)", skipped=True, dest=str(dest))
    if dry_run:
        if all(s == "up_to_date" for s in states):
            return InstallResult(success=True, message=f"{dests[0]} already up to date", skipped=True, dest=str(dests[0]))
        return InstallResult(success=True, message=f"would install {name} from github {_DEFAULT_REPO}@{_DEFAULT_REF} to {dests_str}", dest=str(dests[0]))
    skipped = 0
    for dest, state in zip(dests, states):
        if state == "up_to_date" and not force:
            skipped += 1
            continue
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        except Exception as exc:
            return InstallResult(success=False, error=f"failed to write {dest}: {exc}", dest=str(dest))
    if skipped == len(dests):
        return InstallResult(success=True, message=f"{dests[0]} already up to date", skipped=True, dest=str(dests[0]))
    return InstallResult(success=True, message=f"installed {name} from github {_DEFAULT_REPO}@{_DEFAULT_REF} to {dests_str}", dest=str(dests[0]))
