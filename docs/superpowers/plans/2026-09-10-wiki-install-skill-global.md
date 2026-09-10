# `wiki install-skill` installs everywhere with no parameters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make bare `wiki install-skill` install the three wiki skills to the checkout and the home directory with no flags.

**Architecture:** Collapse `skills.py` to a fixed bundle + fixed four roots with byte-compare sync, strip `cli.py` to a bare subcommand, rewrite the two install-skill test files first, then update docs and bump `0.3.0` to `0.4.0`.

**Tech Stack:** Python 3.11+ stdlib only (`argparse`, `urllib`, `pathlib`), pytest.

---

## File map

| File | Change |
|---|---|
| `src/wiki_cli/skills.py` | Rewrite: drop all parameters, add `install_all()` over 4 fixed roots with sync policy |
| `src/wiki_cli/cli.py` | Modify: bare `install-skill` subparser, delegate to `install_all()` |
| `tests/test_wiki_skills.py` | Rewrite: 5 tests against `install_all()` with `HOME` redirected |
| `tests/test_wiki_cli_install_skill.py` | Rewrite: 3 tests for bare invocation, old-flag rejection, error passthrough |
| `tests/test_wiki_cli.py` | No change: contains no `install-skill` cases (verified by grep in Task 2) |
| `README.md:147-173` | Replace install-skill section with bare everywhere behavior |
| `CLAUDE.md:14,50,52` | Update three `install-skill` descriptions |
| `CHANGELOG.md` | New `0.4.0` entry on top |
| `pyproject.toml:7` | `0.3.0` to `0.4.0` |

---

### Task 1: `skills.py` — fixed bundle, four roots, sync policy

**Files:**
- Modify: `src/wiki_cli/skills.py` (full rewrite, 90 lines to ~75)
- Test: `tests/test_wiki_skills.py` (full rewrite)

- [ ] **Step 1: Confirm the only `install_skill` importers are `cli.py` and the tests**

Run: `rg -n "install_skill|DEFAULT_SKILL" src tests`
Expected: matches only in `src/wiki_cli/skills.py`, `src/wiki_cli/cli.py`, `tests/test_wiki_skills.py`, `tests/test_wiki_cli_install_skill.py`

- [ ] **Step 2: Write the failing tests**

Write `tests/test_wiki_skills.py` in full:

```python
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
```

- [ ] **Step 3: Run the new tests to verify they fail**

Run: `pytest tests/test_wiki_skills.py -v`
Expected: FAIL with `AttributeError: module 'wiki_cli.skills' has no attribute 'install_all'`

- [ ] **Step 4: Write the new implementation**

Write `src/wiki_cli/skills.py` in full:

```python
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
        if dest.exists() and dest.read_bytes() == data:
            continue
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        except Exception as exc:
            return InstallResult(success=False, error=f"failed to write {dest}: {exc}", dest=str(dest))
        wrote += 1
    if wrote == 0:
        return InstallResult(success=True, message=f"{name} already up to date (4/4)", skipped=True, dest=str(dests[0]))
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_wiki_skills.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add src/wiki_cli/skills.py tests/test_wiki_skills.py
git commit -m "feat: install wiki skills to checkout and home with no flags"
```

---

### Task 2: `cli.py` — bare `install-skill` subcommand

**Files:**
- Modify: `src/wiki_cli/cli.py`
- Test: `tests/test_wiki_cli_install_skill.py` (full rewrite)

- [ ] **Step 1: Write the failing tests**

Write `tests/test_wiki_cli_install_skill.py` in full:

```python
import pytest

import wiki_cli.cli as cli_module
from wiki_cli.skills import DEFAULT_SKILLS, InstallResult


def _ok(name):
    return InstallResult(success=True, message=f"installed {name} from github", dest=f"/tmp/{name}")


def test_cli_install_skill_bare_calls_install_all_with_no_args(monkeypatch, tmp_path, capsys):
    calls = []

    def fake_install_all():
        calls.append(True)
        return [_ok(n) for n in DEFAULT_SKILLS]

    monkeypatch.setattr(cli_module, "install_all", fake_install_all)
    monkeypatch.chdir(tmp_path)
    code = cli_module.main(["install-skill"])
    assert code == 0
    assert calls == [True]
    assert "installed" in capsys.readouterr().out.lower()


def test_cli_install_skill_rejects_positional_and_old_flags():
    for argv in (
        ["install-skill", "wiki-remember"],
        ["install-skill", "--force"],
        ["install-skill", "--dry-run"],
        ["install-skill", "--target", "claude"],
    ):
        with pytest.raises(SystemExit) as exc:
            cli_module.main(argv)
        assert exc.value.code == 2


def test_cli_install_skill_reports_error_and_exits_one_but_continues(monkeypatch, tmp_path, capsys):
    def fake_install_all():
        return [
            InstallResult(success=False, error="failed to fetch wiki-remember from github (404 Not Found)"),
            _ok(DEFAULT_SKILLS[1]),
            _ok(DEFAULT_SKILLS[2]),
        ]

    monkeypatch.setattr(cli_module, "install_all", fake_install_all)
    monkeypatch.chdir(tmp_path)
    code = cli_module.main(["install-skill"])
    assert code == 1
    captured = capsys.readouterr()
    assert "404" in captured.err
    assert "installed" in captured.out.lower()
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `pytest tests/test_wiki_cli_install_skill.py -v`
Expected: FAIL with `AttributeError` on `install_all` (cli still imports `install_skill`)

- [ ] **Step 3: Write the bare subcommand**

Write `src/wiki_cli/cli.py` in full:

```python
import argparse
import os
import sys

from .lint import LintFinding, lint_wiki
from .skills import install_all


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wiki",
        description="Local helpers for the .wiki knowledge base: mechanical lint checks and skill installation. Wiki content itself is written by the wiki-create, wiki-update, and wiki-remember skills.",
    )
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("lint", help="mechanical checks over .wiki on disk")
    sub.add_parser("install-skill", help="install wiki skills (wiki-remember, wiki-create, wiki-update) to this checkout and your home directory from github main")
    return parser


def _print_lint_report(findings: list[LintFinding]) -> int:
    for finding in findings:
        print(f"{finding.severity}: {finding.file}:{finding.line}: {finding.message}")

    errors = [f for f in findings if f.severity == "error"]
    advisories = [f for f in findings if f.severity == "advisory"]
    print(f"{len(errors)} error(s), {len(advisories)} advisory(ies)")

    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.mode == "lint":
        return _print_lint_report(lint_wiki(os.getcwd()))

    results = install_all()
    exit_code = 0
    for skill_result in results:
        if skill_result.success:
            if skill_result.message:
                print(skill_result.message)
        else:
            print(f"error: {skill_result.error or 'install failed'}", file=sys.stderr)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the install-skill tests plus the lint CLI tests**

Run: `pytest tests/test_wiki_cli_install_skill.py tests/test_wiki_cli.py -v`
Expected: all passed (`test_wiki_cli.py` has no `install-skill` cases, lint cases unaffected)

- [ ] **Step 5: Commit**

```bash
git add src/wiki_cli/cli.py tests/test_wiki_cli_install_skill.py
git commit -m "feat: make wiki install-skill a bare everywhere command"
```

---

### Task 3: Docs, version, full verification

**Files:**
- Modify: `README.md:147-173`
- Modify: `CLAUDE.md:14,50,52`
- Modify: `CHANGELOG.md` (prepend `0.4.0` entry)
- Modify: `pyproject.toml:7`

- [ ] **Step 1: Replace the README install section**

Replace the block starting `### Install the wiki Skills` through the paragraph ending `"already exists (use --force)"` with:

```markdown
### Install the wiki Skills

```bash
wiki install-skill
```

Copies skills from `renatoviolin/wiki-cli` main branch
(`raw.githubusercontent.com`) with no parameters. Installs all three skills,
`wiki-remember`, `wiki-create`, and `wiki-update`, to four locations: the
current checkout (`./.claude/skills/<name>/SKILL.md` for Claude Code and
`./.github/skills/<name>/SKILL.md` for GitHub Copilot / VS Code) and your home
directory (`~/.claude/skills/<name>/SKILL.md`, discovered by both Claude Code
and Copilot, plus `~/.copilot/skills/<name>/SKILL.md` for Copilot). A failure
on one skill still attempts the rest, and the command exits `1` if any of them
failed. Reruns fetch the latest `SKILL.md` from GitHub `main`: files that
differ are overwritten, identical files are reported "already up to date".
```

- [ ] **Step 2: Update the three CLAUDE.md lines**

`CLAUDE.md:14` old:

```
Wiki content for **the repository you are currently in** is written by three skills under `.claude/skills/` — `wiki-create`, `wiki-update`, and `wiki-remember` — which the review flow then reads to make better-informed reviews. A slim companion CLI (`wiki_cli`) ships only two local helpers: `wiki lint` (mechanical checks over `.wiki/` on disk) and `wiki install-skill` (fetch the skills into a checkout from GitHub `main`).
```

new:

```
Wiki content for **the repository you are currently in** is written by three skills under `.claude/skills/` — `wiki-create`, `wiki-update`, and `wiki-remember` — which the review flow then reads to make better-informed reviews. A slim companion CLI (`wiki_cli`) ships only two local helpers: `wiki lint` (mechanical checks over `.wiki/` on disk) and `wiki install-skill` (bare command fetching the three skills from GitHub `main` into the checkout and your home directory).
```

`CLAUDE.md:50` old:

```
- **`cli.py`** — argparse with subparsers `lint`/`install-skill`. `lint` takes no flags and runs the mechanical checks from `lint.py` over the current checkout; `install-skill` fetches from `raw.githubusercontent.com/renatoviolin/wiki-cli/main` — `[skill]` positional (default: installs the bundle `DEFAULT_SKILLS` — `wiki-remember`, `wiki-create`, `wiki-update`; a name installs just that one), `--force`, `--dry-run`, `--target claude|copilot|all` (default `all`).
```

new:

```
- **`cli.py`** — argparse with subparsers `lint`/`install-skill`. Both take no flags: `lint` runs the mechanical checks from `lint.py` over the current checkout; bare `install-skill` installs the bundle `DEFAULT_SKILLS` (`wiki-remember`, `wiki-create`, `wiki-update`) from `raw.githubusercontent.com/renatoviolin/wiki-cli/main` to the checkout and the home directory.
```

`CLAUDE.md:52` old:

```
- **`skills.py`** — `install_skill()` — pure github fetch of `.claude/skills/<name>/SKILL.md` from `raw.githubusercontent.com/renatoviolin/wiki-cli/main` via `urllib`, writes to `.claude/skills/` (Claude Code) and `.github/skills/` (Copilot/VS Code) according to `--target`, handles `--force`/`--dry-run`, idempotent "already up to date" vs "already exists (use --force)" reporting, no SDK dependency. `DEFAULT_SKILLS` is the bundle `install-skill` installs when called with no name.
```

new:

```
- **`skills.py`** — `install_all()` — pure github fetch of `.claude/skills/<name>/SKILL.md` from `raw.githubusercontent.com/renatoviolin/wiki-cli/main` via `urllib`, writes each skill to four roots (checkout `.claude/skills/` + `.github/skills/`, home `~/.claude/skills/` + `~/.copilot/skills/`), overwriting on differs and skipping identical files ("already up to date"), no SDK dependency.
```

- [ ] **Step 3: Prepend the CHANGELOG entry and bump the version**

Prepend above the `## [0.3.0]` line in `CHANGELOG.md`:

```markdown
## [0.4.0] - 2026-09-10

### Changed

- `wiki install-skill` is now bare (no `[skill]` positional, no `--force`/`--dry-run`/`--target`): one invocation installs `wiki-remember`, `wiki-create`, and `wiki-update` from GitHub `main` to the current checkout (`./.claude/skills/`, `./.github/skills/`) and your home directory (`~/.claude/skills/`, `~/.copilot/skills/`). Existing files are overwritten when they differ, skipped when identical.

```

In `pyproject.toml:7` change `version = "0.3.0"` to `version = "0.4.0"`.

- [ ] **Step 4: Run the full suite**

Run: `pytest tests/ -v`
Expected: full suite green

- [ ] **Step 5: Verify the shipped CLI end to end with a redirected HOME**

Run: `mkdir -p /tmp/wiki-verify/home /tmp/wiki-verify/repo && HOME=/tmp/wiki-verify/home python -m wiki_cli.cli install-skill`
Expected: three `installed ...` lines on stdout, exit 0; afterwards `ls /tmp/wiki-verify/home/.claude/skills /tmp/wiki-verify/home/.copilot/skills` shows all three skills and the 12 `SKILL.md` files exist

Run: `HOME=/tmp/wiki-verify/home python -m wiki_cli.cli install-skill`
Expected: three `already up to date` lines, no writes

Run: `python -m wiki_cli.cli install-skill --force`
Expected: exit 2 usage error (old flag rejected)

Run: `python -m wiki_cli.cli install-skill --help`
Expected: exit 0, usage shows the bare subcommand with no options

- [ ] **Step 6: Commit docs and release metadata**

```bash
git add README.md CLAUDE.md CHANGELOG.md pyproject.toml
git commit -m "docs: wiki install-skill installs everywhere with no flags"
```

Do not tag or push; tagging stays the maintainer's call.
