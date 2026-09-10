# Add OpenCode target to `wiki install-skill` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `wiki install-skill` so users can install `wiki-remember` (or any future skill) into OpenCode's native skill location (`.opencode/skills/<name>/SKILL.md`) via `--target opencode` and via `--target all` (which should then install to all three ecosystems: Claude Code, Copilot/VS Code, and OpenCode).

**Architecture:** Pure `src/wiki_cli/skills.py` + `src/wiki_cli/cli.py` change — no SDK, no network change. Add a new constant `_OPENCODE_BASE = ".opencode/skills"` and extend the `target` parameter to accept `"opencode"` and make `"all"` expand to three bases. Keep the existing github-fetch, `force`/`dry-run`, `already up to date` vs `already exists (use --force)` semantics, and idempotency. No change to `_fetch_github`, `_github_raw_url`, or error handling. Docs and Help text updated to list the new target.

**Tech Stack:** Python 3.11+, `urllib` stdlib, `argparse`, `pytest` 8+, no new deps.

---

## File Structure

**Modify:**
- `src/wiki_cli/skills.py` — add `_OPENCODE_BASE`, extend `target` validation and `bases` construction.
- `src/wiki_cli/cli.py:55-59` — extend `choices=["claude", "copilot", "all"]` to `["claude", "copilot", "opencode", "all"]` and update `help`.

**Test:**
- `tests/test_wiki_skills.py` — add `opencode`-specific tests (clone existing claude/copilot patterns).
- `tests/test_wiki_cli_install_skill.py` — extend `test_cli_install_skill_target_flag` to cover `opencode` and `all`.

**Docs:**
- `README.md:190-212` — table / code block for `install-skill --target` examples.
- `CLAUDE.md:54` — `cli.py` line documenting valid `--target` values.
- `.wiki/wiki-cli.md` — skill install section.

---

## Research: How OpenCode Handles Skills (2026-08-28)

Source: `https://opencode.ai/docs/skills/` (last updated 2026-08-27) + blog guides + `opencode.json` schema docs.

**Discovery locations (project-local, walked up to git worktree + global):**
```
Project:  .opencode/skills/<name>/SKILL.md        ← native OpenCode
Global:   ~/.config/opencode/skills/<name>/SKILL.md
Claude compat (also scanned by OpenCode):
          .claude/skills/<name>/SKILL.md
          ~/.claude/skills/<name>/SKILL.md
Agent compat:
          .agents/skills/<name>/SKILL.md
          ~/.agents/skills/<name>/SKILL.md
```
OpenCode loads any matching `skills/*/SKILL.md` in `.opencode/` and also scans `.claude/skills` / `.agents/skills` along the way. So `.claude/skills/wiki-remember/SKILL.md` *already* works in OpenCode via its Claude-compatible scan, but the native project location is `.opencode/skills/wiki-remember/SKILL.md`. Global equivalents exist under `~/.config/opencode/`.

**SKILL.md format:**
```markdown
---
name: wiki-remember
description: "One sentence covering what it does AND when to trigger"
---
# body
```
Required frontmatter: `name` (1-64 chars, lowercase alphanumeric with single hyphens), `description` (1-1024 chars, front-load trigger keywords). Unknown fields ignored. File must be exactly `SKILL.md` inside its own folder.

**Implications for this plan:**
- Do NOT change SKILL.md content — reuse the same file fetched from `raw.githubusercontent.com/renatoviolin/wiki-cli/main/.claude/skills/<name>/SKILL.md` and write it to `.opencode/skills/<name>/SKILL.md` verbatim. The existing SKILL.md already has correct frontmatter (`name: wiki-remember`, `description: ...`).
- Project-local install is the right scope for `wiki install-skill` (current `target_dir=os.getcwd()` behavior) — matches existing `claude`/`copilot` behavior which writes to `<cwd>/.claude/...` and `<cwd>/.github/...`. For OpenCode, write to `<cwd>/.opencode/skills/...`.
- `all` should install to all three project locations to maximize portability: `.claude/skills` (covers Claude + OpenCode via compat), `.github/skills` (Copilot explicit), `.opencode/skills` (OpenCode native, preferred). User can narrow with `--target opencode` (or `claude`/`copilot`).
- Help text and README should call out that `.claude/skills` already works in OpenCode via compat scan, but `.opencode/skills` is the canonical OpenCode project location.

No schema change in `opencode.json` needed — File-based skill discovery requires no config entry unless user uses custom `skills.paths`.

---

### Task 1: Add `opencode` target in `skills.py` (core logic)

**Files:**
- Modify: `src/wiki_cli/skills.py:11-50`
- Test: `tests/test_wiki_skills.py`

- [ ] **Step 1: Write the failing tests for opencode target**

Create new tests mirroring the existing `test_install_github_target_claude_only` pattern. Add to `tests/test_wiki_skills.py` after `test_install_github_target_copilot_only`:

```python
def test_install_github_target_opencode_only(tmp_path, monkeypatch):
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
    result = skills.install_skill(skill="wiki-remember", target_dir=str(target), target="opencode")
    assert result.success is True
    assert (target / ".opencode" / "skills" / "wiki-remember" / "SKILL.md").exists()
    assert not (target / ".claude" / "skills" / "wiki-remember" / "SKILL.md").exists()
    assert not (target / ".github" / "skills" / "wiki-remember" / "SKILL.md").exists()

def test_install_github_target_all_includes_opencode(tmp_path, monkeypatch):
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
    result = skills.install_skill(skill="wiki-remember", target_dir=str(target), target="all")
    assert result.success is True
    assert (target / ".claude" / "skills" / "wiki-remember" / "SKILL.md").exists()
    assert (target / ".github" / "skills" / "wiki-remember" / "SKILL.md").exists()
    assert (target / ".opencode" / "skills" / "wiki-remember" / "SKILL.md").read_bytes() == fake_bytes
```

Also add invalid-target negative test (optional but cheap):

```python
def test_install_github_invalid_target(tmp_path, monkeypatch):
    result = skills.install_skill(skill="wiki-remember", target_dir=str(tmp_path), target="vscode")
    assert result.success is False
    assert "invalid target" in result.error.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_wiki_skills.py::test_install_github_target_opencode_only -v`
Expected: FAIL — `assert ... .opencode ... exists()` fails or `invalid target` for `opencode` (since `skills.py:44-45` currently rejects `opencode`).

Also: `pytest tests/test_wiki_skills.py::test_install_github_target_all_includes_opencode -v`
Expected: FAIL — `all` does not write `.opencode/...`.

- [ ] **Step 3: Implement minimal change in `src/wiki_cli/skills.py`**

`src/wiki_cli/skills.py:12-13` Add constant:

```python
_CLAUDE_BASE = ".claude/skills"
_COPILOT_BASE = ".github/skills"
_OPENCODE_BASE = ".opencode/skills"
```

`src/wiki_cli/skills.py:44-50` Extend validation and bases:

```python
    if target not in ("claude", "copilot", "opencode", "all"):
        return InstallResult(success=False, error=f"invalid target {target!r} — must be claude, copilot, opencode, or all")
    bases = []
    if target in ("claude", "all"):
        bases.append(_CLAUDE_BASE)
    if target in ("copilot", "all"):
        bases.append(_COPILOT_BASE)
    if target in ("opencode", "all"):
        bases.append(_OPENCODE_BASE)
```

Keep `_DEFAULT_REPO`, `_DEFAULT_REF`, `_fetch_github`, dry_run/force/already-up-to-date logic untouched — it already loops over `bases` and `dests`, so it will automatically handle the third dest (including `dry_run` dests_str, `states`, `skipped` counting, `dest.parent.mkdir`, `dest.write_bytes`).

Exact lines: only `src/wiki_cli/skills.py:11-50` touched.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_wiki_skills.py -v`
Expected: PASS — all 11 tests (8 existing + 3 new) pass. Existing claude/copilot/dry-run/force/404 tests unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/wiki_cli/skills.py tests/test_wiki_skills.py
git commit -m "feat: add opencode target to install_skill (.opencode/skills)"
```

---

### Task 2: Wire `opencode` through `cli.py` (`--target` choices)

**Files:**
- Modify: `src/wiki_cli/cli.py:55-59`
- Test: `tests/test_wiki_cli_install_skill.py:62-74`

- [ ] **Step 1: Write the failing CLI test**

Extend `tests/test_wiki_cli_install_skill.py` — add to `test_cli_install_skill_target_flag` a new branch and a new dedicated test:

```python
def test_cli_install_skill_target_flag(monkeypatch, tmp_path):
    captured = {}

    def fake_install(skill=None, target_dir=None, force=False, dry_run=False, target="all"):
        captured["target"] = target
        return InstallResult(success=True, message="ok", dest="x")

    monkeypatch.setattr(cli_module, "install_skill", fake_install)
    monkeypatch.chdir(tmp_path)
    cli_module.main(["install-skill", "--target", "claude"])
    assert captured["target"] == "claude"
    cli_module.main(["install-skill", "--target", "copilot"])
    assert captured["target"] == "copilot"
    cli_module.main(["install-skill", "--target", "opencode"])
    assert captured["target"] == "opencode"
    cli_module.main(["install-skill", "--target", "all"])
    assert captured["target"] == "all"

def test_cli_install_skill_rejects_invalid_target(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc:
        cli_module.main(["install-skill", "--target", "vscode"])
    assert exc.value.code == 2
```

Second test expects argparse to reject invalid `choices` before `install_skill` is called.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wiki_cli_install_skill.py::test_cli_install_skill_target_flag -v`
Expected: FAIL — `SystemExit: 2` on `--target opencode` because `choices=["claude","copilot","all"]` does not include `opencode`. Error: `invalid choice: 'opencode'`.

Run: `pytest tests/test_wiki_cli_install_skill.py::test_cli_install_skill_rejects_invalid_target -v`
Expected: FAIL — test expects SystemExit but not yet present? Actually it should PASS if we expect failure, but before change the test we wrote would fail because it expects 2 and gets 2? The failure mode for the first test is the main. Let's just run the first one to confirm fail.

- [ ] **Step 3: Implement minimal change in `src/wiki_cli/cli.py`**

`src/wiki_cli/cli.py:55-59` Change:

```python
    p_install = sub.add_parser("install-skill", help="install wiki-remember skill from github main")
    p_install.add_argument("skill", nargs="?", default=None, help="skill name (default: wiki-remember)")
    p_install.add_argument("--force", action="store_true", help="overwrite existing SKILL.md")
    p_install.add_argument("--dry-run", action="store_true", help="print what would happen without writing")
    p_install.add_argument("--target", choices=["claude", "copilot", "opencode", "all"], default="all", help="install target: claude (.claude/skills), copilot (.github/skills), opencode (.opencode/skills), or all (default)")
```

Only that line changes. No change to `install_skill` call site `cli.py:81` — it already forwards `target=args.target`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_wiki_cli_install_skill.py -v`
Expected: PASS — all 7 tests pass (6 existing + 1 extended/1 new).

- [ ] **Step 5: Commit**

```bash
git add src/wiki_cli/cli.py tests/test_wiki_cli_install_skill.py
git commit -m "feat: expose --target opencode in wiki install-skill CLI"
```

---

### Task 3: Update documentation (README, CLAUDE, .wiki)

**Files:**
- Modify: `README.md:190-212`
- Modify: `CLAUDE.md:54`
- Modify: `.wiki/wiki-cli.md` (skill install section)

- [ ] **Step 1: Update `README.md` install-skill docs**

Current `README.md:190-212` shows:
```markdown
wiki install-skill                                    # both Claude + Copilot
wiki install-skill --target claude                    # only .claude/skills/
wiki install-skill --target copilot                   # only .github/skills/ (VS Code)
```
Change to:
```markdown
wiki install-skill                                    # all: Claude + Copilot + OpenCode
wiki install-skill --target claude                    # only .claude/skills/ (Claude Code; also auto-discovered by OpenCode)
wiki install-skill --target copilot                   # only .github/skills/ (Copilot/VS Code)
wiki install-skill --target opencode                  # only .opencode/skills/ (OpenCode native)
wiki install-skill --target all                       # alias for default (all three)
```
And paragraph `Copies the wiki-remember skill... into the current checkout. By default installs to both Claude Code... and GitHub Copilot / VS Code...` → update to:

```markdown
Copies the `wiki-remember` skill from `renatoviolin/wiki-cli` main branch
(`raw.githubusercontent.com`) into the current checkout. By default installs
to all three: **Claude Code** (`./.claude/skills/wiki-remember/SKILL.md` —
also auto-discovered by OpenCode via its Claude-compatible scan),
**GitHub Copilot / VS Code** (`./.github/skills/wiki-remember/SKILL.md`),
and **OpenCode** (`./.opencode/skills/wiki-remember/SKILL.md` — native
OpenCode project location; OpenCode also scans `.claude/skills` so either
location works, but `.opencode/skills` is canonical). Use
`--target claude|copilot|opencode|all` to restrict, `--dry-run` to preview
without writing, and `--force` to overwrite. The SKILL.md format (`name` +
`description` frontmatter + Markdown body) is identical for all three agents.
```

- [ ] **Step 2: Update `CLAUDE.md:54`**

Current: `install-skill` fetches... — only `[skill]` positional ... `--target claude|copilot|all` (default `all`). ...
Change `choices` list to `claude|copilot|opencode|all` and add `".opencode/skills/" (OpenCode native; OpenCode also scans .claude/skills)` to description. Exact new line:

```markdown
- **`skills.py`** — `install_skill()` — pure github fetch of `.claude/skills/<name>/SKILL.md` from `raw.githubusercontent.com/renatoviolin/wiki-cli/main` via `urllib`, writes to `.claude/skills/` (Claude Code, also scanned by OpenCode), `.github/skills/` (Copilot / VS Code), and `.opencode/skills/` (OpenCode native) according to `--target`, handles `--force`/`--dry-run`, idempotent "already up to date" vs "already exists (use --force)" reporting, no SDK dependency.
```

And earlier `cli.py` bullet: `--target claude|copilot|opencode|all`.

- [ ] **Step 3: Update `.wiki/wiki-cli.md`**

Same as README — extend the skill install subsection to list three locations and note OpenCode native vs compat scan. Do NOT touch evidence-discipline or other sections.

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md .wiki/wiki-cli.md
git commit -m "docs: document --target opencode for wiki install-skill"
```

---

### Task 4: Dry-run / force / already-up-to-date coverage for `all` (three-dest) + full suite

**Files:**
- Test: `tests/test_wiki_skills.py` (add one more if not already)
- No source change

- [ ] **Step 1: Add comprehensive `all` triple-write dry-run test (if Task 1 didn't already cover)**

Add (or verify exists):

```python
def test_install_all_dry_run_lists_three_dests(tmp_path, monkeypatch):
    target = tmp_path / "repo"
    target.mkdir()
    fake_bytes = b"---\nname: wiki-remember\n---\n# fake"

    class FakeResp:
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def read(self): return fake_bytes

    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout=5: FakeResp())
    result = skills.install_skill(skill="wiki-remember", target_dir=str(target), dry_run=True, target="all")
    assert result.success is True
    assert ".claude" in result.message
    assert ".github" in result.message
    assert ".opencode" in result.message
    assert not (target / ".claude/skills/wiki-remember/SKILL.md").exists()
    assert not (target / ".github/skills/wiki-remember/SKILL.md").exists()
    assert not (target / ".opencode/skills/wiki-remember/SKILL.md").exists()

def test_install_all_already_up_to_date_three(tmp_path, monkeypatch):
    target = tmp_path / "repo"
    target.mkdir()
    fake_bytes = b"---\nname: wiki-remember\n---\n# fake"
    class FakeResp:
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def read(self): return fake_bytes
    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout=5: FakeResp())
    skills.install_skill(skill="wiki-remember", target_dir=str(target), target="all")
    result = skills.install_skill(skill="wiki-remember", target_dir=str(target), target="all")
    assert result.success is True
    assert result.skipped is True
    assert "already up to date" in result.message.lower()
```

- [ ] **Step 2: Run full suite**

Run: `pytest tests/ -v`
Expected: PASS — 214+ tests (210 before + 4 new). No failures in `test_runner.py` or `test_wiki_*`.

- [ ] **Step 3: Manual smoke (no test)**

Run:
```bash
mkdir -p /tmp/opencode-smoke && cd /tmp/opencode-smoke && git init -q
python -m wiki_cli.cli install-skill --target opencode --dry-run
python -m wiki_cli.cli install-skill --target all --dry-run
python -m wiki_cli.cli install-skill --target opencode
ls -R .opencode
cat .opencode/skills/wiki-remember/SKILL.md | head -n 5
# should show frontmatter name: wiki-remember
python -m wiki_cli.cli install-skill --target all --dry-run  # now should say already up to date
```

Expected: dry-run lists three dests for `all`, single for `opencode`; second `all` dry-run says already up to date; file starts with `---` frontmatter.

- [ ] **Step 4: Commit (if new tests added)**

```bash
git add tests/test_wiki_skills.py
git commit -m "test: cover opencode --target all dry-run and idempotency"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- [ ] `opencode` target installs to `.opencode/skills/...` — Task 1
- [ ] `all` installs to three locations — Task 1 + Task 4
- [ ] `--target` choices include `opencode` — Task 2
- [ ] `dry-run`/`force`/`already up to date` semantics preserved for three dests — Task 1/4
- [ ] Docs updated — Task 3
- [ ] No SKILL.md content change (reuse same fetch) — Task 1

**2. Placeholder scan:** No TBD/TODO — all steps have exact code, file paths, and commands.

**3. Type consistency:** `target: str = "all"` with literal union `"claude"|"copilot"|"opencode"|"all"` matches `choices` in `cli.py` and `if target not in (...)` in `skills.py`; `bases` is `list[str]` of `".claude/skills"` etc.; `_OPENCODE_BASE` is `str`.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-28-opencode-install-skill.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
