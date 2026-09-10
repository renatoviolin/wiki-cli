# `wiki install-skill` installs everywhere with no parameters — design

Date: 2026-09-10
Status: approved, awaiting implementation plan

## Background

`wiki install-skill` today is repo-local only (`src/wiki_cli/skills.py:41-60`):
dest root is `target_dir or os.getcwd()` with bases `.claude/skills` and
`.github/skills`, selected by `--target claude|copilot|all`. `src/wiki_cli/cli.py:16-20`
exposes `install-skill [skill] [--force] [--dry-run] [--target]`, bare meaning the
`DEFAULT_SKILLS` bundle (`wiki-remember`, `wiki-create`, `wiki-update`).

There is no global install. Users must re-run per checkout, and the wiki skills are
unavailable in fresh repos despite being project-independent instructions.

Global skill locations (verified against current docs):

| Agent | Project | Personal / global |
|---|---|---|
| Claude Code | `.claude/skills/<name>/SKILL.md` | `~/.claude/skills/<name>/SKILL.md` |
| Copilot | `.github/skills/`, `.claude/skills/`, `.agents/skills/` | `~/.copilot/skills/`, `~/.claude/skills/`, `~/.agents/skills/` |

`~/.claude/skills/` is read by both agents. `~/.copilot/skills/` is Copilot-only.
Local `~/.claude/skills/` already holds 5 unrelated skills; `~/.copilot/` does not
exist yet on this machine.

## Goal

Bare `wiki install-skill` with no parameters installs the full bundle everywhere it
is needed, so one invocation covers the current checkout and all future checkouts
for both Claude Code and Copilot.

## Non-goals

- No changes to `code_review_cli`.
- No changes to `.claude/skills/*/SKILL.md` content or `lint.py`.
- No new flags, no selective install, no `--dry-run` preview in this change.
- No tag/push; release tagging stays the maintainer's call.

## Decision

Approach A with no parameters was approved over a `--global`/`--scope` flag
(extra surface for a one-time setup command) and over docs-only manual copy (no
idempotency, drifts on updates).

Bare `wiki install-skill` installs all three `DEFAULT_SKILLS` to all four roots:

1. `<cwd>/.claude/skills/<name>/SKILL.md`
2. `<cwd>/.github/skills/<name>/SKILL.md`
3. `~/.claude/skills/<name>/SKILL.md`
4. `~/.copilot/skills/<name>/SKILL.md`

That is 12 files. `~/.claude/skills` alone would technically cover both agents, but
writing both home dirs mirrors the existing repo `all` semantics (explicit over
clever) and survives either agent narrowing its discovery set later.

Existing-file policy is sync: fetch each skill once from github `main`, compare
bytes per dest — missing or differs gets written, identical is skipped. The command
never fails on "already exists" and never prompts.

## Changes

### `skills.py`

- Remove `skill`, `target_dir`, `force`, `dry_run`, `target` parameters. Single entry
  point over the fixed bundle, e.g. `install_all()` returning per-skill results;
  keep the `InstallResult` dataclass shape (success/message/error/skipped/dest).
- Fixed roots: repo bases `.claude/skills` + `.github/skills` under `Path.cwd()`,
  global bases `Path.home() / ".claude/skills"` and `Path.home() / ".copilot/skills"`.
  Resolve `Path.home()` at call time so tests can redirect `HOME`.
- Fetch each skill once via the existing `_github_raw_url`/`_fetch_github` path
  (`renatoviolin/wiki-cli@main`). A fetch failure fails that skill only; the other
  two still run.
- Per dest: `mkdir(parents=True, exist_ok=True)`, byte-compare, write on
  missing/differs. A write failure fails that skill with the dest in `error`.
- Success message stays one line per skill naming the installed/verified dests;
  `skipped=True` only when all four dests were already up to date.

### Slimmed CLI

- `cli.py` keeps the `install-skill` subparser but with no positional and no
  `--force`/`--dry-run`/`--target` flags: literally `wiki install-skill`.
- Loop over the bundle result, print each message to stdout, `error: ...` to
  stderr per failure, exit 1 if any skill failed else 0. Stdout contract for
  `install-skill` becomes "one summary line per skill, nothing else".

### Tests

- Rewrite `tests/test_wiki_skills.py`: fetch-and-write to all four roots (with
  `HOME` redirected to `tmp_path`), identical-bytes skip, differs-overwrites,
  404 fails that skill only, invalid skill name rejected before any write.
- Rewrite `tests/test_wiki_cli_install_skill.py`: bare invocation installs the
  bundle, reports per-skill errors to stderr with exit 1 while continuing the
  bundle, exit 0 on full success.
- Keep `tests/test_wiki_cli.py` `lint` cases; update its `install-skill` cases for
  the bare invocation. Success: `pytest tests/ -v` green.

### Docs + release

- `README.md`: replace `install-skill` usage with the bare everywhere behavior and
  the four destination roots.
- `CHANGELOG.md`: entry describing the breaking CLI simplification and the new
  global coverage.
- `pyproject.toml`: version `0.3.0` → `0.4.0` (breaking CLI surface).
- `CLAUDE.md`: update the `wiki_cli` helpers paragraph (`install-skill` fetches the
  bundle to repo + home, no flags).

## Verification

1. `pytest tests/ -v` — full suite green, with `HOME` redirection proving no test
   touches the real home directory.
2. `wiki install-skill --help` shows no options.
3. Fresh `tmp` dir as cwd with `HOME=tmp/home`: `wiki install-skill` creates all 12
   files; second run reports up to date and writes nothing (mtime check).
4. `wiki lint` behavior unchanged.

## Risks

- Writes outside the repo (`$HOME`) for the first time; mitigated by resolving
  `Path.home()` at call time, creating only `<skill>/SKILL.md` leaves, and tests
  redirecting `HOME`.
- No `--dry-run` preview anymore; mitigated by the byte-compare making reruns safe
  and output stating what was written vs already current.
- Selective install (`wiki install-skill wiki-remember`, `--target claude`) disappears;
  accepted per explicit request — the bundle is three small files and the command is
  idempotent.
- First global write creates `~/.copilot/skills/` on machines without it; intended.
