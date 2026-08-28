# wiki install-skill (hybrid: bundled + GitHub) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `wiki install-skill` to `wiki_cli` — copies `.claude/skills/<name>/SKILL.md` into the caller's checkout via a bundled, offline-first copy (version-pinned) with an opt-in `--from github` network fetch that always pulls latest from `renatoviolin/wiki-cli`.

**Architecture:** Bundle the repo's `.claude/skills/wiki-remember/SKILL.md` as package data under `src/wiki_cli/bundled_skills/` (so `pip install git+https://...` pins it). New `src/wiki_cli/skills.py` exposes `install_skill()` that either copies from `importlib.resources` (default) or fetches via `urllib.request` from `raw.githubusercontent.com` when `--from github`. `src/wiki_cli/cli.py` gains an `install-skill` subcommand (subparsers, backwards-compat with `create|update|lint`) and delegates to `skills.py`. No SDK, no git/gh calls, only stdlib + filesystem.

**Tech Stack:** Python 3.11+, `argparse`, `pathlib`, `shutil`, `importlib.resources` (`files`/`as_file`), `urllib.request` + `urllib.error`, `pytest` + `tmp_path` + `monkeypatch`. No new dependencies.

---

## File Structure

```
src/wiki_cli/
  __init__.py
  cli.py                 # MODIFY — add install-skill subparser, wire to skills.py
  skills.py              # CREATE — bundled+GitHub install logic (no comments, pure functions)
  bundled_skills/
    __init__.py
    wiki-remember/
      SKILL.md           # CREATE — verbatim copy of .claude/skills/wiki-remember/SKILL.md (source of truth stays .claude/)
  result.py              # unchanged
  runner.py              # unchanged
  lint.py                # unchanged
  prompts.py             # unchanged
.claude/skills/
  wiki-remember/
    SKILL.md             # SOURCE OF TRUTH — unchanged, copied at release time
pyproject.toml           # MODIFY — add package-data for bundled_skills
tests/
  test_wiki_cli.py       # MODIFY — add install-skill parser tests (optional, or new file)
  test_wiki_skills.py    # CREATE — unit tests for skills.py (bundled + dry-run + force + errors)
  test_wiki_cli_install_skill.py  # CREATE — CLI integration tests for install-skill
docs/superpowers/plans/2026-08-28-wiki-install-skill.md  # this plan
```

**Responsibilities:**

- `bundled_skills/` — ship-time snapshot of every skill; read-only at runtime via `importlib.resources`. One file today, directory-tree tomorrow.
- `skills.py` — all I/O. Discovers target root, lists bundled skills, reads bundled vs GitHub bytes, compares, writes `.claude/skills/<name>/SKILL.md`, returns a result object. Never calls `query()`/SDK.
- `cli.py` — arg parsing + exit codes + human output only. No filesystem logic beyond `os.getcwd()`.

---

## Global Constraints

- No comments in code anywhere — repo standing rule (`CLAUDE.md: Code style`) — applies to every new file.
- Zero imports between `wiki_cli` and `code_review_cli` (`CLAUDE.md: Architecture`).
- `src/wiki_cli/__init__.py` stays minimal; `skills.py` must be importable without the Claude Agent SDK installed (so install-skill works even if SDK missing).
- Bundled copy is version-pinned: after `pip install git+https://github.com/renatoviolin/wiki-cli.git`, `wiki install-skill` installs the SKILL.md that shipped with that install, not whatever is on `main` today — `--from github` is the only way to get tip-of-main.
- `wiki install-skill` writes only under `<target>/.claude/skills/<name>/` (default `<target>` = `git rev-parse --show-toplevel` if inside git else `os.getcwd()`). Never touches `.wiki/` or source code.
- Idempotent: if destination exists and content identical → no write, report "already up to date". If exists and differs → overwrite only with `--force`; without `--force` report error and exit 1 (or 0 with skip? — spec says error). `--dry-run` prints what would happen, writes nothing.
- Exit codes: `0` success, `1` install failed (exists without force, fetch 404, not a git repo? — still install to cwd), `2` bad args (unknown skill, bad --from/--ref).
- No `git add/commit/push` — same as `wiki create/update` (`prompts.py: _HARD_CONSTRAINTS`).
- Naming: `wiki install-skill` (hyphen) as subcommand, plus single optional positional `skill` (default `wiki-remember`); `--all` flag to install every bundled skill at once (YAGNI guard: implement as trivial loop, but test it).
- Network path uses only stdlib `urllib`; 5s timeout; no auth; public repo only.

---

### Task 1: Bundle the skill as package data

**Files:**
- Create: `src/wiki_cli/bundled_skills/__init__.py`
- Create: `src/wiki_cli/bundled_skills/wiki-remember/SKILL.md`
- Modify: `pyproject.toml:14-22`

- [ ] **Step 1: Create bundled directory and copy SKILL.md verbatim**

Run:
```bash
mkdir -p src/wiki_cli/bundled_skills/wiki-remember
cp .claude/skills/wiki-remember/SKILL.md src/wiki_cli/bundled_skills/wiki-remember/SKILL.md
touch src/wiki_cli/bundled_skills/__init__.py
ls -l src/wiki_cli/bundled_skills/wiki-remember/SKILL.md
```
Expected: file exists, `diff -u .claude/skills/wiki-remember/SKILL.md src/wiki_cli/bundled_skills/wiki-remember/SKILL.md` empty.

- [ ] **Step 2: Update pyproject.toml to include bundled SKILL.md as package data**

Read `pyproject.toml:1-22`, then add after `[tool.setuptools.packages.find]`:

```toml
[tool.setuptools.package-data]
wiki_cli = ["bundled_skills/**/*.md", "bundled_skills/*.md"]
```

Full file should read:
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "code-review-cli"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["claude-agent-sdk>=0.2.137"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
code-review = "code_review_cli.cli:main"
wiki = "wiki_cli.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
wiki_cli = ["bundled_skills/**/*.md"]
```

- [ ] **Step 3: Verify importlib.resources can read the bundled file after editable install**

Run:
```bash
pip install -e . -q
python3 -c "from importlib.resources import files; p=files('wiki_cli')/'bundled_skills/wiki-remember/SKILL.md'; print(p.is_file()); print(p.read_text()[:30])"
```
Expected: `True` and `---` header snippet. If `is_file()` false, check `package-data` glob.

- [ ] **Step 4: Commit**

```bash
git add src/wiki_cli/bundled_skills/__init__.py src/wiki_cli/bundled_skills/wiki-remember/SKILL.md pyproject.toml
git commit -m "feat: bundle wiki-remember skill as package data"
```

---

### Task 2: Core `skills.py` — bundled install, idempotency, dry-run, --all

**Files:**
- Create: `src/wiki_cli/skills.py`
- Test: `tests/test_wiki_skills.py` (created in this task for TDD, first 5 tests are bundled-only)

- [ ] **Step 1: Write failing tests for bundled install**

Create `tests/test_wiki_skills.py`:

```python
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
```

Run: `pytest tests/test_wiki_skills.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wiki_cli.skills'` (or similar).

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_wiki_skills.py -v
```
Expected: 6 failures, first is import error.

- [ ] **Step 3: Implement minimal `src/wiki_cli/skills.py` for bundled path**

Create `src/wiki_cli/skills.py`:

```python
import os
import shutil
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

_BUNDLED_ROOT = "bundled_skills"
_DEFAULT_SKILL = "wiki-remember"

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
    for name in skills_to_install:
        data = _read_bundled(name)
        if data is None:
            return InstallResult(success=False, error=f"unknown skill {name!r}")
        dest = root / ".claude" / "skills" / name / "SKILL.md"
        last_dest = str(dest)
        if dest.exists() and not force and not dry_run:
            existing = dest.read_bytes()
            if existing == data:
                continue
            return InstallResult(success=False, error=f"{dest} already exists (use --force to overwrite)", skipped=True, dest=str(dest))
        if dry_run:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    if dry_run:
        return InstallResult(success=True, message=f"would install {', '.join(skills_to_install)} to {root / '.claude' / 'skills'}", dest=last_dest)
    return InstallResult(success=True, message=f"installed {', '.join(skills_to_install)} to {root / '.claude' / 'skills'}", dest=last_dest)

def _install_from_github(skill, target_dir, ref, repo, force, dry_run, all_skills):
    return InstallResult(success=False, error="github source not yet implemented")
```

- [ ] **Step 4: Run tests to verify bundled path passes**

```bash
pytest tests/test_wiki_skills.py -v
```
Expected: first 4-5 pass; `all` and idempotency edge may need tweak — adjust message/skipped handling until asserts pass. Keep adjusting `skills.py` only, not tests.

- [ ] **Step 5: Commit**

```bash
git add src/wiki_cli/skills.py tests/test_wiki_skills.py
git commit -m "feat: add bundled skill installer with idempotency and dry-run"
```

---

### Task 3: GitHub fetch layer (opt-in `--from github`)

**Files:**
- Modify: `src/wiki_cli/skills.py:40-80`
- Modify: `tests/test_wiki_skills.py` (append GitHub tests)

- [ ] **Step 1: Write failing tests for GitHub source (mocked urllib)**

Append to `tests/test_wiki_skills.py`:

```python
import urllib.request, urllib.error

def test_install_github_fetches_and_writes(tmp_path, monkeypatch):
    target = tmp_path / "repo"
    target.mkdir()
    fake_bytes = b"---\nname: wiki-remember\n---\n# fake"
    class FakeResp:
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def read(self): return fake_bytes
        def getcode(self): return 200
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
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def read(self): return b"content"
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
```

Run: `pytest tests/test_wiki_skills.py -v`
Expected: FAIL — github tests hit "not yet implemented".

- [ ] **Step 2: Implement `_install_from_github` and URL builder**

In `src/wiki_cli/skills.py`, replace stub with:

```python
import urllib.request
import urllib.error

_DEFAULT_REPO = "renatoviolin/wiki-cli"
_DEFAULT_REF = "main"

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
        return InstallResult(success=False, error=f"failed to fetch {name} from github ({exc.code} {exc.reason}) — { _github_raw_url(repo, ref, name)}")
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
```

Also ensure top-level `install_skill` validation for `--from github --all` and unknown `source`.

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_wiki_skills.py -v
```
Expected: all 10 tests PASS.

- [ ] **Step 4: Manual smoke with real network (optional, not in CI)**

```bash
python -m wiki_cli.cli install-skill --from github --dry-run --verbose 2>&1 | head
```
Expected: `would install wiki-remember from github renatoviolin/wiki-cli@main ...` or network error if offline (should not crash).

- [ ] **Step 5: Commit**

```bash
git add src/wiki_cli/skills.py tests/test_wiki_skills.py
git commit -m "feat: add github fetch for install-skill via raw.githubusercontent.com"
```

---

### Task 4: CLI — `wiki install-skill` subcommand

**Files:**
- Modify: `src/wiki_cli/cli.py:1-90`
- Test: `tests/test_wiki_cli_install_skill.py` (CREATE)

Current `cli.py:35-45` uses `parser.add_argument("mode", choices=["create","update","lint"])`. This task replaces it with subparsers while keeping `create|update|lint` working.

- [ ] **Step 1: Write failing CLI integration tests**

Create `tests/test_wiki_cli_install_skill.py`:

```python
import wiki_cli.cli as cli_module
from wiki_cli.skills import InstallResult

def test_cli_install_skill_calls_bundled_by_default(monkeypatch, tmp_path, capsys):
    captured = {}
    def fake_install(skill=None, target_dir=None, source="bundled", ref=None, repo=None, force=False, dry_run=False, all_skills=False):
        captured.update(dict(skill=skill, source=source, force=force, dry_run=dry_run, all_skills=all_skills))
        return InstallResult(success=True, message="installed wiki-remember", dest=str(tmp_path / ".claude/skills/wiki-remember/SKILL.md"))
    monkeypatch.setattr(cli_module, "install_skill", fake_install)
    monkeypatch.chdir(tmp_path)
    code = cli_module.main(["install-skill"])
    assert code == 0
    assert captured["source"] == "bundled"
    assert captured["skill"] is None
    out = capsys.readouterr().out
    assert "installed" in out.lower()

def test_cli_install_skill_explicit_name(monkeypatch, tmp_path):
    captured = {}
    def fake_install(skill=None, **kw): captured["skill"]=skill; return InstallResult(success=True, message="ok", dest="x")
    monkeypatch.setattr(cli_module, "install_skill", fake_install)
    monkeypatch.chdir(tmp_path)
    cli_module.main(["install-skill", "wiki-remember"])
    assert captured["skill"] == "wiki-remember"

def test_cli_install_skill_force_flag(monkeypatch, tmp_path):
    captured = {}
    def fake_install(skill=None, force=False, **kw): captured["force"]=force; return InstallResult(success=True, message="ok", dest="x")
    monkeypatch.setattr(cli_module, "install_skill", fake_install)
    monkeypatch.chdir(tmp_path)
    cli_module.main(["install-skill", "--force"])
    assert captured["force"] is True

def test_cli_install_skill_dry_run(monkeypatch, tmp_path):
    captured = {}
    def fake_install(dry_run=False, **kw): captured["dry_run"]=dry_run; return InstallResult(success=True, message="would install", dest="x")
    monkeypatch.setattr(cli_module, "install_skill", fake_install)
    monkeypatch.chdir(tmp_path)
    cli_module.main(["install-skill", "--dry-run"])
    assert captured["dry_run"] is True

def test_cli_install_skill_from_github(monkeypatch, tmp_path):
    captured = {}
    def fake_install(source="bundled", ref=None, repo=None, **kw):
        captured.update(source=source, ref=ref, repo=repo); return InstallResult(success=True, message="ok", dest="x")
    monkeypatch.setattr(cli_module, "install_skill", fake_install)
    monkeypatch.chdir(tmp_path)
    cli_module.main(["install-skill", "--from", "github", "--ref", "v0.1.0", "--repo", "renatoviolin/wiki-cli"])
    assert captured["source"] == "github"
    assert captured["ref"] == "v0.1.0"
    assert captured["repo"] == "renatoviolin/wiki-cli"

def test_cli_install_skill_reports_error_and_exits_one(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli_module, "install_skill", lambda **kw: InstallResult(success=False, error="already exists (use --force)"))
    monkeypatch.chdir(tmp_path)
    code = cli_module.main(["install-skill"])
    assert code == 1
    assert "already exists" in capsys.readouterr().err.lower()

def test_cli_install_skill_all_flag(monkeypatch, tmp_path):
    captured = {}
    def fake_install(all_skills=False, **kw): captured["all_skills"]=all_skills; return InstallResult(success=True, message="installed", dest="x")
    monkeypatch.setattr(cli_module, "install_skill", fake_install)
    monkeypatch.chdir(tmp_path)
    cli_module.main(["install-skill", "--all"])
    assert captured["all_skills"] is True
```

Run: `pytest tests/test_wiki_cli_install_skill.py -v`
Expected: FAIL — `unrecognized arguments` or `choices` error.

- [ ] **Step 2: Refactor `src/wiki_cli/cli.py` to subparsers**

Replace `src/wiki_cli/cli.py:35-90` with:

```python
import argparse
import os
import sys

from .lint import lint_wiki
from .result import WikiResult
from .skills import install_skill

_MODEL_ALIASES = {"haiku": "claude-haiku-4-5", "sonnet": "claude-sonnet-5", "opus": "claude-opus-5"}

def _print_metrics(result: WikiResult, mode: str) -> None: ... # keep as-is

def _print_lint_report(findings): ... # keep as-is

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wiki", description="Generate or update the .wiki knowledge base for the current repository.")
    sub = parser.add_subparsers(dest="mode", required=True)
    p_create = sub.add_parser("create", help="inventory and write .wiki from scratch")
    p_create.add_argument("--model", default=None)
    p_create.add_argument("--verbose", action="store_true")
    p_update = sub.add_parser("update", help="update .wiki for changes since last wiki commit")
    p_update.add_argument("--model", default=None)
    p_update.add_argument("--verbose", action="store_true")
    p_lint = sub.add_parser("lint", help="mechanical checks over .wiki on disk")
    p_lint.add_argument("--model", default=None)
    p_lint.add_argument("--verbose", action="store_true")
    p_install = sub.add_parser("install-skill", help="install .claude/skills from bundled package or github")
    p_install.add_argument("skill", nargs="?", default=None, help="skill name (default: wiki-remember)")
    p_install.add_argument("--force", action="store_true", help="overwrite existing SKILL.md")
    p_install.add_argument("--dry-run", action="store_true", help="print what would happen without writing")
    p_install.add_argument("--from", dest="source", choices=["bundled", "github"], default="bundled", help="source to install from")
    p_install.add_argument("--ref", default=None, help="git ref for --from github (default: main)")
    p_install.add_argument("--repo", default=None, help="owner/repo for --from github (default: renatoviolin/wiki-cli)")
    p_install.add_argument("--all", dest="all_skills", action="store_true", help="install all bundled skills")
    p_install.add_argument("--verbose", action="store_true", help="verbose output")
    return parser

def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.mode == "lint":
        return _print_lint_report(lint_wiki(os.getcwd()))
    if args.mode == "install-skill":
        if args.all_skills and args.skill is not None:
            print("error: --all cannot be combined with a skill name", file=sys.stderr)
            return 2
        if args.source == "github" and args.all_skills:
            print("error: --all not supported with --from github", file=sys.stderr)
            return 2
        if args.ref is not None and args.source != "github":
            print("error: --ref only valid with --from github", file=sys.stderr)
            return 2
        if args.repo is not None and args.source != "github":
            print("error: --repo only valid with --from github", file=sys.stderr)
            return 2
        result = install_skill(skill=args.skill, target_dir=os.getcwd(), source=args.source, ref=args.ref, repo=args.repo, force=args.force, dry_run=args.dry_run, all_skills=args.all_skills)
        if result.success:
            if result.message:
                print(result.message)
            return 0
        msg = result.error or "install failed"
        print(f"error: {msg}", file=sys.stderr)
        return 1
    model = None
    if args.model is not None:
        model = _MODEL_ALIASES.get(args.model.lower())
        if model is None:
            print(f"error: --model must be one of {sorted(_MODEL_ALIASES)}, got {args.model!r}", file=sys.stderr)
            return 2
    from .runner import run_wiki
    result: WikiResult = run_wiki(args.mode, verbose=args.verbose, model=model)
    _print_metrics(result, args.mode)
    if result.success:
        print(result.text)
        for page in result.pages_written:
            print(page)
        return 0
    print(f"error: {result.error_message}", file=sys.stderr)
    return result.exit_code()
```

Key: lazy import `run_wiki` inside `main` so `install-skill` does not require `claude-agent-sdk` installed.

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_wiki_cli_install_skill.py tests/test_wiki_cli.py -v
```
Expected: all PASS. Existing `tests/test_wiki_cli.py` still passes because `create|update|lint` subparsers preserve same `args.mode` values. Fix any `SystemExit` code 2 mismatches.

- [ ] **Step 4: Manual run**

```bash
python -m wiki_cli.cli install-skill --dry-run 2>&1
python -m wiki_cli.cli install-skill --help 2>&1 | head -n 40
python -m wiki_cli.cli create --help 2>&1 | head -n 20
```
Expected: help shows `install-skill` with `--from {bundled,github}`, `--force`, `--dry-run`, `--all`.

- [ ] **Step 5: Commit**

```bash
git add src/wiki_cli/cli.py tests/test_wiki_cli_install_skill.py
git commit -m "feat: add wiki install-skill CLI subcommand"
```

---

### Task 5: Keep bundled copy in sync + add existing CLI tests for backward compat

**Files:**
- Modify: `tests/test_wiki_cli.py` (add lint/create compat if missing)
- Create: `scripts/sync-bundled-skills.sh` (optional)

- [ ] **Step 1: Verify existing wiki CLI tests still pass unchanged**

```bash
pytest tests/test_wiki_cli.py tests/test_wiki_runner.py tests/test_wiki_skills.py -v
```
Expected: all PASS (13+6 existing). If any `choices` test expects `argparse` error message wording, update test to match subparser message (`invalid choice` → `argument mode: invalid choice` vs `required`).

- [ ] **Step 2: Add sync helper (optional, YAGNI-safe)**

Create `scripts/sync-bundled-skills.sh`:

```bash
#!/bin/sh
set -eu
cp .claude/skills/wiki-remember/SKILL.md src/wiki_cli/bundled_skills/wiki-remember/SKILL.md
echo "synced"
```

Run: `chmod +x scripts/sync-bundled-skills.sh && ./scripts/sync-bundled-skills.sh && git diff --stat`
Expected: no diff (already in sync). Document in `CLAUDE.md` release checklist to run this before bumping version.

- [ ] **Step 3: Run full suite**

```bash
pytest tests/ -v
```
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add tests/test_wiki_cli.py scripts/sync-bundled-skills.sh
git commit -m "chore: keep bundled skills in sync"
```

---

### Task 6: Docs and release

**Files:**
- Modify: `README.md:100-185` (wiki_cli usage section)
- Modify: `CLAUDE.md: Architecture` (wiki_cli — five modules)
- Modify: `CHANGELOG.md:1-10`
- Modify: `pyproject.toml:7` (version bump if releasing)

- [ ] **Step 1: Update README.md wiki_cli usage**

Under `### Usage` after `wiki lint` docs, add:

````markdown
### Install the wiki-remember Skill

```bash
wiki install-skill
wiki install-skill --dry-run
wiki install-skill --force
wiki install-skill --from github
wiki install-skill --from github --ref v0.2.0
wiki install-skill --all
```

Copies the bundled `wiki-remember` skill into `./.claude/skills/wiki-remember/SKILL.md` of the current checkout (or `git` root). By default it installs the version pinned to your installed `wiki` package (offline, no network). Use `--from github` to fetch tip-of-`main` (or a tagged `--ref`) from `renatoviolin/wiki-cli`. `--dry-run` previews, `--force` overwrites an existing install, `--all` installs every bundled skill.
````

- [ ] **Step 2: Update CLAUDE.md Architecture wiki_cli section**

Change "four modules" → "six modules" and add bullet:

```markdown
- **`skills.py`** — `install_skill()` — copies `.claude/skills/<name>/SKILL.md` from `bundled_skills/` (via `importlib.resources`) or from `raw.githubusercontent.com` when `--from github`. Handles `--force`/`--dry-run`/`--all`, no SDK dependency.
- **`bundled_skills/`** — package data snapshot of `.claude/skills/*` shipped at `pip install` time; `skills.py` reads from here for offline installs.
```

Also note `cli.py` now uses `subparsers` with `install-skill`.

- [ ] **Step 3: Update CHANGELOG.md**

Add `## [0.2.0] - 2026-08-28`:

```markdown
## [0.2.0] - 2026-08-28

### wiki_cli

- Add `wiki install-skill` (hybrid): installs `.claude/skills/wiki-remember/SKILL.md` into the current checkout from bundled package data (default, offline, version-pinned) or from GitHub with `--from github [--ref <tag>] [--repo owner/repo]`. Supports `--force`, `--dry-run`, `--all`.
```

- [ ] **Step 4: Verify docs build**

```bash
pytest tests/ -q
python -m wiki_cli.cli --help 2>&1 | head -n 50
python -m wiki_cli.cli install-skill --help 2>&1 | head -n 30
```

- [ ] **Step 5: Commit and tag (per CLAUDE.md Releasing)**

```bash
git add README.md CLAUDE.md CHANGELOG.md pyproject.toml
git commit -m "docs: document wiki install-skill"
# only if releasing:
# git tag -a v0.2.0 -m "v0.2.0 - wiki install-skill (hybrid bundled+github)"
```

---

## Self-Review Checklist

- [ ] Every `wiki install-skill` variant from spec has a test: default bundled, explicit name, `--force`, `--dry-run`, `--from github` + `--ref`/`--repo`, `--all`, unknown skill, already-exists without force, 404, `--all` with name, `--ref` without github.
- [ ] No placeholders — every step has exact code/commands.
- [ ] Types consistent: `InstallResult(success, message, error, skipped, dest)` used identically in `skills.py` and CLI tests.
- [ ] No new deps, no SDK import in `skills.py`, lazy `run_wiki` import in `cli.py`.
- [ ] `pyproject.toml` package-data glob correct (`bundled_skills/**/*.md`).
- [ ] Existing `tests/test_wiki_cli.py` still green after subparser refactor.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-28-wiki-install-skill.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
