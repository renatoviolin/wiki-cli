# Remove wiki-cli headless commands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shrink `wiki_cli` to the `lint` + `install-skill` helpers, deleting the headless `create`/`update` stack and the skill generator.

**Architecture:** Test-first removal: rewrite `tests/test_wiki_cli.py` to assert the new surface (fails against current code), slim `src/wiki_cli/cli.py`, delete the four dead source modules and four dead test files, then update docs/version/changelog.

**Tech Stack:** Python 3.11+, argparse, pytest, git.

---

## File structure

| File | Change |
|---|---|
| `tests/test_wiki_cli.py` | Rewrite: drop all `run_wiki`/`WikiResult`/model tests, assert `create`/`update`/`generate-skills` rejected and `lint` takes no flags |
| `src/wiki_cli/cli.py` | Rewrite: only `lint` (bare) + `install-skill` subparsers |
| `src/wiki_cli/prompts.py` | Delete (`git rm`) |
| `src/wiki_cli/runner.py` | Delete (`git rm`) |
| `src/wiki_cli/result.py` | Delete (`git rm`) |
| `src/wiki_cli/skill_gen.py` | Delete (`git rm`) |
| `tests/test_wiki_prompts.py` | Delete (`git rm`) |
| `tests/test_wiki_runner.py` | Delete (`git rm`) |
| `tests/test_wiki_skill_gen.py` | Delete (`git rm`) |
| `tests/test_wiki_cli_generate_skills.py` | Delete (`git rm`) |
| `src/wiki_cli/lint.py` | Untouched |
| `src/wiki_cli/skills.py` | Untouched |
| `src/wiki_cli/__init__.py` | Untouched (empty) |
| `.claude/skills/*.md` | Untouched (byte-identical) |
| `src/code_review_cli/` | Untouched |
| `CLAUDE.md` | Edit: "What this is", Commands example, Architecture intro, `wiki_cli` module list, remove "Why the wiki prompt" section |
| `README.md` | Edit: install paragraph, `wiki_cli` section (drop `create`/`update` usage, fix skill comparison) |
| `CHANGELOG.md` | Add `[0.3.0]` entry at top |
| `pyproject.toml` | Version `0.2.1` → `0.3.0` |

`result.py` is safe to delete: the only importers of `wiki_cli.result.WikiResult` are `src/wiki_cli/cli.py` and `src/wiki_cli/runner.py` (verified by grep; `code_review_cli` has its own `ReviewResult` and there are zero imports between the two packages).

> Staging warning: the working tree already contains unrelated uncommitted
> changes (`.claude/skills/*.md`, `src/wiki_cli/prompts.py`, plus untracked
> `.claude/skills/.DS_Store`, `.vscode/`,
> `docs/superpowers/plans/2026-08-28-opencode-install-skill.md`). Every commit
> below must `git add` ONLY the listed files. Never `git add -A` / `git commit -a`.

---

### Task 1: Rewrite `tests/test_wiki_cli.py` for the new surface (red)

**Files:**
- Modify: `tests/test_wiki_cli.py` (full rewrite)

- [ ] **Step 1: Write the new test file**

Replace the entire contents of `tests/test_wiki_cli.py` with:

```python
import os

import pytest

import wiki_cli.cli as cli_module
from wiki_cli.lint import LintFinding


@pytest.mark.parametrize(
    "argv",
    [
        ["create"],
        ["update"],
        ["generate-skills"],
        ["destroy"],
        [],
        ["lint", "--model", "opus"],
    ],
)
def test_main_rejects_removed_modes_and_flags(argv):
    with pytest.raises(SystemExit) as exc:
        cli_module.main(argv)

    assert exc.value.code == 2


def test_main_lint_passes_cwd_as_repo_root(monkeypatch, tmp_path):
    captured = {}

    def _fake_lint(repo_root):
        captured["repo_root"] = repo_root
        return []

    monkeypatch.setattr(cli_module, "lint_wiki", _fake_lint)
    monkeypatch.chdir(tmp_path)

    cli_module.main(["lint"])

    assert captured["repo_root"] == os.getcwd()


def test_main_lint_reports_errors_and_returns_one(monkeypatch, capsys):
    monkeypatch.setattr(
        cli_module,
        "lint_wiki",
        lambda repo_root: [
            LintFinding(
                file=".wiki/page.md",
                line=3,
                severity="error",
                message="missing `## Sources` section",
            )
        ],
    )

    exit_code = cli_module.main(["lint"])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert ".wiki/page.md" in out
    assert "missing `## Sources` section" in out


def test_main_lint_advisory_only_returns_zero(monkeypatch, capsys):
    monkeypatch.setattr(
        cli_module,
        "lint_wiki",
        lambda repo_root: [
            LintFinding(
                file=".wiki/page.md",
                line=5,
                severity="advisory",
                message="possible stale reference",
            )
        ],
    )

    exit_code = cli_module.main(["lint"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "possible stale reference" in out


def test_main_lint_clean_wiki_prints_summary(monkeypatch, capsys):
    monkeypatch.setattr(cli_module, "lint_wiki", lambda repo_root: [])

    exit_code = cli_module.main(["lint"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "0 error" in out
```

- [ ] **Step 2: Run the rewritten tests to verify they fail**

Run: `pytest tests/test_wiki_cli.py -v`
Expected: FAIL — `test_main_rejects_create_mode`, `test_main_rejects_update_mode`, `test_main_rejects_generate_skills_mode`, and `test_main_lint_rejects_model_flag` fail because the current parser still accepts `create`/`update`/`generate-skills` and `lint --model`. The six lint behavior tests pass.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_wiki_cli.py
git commit -m "test: assert wiki CLI keeps only lint and install-skill"
```

---

### Task 2: Slim `src/wiki_cli/cli.py` (green)

**Files:**
- Modify: `src/wiki_cli/cli.py` (full rewrite)
- Test: `tests/test_wiki_cli.py`

- [ ] **Step 1: Write the slimmed CLI**

Replace the entire contents of `src/wiki_cli/cli.py` with (no comments, per repo code style):

```python
import argparse
import os
import sys

from .lint import LintFinding, lint_wiki
from .skills import DEFAULT_SKILLS, install_skill


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wiki",
        description="Local helpers for the .wiki knowledge base: mechanical lint checks and skill installation. Wiki content itself is written by the wiki-create, wiki-update, and wiki-remember skills.",
    )
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("lint", help="mechanical checks over .wiki on disk")
    p_install = sub.add_parser("install-skill", help=f"install wiki skills from github main (default: {', '.join(DEFAULT_SKILLS)})")
    p_install.add_argument("skill", nargs="?", default=None, help=f"skill name (default: installs {', '.join(DEFAULT_SKILLS[:-1])}, and {DEFAULT_SKILLS[-1]})")
    p_install.add_argument("--force", action="store_true", help="overwrite existing SKILL.md")
    p_install.add_argument("--dry-run", action="store_true", help="print what would happen without writing")
    p_install.add_argument("--target", choices=["claude", "copilot", "all"], default="all", help="install target: claude (.claude/skills), copilot (.github/skills), or all (default)")
    return parser


def _print_lint_report(findings: list[LintFinding]) -> int:
    for finding in findings:
        print(f"{finding.severity}: {finding.file}:{finding.line}: {finding.message}")

    errors = sum(finding.severity == "error" for finding in findings)
    advisories = sum(finding.severity == "advisory" for finding in findings)
    print(f"{errors} error(s), {advisories} advisory(ies)")

    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.mode == "lint":
        return _print_lint_report(lint_wiki(os.getcwd()))

    names = [args.skill] if args.skill else DEFAULT_SKILLS
    exit_code = 0
    for name in names:
        skill_result = install_skill(skill=name, target_dir=os.getcwd(), force=args.force, dry_run=args.dry_run, target=args.target)
        if skill_result.success and skill_result.message:
            print(skill_result.message)
        else:
            print(f"error: {skill_result.error or 'install failed'}", file=sys.stderr)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the CLI tests to verify they pass**

Run: `pytest tests/test_wiki_cli.py tests/test_wiki_cli_install_skill.py tests/test_wiki_lint.py tests/test_wiki_skills.py -v`
Expected: PASS — all tests in the four kept files pass. (`tests/test_wiki_prompts.py`, `tests/test_wiki_runner.py`, `tests/test_wiki_skill_gen.py`, and `tests/test_wiki_cli_generate_skills.py` still exist and still pass at this point; they are deleted in Task 4.)

- [ ] **Step 3: Commit**

```bash
git add src/wiki_cli/cli.py tests/test_wiki_cli.py
git commit -m "feat: slim wiki CLI to lint and install-skill"
```

---

### Task 3: Delete the dead source modules

**Files:**
- Delete: `src/wiki_cli/prompts.py`, `src/wiki_cli/runner.py`, `src/wiki_cli/result.py`, `src/wiki_cli/skill_gen.py`

- [ ] **Step 1: Remove the files**

```bash
git rm src/wiki_cli/prompts.py src/wiki_cli/runner.py src/wiki_cli/result.py src/wiki_cli/skill_gen.py
```

- [ ] **Step 2: Verify nothing references the deleted modules**

Run: `rg -n "wiki_cli\.(prompts|runner|result|skill_gen)|from \.(prompts|runner|result|skill_gen)|from wiki_cli\.(prompts|runner|result|skill_gen)|write_skill_files|render_skill_md|run_wiki|WikiResult|build_prompt|_MODEL_ALIASES|_print_metrics" src/ tests/`
Expected: no output.

- [ ] **Step 3: Run the full suite to confirm the only failures are the orphaned test files**

Run: `pytest tests/ -v`
Expected: FAIL — only collection errors / import failures in `tests/test_wiki_prompts.py`, `tests/test_wiki_runner.py`, `tests/test_wiki_skill_gen.py`, and `tests/test_wiki_cli_generate_skills.py`, because they import the deleted modules. Everything else passes.

- [ ] **Step 4: Commit**

```bash
git add -u src/wiki_cli/
git commit -m "feat: delete wiki headless stack and skill generator"
```

---

### Task 4: Delete the orphaned test files (green)

**Files:**
- Delete: `tests/test_wiki_prompts.py`, `tests/test_wiki_runner.py`, `tests/test_wiki_skill_gen.py`, `tests/test_wiki_cli_generate_skills.py`

- [ ] **Step 1: Remove the files**

```bash
git rm tests/test_wiki_prompts.py tests/test_wiki_runner.py tests/test_wiki_skill_gen.py tests/test_wiki_cli_generate_skills.py
```

- [ ] **Step 2: Run the full suite to verify it is green**

Run: `pytest tests/ -v`
Expected: PASS — full suite green, and `tests/test_wiki_cli.py`, `tests/test_wiki_lint.py`, `tests/test_wiki_skills.py`, `tests/test_wiki_cli_install_skill.py` are the only remaining `test_wiki_*` files.

- [ ] **Step 3: Commit**

```bash
git add -u tests/
git commit -m "test: drop tests for removed wiki headless commands"
```

---

### Task 5: Docs, version, changelog

**Files:**
- Modify: `CLAUDE.md`, `README.md`, `CHANGELOG.md`, `pyproject.toml`

- [ ] **Step 1: Update `CLAUDE.md`, hunk 1 — "What this is" (lines 14-19)**

Old:

```
A second, independent CLI (`wiki_cli`) generates and maintains a `.wiki/` knowledge base for **the repository you are currently in**, which the review flow then reads to make better-informed reviews. It takes no repo/provider arguments — it operates on the current checkout, writes files, and stops without committing; the developer commits `.wiki/` alongside their own work. A separate Claude Code Skill, `wiki-remember` (`.claude/skills/wiki-remember/SKILL.md`), also writes into `.wiki/` — interactively, from conversation, capturing decisions under `.wiki/decisions/`; `wiki_cli` is instructed to leave `.wiki/decisions/` and the index's "Decisions & rationale" section alone.

```bash
python -m wiki_cli.cli create|update [--model haiku|sonnet|opus] [--verbose]
# --model defaults to sonnet; opus only with --model opus
```
```

New:

```
Wiki content for **the repository you are currently in** is written by three skills under `.claude/skills/` — `wiki-create`, `wiki-update`, and `wiki-remember` — which the review flow then reads to make better-informed reviews. A slim companion CLI (`wiki_cli`) ships only two local helpers: `wiki lint` (mechanical checks over `.wiki/` on disk) and `wiki install-skill` (fetch the skills into a checkout from GitHub `main`).

```bash
python -m wiki_cli.cli lint|install-skill
```
```

- [ ] **Step 2: Update `CLAUDE.md`, hunk 2 — Commands example (line 28)**

Old:

```
pytest tests/test_wiki_runner.py -v   # wiki_cli's tests are prefixed test_wiki_*
```

New:

```
pytest tests/test_wiki_lint.py -v     # wiki_cli's tests are prefixed test_wiki_*
```

- [ ] **Step 3: Update `CLAUDE.md`, hunk 3 — Architecture intro (line 47) and `wiki_cli` module list (lines 49-57)**

Old:

```
Two independent packages under `src/`, sharing only this repository — **zero imports between them**. `code_review_cli` reviews a pull request; `wiki_cli` maintains the `.wiki/` knowledge base for the current checkout. The only coupling is a convention: the review prompt reads `.wiki/` if it happens to exist.

### `wiki_cli` — seven modules

- **`prompts.py`** — `build_prompt(mode)` for `create` / `update`, plus the forced `_RESULT_SCHEMA` (`{success, summary, pages_written, failure_reason}`). The prompt has the session resolve the repo root itself (`git rev-parse --show-toplevel`) and, for `update`, find the wiki's last commit (`git log -1 --format=%H -- .wiki/`) and diff it against `HEAD` — so the wrapper still never runs git. The prompt body (~10KB per mode) is assembled from labelled sections — hard constraints, evidence discipline, page contract, structure, style, diagrams, finishing checks — plus one mode-specific workflow. A hard constraint in the shared preamble carves `.wiki/decisions/` out of both modes' regeneration/delete behavior and requires copying `index.md`'s "Decisions & rationale" section forward verbatim. See "Why the wiki prompt is written the way it is" below before editing any of it.
- **`result.py`** — `WikiResult`, mirroring `ReviewResult` plus `pages_written`.
- **`runner.py`** — the one `query()` call. Unlike `code_review_cli.runner` it uses `cwd=os.getcwd()` with **no temp workspace and no cleanup**, because it deliberately writes into the developer's real checkout.
- **`cli.py`** — argparse with subparsers `create`/`update`/`lint`/`install-skill`/`generate-skills`. `create`/`update` take the single positional mode plus `--model`/`--verbose` (`--model` defaults to `sonnet`, `opus` only with `--model opus`); `lint` is model-free; `install-skill` fetches from `raw.githubusercontent.com/renatoviolin/wiki-cli/main` — `[skill]` positional (default: installs the bundle `DEFAULT_SKILLS` — `wiki-remember`, `wiki-create`, `wiki-update`; a name installs just that one), `--force`, `--dry-run`, `--target claude|copilot|all` (default `all`); `generate-skills` is the dev-only, model-free command that (re)writes `.claude/skills/wiki-create/SKILL.md` and `wiki-update/SKILL.md` in *this* repo from `prompts.py`, to be run and committed whenever `prompts.py` changes. No `validation.py`: argparse `choices` covers the only arguments, and the small model-alias map lives inline.
- **`lint.py`** — pure mechanical checks over `.wiki/` on disk (no Claude call): `## Sources` presence and path existence, pytest-style `` `path::symbol` `` resolution, and advisory header-attributed symbol checks.
- **`skills.py`** — `install_skill()` — pure github fetch of `.claude/skills/<name>/SKILL.md` from `raw.githubusercontent.com/renatoviolin/wiki-cli/main` via `urllib`, writes to `.claude/skills/` (Claude Code) and `.github/skills/` (Copilot/VS Code) according to `--target`, handles `--force`/`--dry-run`, idempotent "already up to date" vs "already exists (use --force)" reporting, no SDK dependency. `DEFAULT_SKILLS` is the bundle `install-skill` installs when called with no name.
- **`skill_gen.py`** — `render_skill_md(mode)`/`write_skill_files()`: wraps `prompts.build_prompt(mode)` verbatim (JSON-closing instruction and all — deliberately the *exact same* prompt the headless CLI sends, not a reworded "interactive" variant, so there is exactly one place that tunes create/update behavior) in YAML frontmatter to produce `wiki-create`/`wiki-update`'s `SKILL.md`. Pure string/filesystem code, no SDK dependency — this is what `generate-skills` calls.
```

New:

```
Two independent packages under `src/`, sharing only this repository — **zero imports between them**. `code_review_cli` reviews a pull request; wiki content for the current checkout is written by the `wiki-create` / `wiki-update` / `wiki-remember` skills under `.claude/skills/`, and `wiki_cli` ships only the two local helpers those skills rely on (`lint`, `install-skill`). The only coupling is a convention: the review prompt reads `.wiki/` if it happens to exist.

### `wiki_cli` — two helpers

- **`cli.py`** — argparse with subparsers `lint`/`install-skill`. `lint` takes no flags and runs the mechanical checks from `lint.py` over the current checkout; `install-skill` fetches from `raw.githubusercontent.com/renatoviolin/wiki-cli/main` — `[skill]` positional (default: installs the bundle `DEFAULT_SKILLS` — `wiki-remember`, `wiki-create`, `wiki-update`; a name installs just that one), `--force`, `--dry-run`, `--target claude|copilot|all` (default `all`).
- **`lint.py`** — pure mechanical checks over `.wiki/` on disk (no Claude call): `## Sources` presence and path existence, pytest-style `` `path::symbol` `` resolution, and advisory header-attributed symbol checks.
- **`skills.py`** — `install_skill()` — pure github fetch of `.claude/skills/<name>/SKILL.md` from `raw.githubusercontent.com/renatoviolin/wiki-cli/main` via `urllib`, writes to `.claude/skills/` (Claude Code) and `.github/skills/` (Copilot/VS Code) according to `--target`, handles `--force`/`--dry-run`, idempotent "already up to date" vs "already exists (use --force)" reporting, no SDK dependency. `DEFAULT_SKILLS` is the bundle `install-skill` installs when called with no name.
```

- [ ] **Step 4: Update `CLAUDE.md`, hunk 4 — remove "Why the wiki prompt is written the way it is" (lines 77-87)**

Delete the entire `### Why the wiki prompt is written the way it is` section (from the `### Why the wiki prompt is written the way it is` heading through the `...which is what makes the wiki self-correcting over time.` paragraph), and replace it with:

```
### Where the wiki instructions live

The wiki instructions live only in `.claude/skills/wiki-create/SKILL.md`, `.claude/skills/wiki-update/SKILL.md`, and `.claude/skills/wiki-remember/SKILL.md` — there is no generator and no `prompts.py` to keep in sync. The review prompt's rule that the code outranks the wiki, with instructions to report contradictions in the review, is what makes the wiki self-correcting over time.
```

Leave the `docs/superpowers/specs/` history paragraph and `### Design history` that follow it untouched.

- [ ] **Step 5: Update `README.md`, hunk 1 — install paragraph (lines 45-49)**

Old:

```
Either install exposes two console scripts from the same `pyproject.toml`:
`code-review` (documented below) and `wiki`, which generates and maintains
the `.wiki/` knowledge base this repo's review prompt reads for context —
see `.wiki/wiki-cli.md` or `CLAUDE.md` for its usage. See
[CHANGELOG.md](CHANGELOG.md) for what changed in each release.
```

New:

```
Either install exposes two console scripts from the same `pyproject.toml`:
`code-review` (documented below) and `wiki`, which ships the two local
helpers for the `.wiki/` knowledge base this repo's review prompt reads for
context (`lint` and `install-skill` — see below). Wiki content itself is
written by the `wiki-create` / `wiki-update` / `wiki-remember` skills — see
`CLAUDE.md` for their usage. See [CHANGELOG.md](CHANGELOG.md) for what
changed in each release.
```

- [ ] **Step 6: Update `README.md`, hunk 2 — `wiki_cli` section (lines 103-169)**

Old (from `## wiki_cli` through the end of the lint `--model`/`--verbose` paragraph):

```
## wiki_cli

`wiki_cli` generates and maintains a `.wiki/` knowledge base for the
repository you're currently in. Unlike `code-review-cli`, it takes no
`--repo`/`--pr`/`--provider` flags — it operates on the current checkout,
writes files under `.wiki/`, and stops without committing; you review the
diff and commit `.wiki/` alongside your own work. `code-review-cli` reads
`.wiki/` for context when it exists, treating the code as authoritative
wherever the two disagree, so keeping the wiki current makes reviews
better-informed.

### Requirements

Same `claude` CLI / `ANTHROPIC_API_KEY` setup as `code-review-cli` above.
No `gh`/AWS credentials and no subagent plugin are needed — `wiki_cli`
doesn't check out a PR or dispatch a review subagent.

### Usage

```bash
wiki create
```

`create` inventories the repository, plans the wiki's structure, and writes
it from scratch — or fully regenerates it if `.wiki/` already exists,
rewriting what's wrong and deleting pages whose subject no longer exists.

```bash
wiki update
```

`update` instead scopes itself to what changed since the wiki's last
commit, rewriting only the affected pages; it falls back to `create`'s
from-scratch workflow if `.wiki/` has no prior commit history.

Both modes accept the same optional `--model haiku|sonnet|opus` and
`--verbose` flags as `code-review-cli` (defaults to `sonnet` when omitted —
`opus` only with `--model opus`):

```bash
wiki update --model opus --verbose
```

Both modes also add a short, idempotent pointer to `.wiki/` inside
`CLAUDE.md` or `AGENTS.md` (whichever exists; `CLAUDE.md` is created if
neither does), so a general Claude Code session working in the repository
knows to consult the wiki.

On success, a one-paragraph summary prints to stdout, followed by one line
per page written, and the process exits `0`. On failure, an error prints to
stderr and the process exits `1` (the wiki-generation run failed) or `2`
(invalid `mode` or `--model` value — rejected before Claude Code is ever
invoked).

### Wiki linting

```bash
wiki lint
```

`lint` is a third mode, and unlike `create`/`update` it never invokes
Claude Code — it's a pure, instant, zero-cost mechanical check over the
`.wiki/` pages already on disk. `create` and `update` already run it
themselves as one of their own finishing checks and fix whatever it
reports before finishing; run it directly to check `.wiki/` as it
currently stands, without triggering a new generation session — e.g. in a
pre-commit hook or CI.

It checks three things:

- **`## Sources` section** (error) — every substantive page must end with
  one, and every path it lists must exist on disk.
- **Pytest-style citations** (error) — any `` `path.py::symbol` `` citation
  must point at a real file that actually defines that `def`/`class`.
- **Header-attributed symbols** (advisory only) — under a `## Section —
  \`file.py\`` heading, a bare backtick-quoted symbol not found in that
  file is flagged as a possible stale reference. This is advisory, not an
  error, because the heuristic can't distinguish a genuinely stale
  citation from a legitimate cross-file mention inside the same section —
  it never fails the run.

`--model`/`--verbose` are parsed but have no effect on this mode. Each
finding prints as one `severity: file:line: message` line, followed by a
`N error(s), M advisory(ies)` summary. The process exits `1` if any
`error`-severity finding was reported, `0` otherwise — advisory findings
never affect the exit code.
```

New:

```
## wiki helpers

Wiki content for the repository you're currently in is written by the
`wiki-create` / `wiki-update` / `wiki-remember` skills (see `CLAUDE.md`) —
invoke with `/wiki-create` or `/wiki-update`, or by asking in plain language
(e.g. "build the wiki for this repo"). `code-review-cli` reads `.wiki/` for
context when it exists, treating the code as authoritative wherever the two
disagree, so keeping the wiki current makes reviews better-informed.

The `wiki` console script ships only two local helpers, both operating on
the current checkout. Neither invokes Claude Code.

### Wiki linting

```bash
wiki lint
```

`lint` is a pure, instant, zero-cost mechanical check over the `.wiki/`
pages already on disk. The `wiki-create` and `wiki-update` skills run it
themselves as one of their own finishing checks and fix whatever it
reports before finishing; run it directly to check `.wiki/` as it
currently stands — e.g. in a pre-commit hook or CI.

It checks three things:

- **`## Sources` section** (error) — every substantive page must end with
  one, and every path it lists must exist on disk.
- **Pytest-style citations** (error) — any `` `path.py::symbol` `` citation
  must point at a real file that actually defines that `def`/`class`.
- **Header-attributed symbols** (advisory only) — under a `## Section —
  \`file.py\`` heading, a bare backtick-quoted symbol not found in that
  file is flagged as a possible stale reference. This is advisory, not an
  error, because the heuristic can't distinguish a genuinely stale
  citation from a legitimate cross-file mention inside the same section —
  it never fails the run.

Each finding prints as one `severity: file:line: message` line, followed by
a `N error(s), M advisory(ies)` summary. The process exits `1` if any
`error`-severity finding was reported, `0` otherwise — advisory findings
never affect the exit code.
```

- [ ] **Step 7: Update `README.md`, hunk 3 — skill comparison table (lines 218-248)**

Old:

```
`wiki-create` and `wiki-update` are the exact same prompts `wiki create` and
`wiki update` send to the headless SDK session, just packaged so a normal
interactive Claude Code session can run them directly — invoke with
`/wiki-create` or `/wiki-update`, or by asking in plain language (e.g. "build
the wiki for this repo"). `wiki-remember` is a different, independent skill —
see the comparison below.

## What gets captured: `wiki_cli` vs `wiki-remember`

`.wiki/` has a second, independent writer besides this CLI: `wiki-remember`,
```

New:

```
`wiki-remember` is a different, independent skill from `wiki-create` /
`wiki-update` — see the comparison below.

## What gets captured: `wiki-create`/`wiki-update` vs `wiki-remember`

`.wiki/` has a second, independent writer besides the structural skills: `wiki-remember`,
```

Old table first column header and rows (lines 235-242):

```
| | `wiki_cli` (`create`/`update`) | `wiki-remember` (interactive Skill) |
|---|---|---|
| **Captures** | WHAT the code is — architecture, module responsibilities, data flow, invariants, entrypoints, test coverage | WHY — decisions, rejected alternatives, and rationale actually discussed in a conversation |
| **Source of truth** | Source code and tests, read directly by the headless session | The conversation itself — never independently re-derives how code behaves |
| **Trigger** | Explicit CLI command (`wiki create`/`update`), run whenever a developer chooses | Explicit user ask mid-conversation — never invoked on its own initiative |
```

New:

```
| | `wiki-create` / `wiki-update` (skills) | `wiki-remember` (interactive Skill) |
|---|---|---|
| **Captures** | WHAT the code is — architecture, module responsibilities, data flow, invariants, entrypoints, test coverage | WHY — decisions, rejected alternatives, and rationale actually discussed in a conversation |
| **Source of truth** | Source code and tests, read directly by the skill session | The conversation itself — never independently re-derives how code behaves |
| **Trigger** | Explicit skill invocation, run whenever a developer chooses | Explicit user ask mid-conversation — never invoked on its own initiative |
```

Old (lines 245-248):

```
In short: `wiki_cli` answers "what does this code do and how is it put
together," continuously re-verified against source; `wiki-remember` answers
"why did we decide this," a durable record of intent that source code alone
can't reconstruct.
```

New:

```
In short: `wiki-create` / `wiki-update` answer "what does this code do and
how is it put together," continuously re-verified against source;
`wiki-remember` answers "why did we decide this," a durable record of intent
that source code alone can't reconstruct.
```

Leave the `### Install the wiki Skills` subsection, the `### Prior art` section, and everything else in `README.md` untouched.

- [ ] **Step 8: Add the `CHANGELOG.md` entry**

Insert directly under the `# Changelog` preamble (after line 4-5, before `## [0.2.1]`):

```markdown
## [0.3.0] - 2026-09-10

### Removed

- `wiki create`, `wiki update`, and `wiki generate-skills` are gone, with `src/wiki_cli/prompts.py`, `runner.py`, `result.py`, and `skill_gen.py`. Wiki content is now written exclusively by the `wiki-create` / `wiki-update` / `wiki-remember` skills under `.claude/skills/`, which are the sole source of the skill instructions.
- `wiki` keeps two local helpers: `wiki lint` (now bare — the ignored `--model`/`--verbose` flags are gone) and `wiki install-skill` (unchanged).
```

- [ ] **Step 9: Bump the version**

In `pyproject.toml`, change `version = "0.2.1"` to `version = "0.3.0"`.

- [ ] **Step 10: Run the tests and commit docs + version**

Run: `pytest tests/ -v`
Expected: PASS — full suite green.

```bash
git add CLAUDE.md README.md CHANGELOG.md pyproject.toml
git commit -m "docs: wiki CLI ships only lint and install-skill"
```

---

### Task 6: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Full suite**

Run: `pytest tests/ -v`
Expected: PASS, full suite green.

- [ ] **Step 2: CLI surface**

Run: `python -m wiki_cli.cli --help`
Expected: usage lists only `lint` and `install-skill`.

Run: `python -m wiki_cli.cli create`
Expected: exit code 2, `invalid choice: 'create'` on stderr.

Run: `python -m wiki_cli.cli lint --help`
Expected: no `--model` / `--verbose` flags listed.

- [ ] **Step 3: Helpers still work**

Run: `python -m wiki_cli.cli install-skill --dry-run`
Expected: exit code 0, prints the would-install plan for the three skills.

- [ ] **Step 4: Commit contains only intended files**

Run: `git status --short` and `git log --oneline -6`
Expected: the only staged/committed changes from this work are the files listed in the file-structure table; the pre-existing unrelated modifications (if still present) remain uncommitted and untouched. No tag/push (release tagging stays the maintainer's call per `CLAUDE.md`).
