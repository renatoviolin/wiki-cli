# Remove wiki-cli headless commands (keep lint + install-skill) — design

Date: 2026-09-10
Status: approved, awaiting implementation plan

## Background

`wiki_cli` currently exposes five `wiki` subcommands: `create`, `update`
(headless Claude Agent SDK runs driven by `prompts.py`), `lint` (local
mechanical checks), `install-skill` (fetch skills from github main), and
`generate-skills` (dev-only regen of `wiki-create`/`wiki-update` SKILL.md from
`prompts.py` via `skill_gen.py`).

The `wiki-create` / `wiki-update` / `wiki-remember` skills under
`.claude/skills/` are now available to all agents and are the workflow. The
headless CLI path is redundant, and `skill_gen.py`'s verbatim-wrap assumption
is already broken: the checked-in SKILL.md files contain ~150 lines with no
source in `prompts.py`, so running `generate-skills` would destroy the
improved skill instructions.

## Goal

Remove the headless wiki commands so the skills are the single workflow.
Keep the two local helpers agents still need: `lint` and `install-skill`.
`.claude/skills/` becomes the sole source of skill instructions.

## Non-goals

- No changes to `code_review_cli`.
- No changes to `.claude/skills/*.md` content in this change (byte-identical).
- No changes to `lint.py` or `skills.py` behavior.
- No tag/push; release tagging stays the maintainer's call.

## Decision

Approach A (slim the package) was approved over full-package delete (needless
churn) and deprecation shims (dead code + dead tests to maintain). Anyone
scripting `wiki create` breaks immediately; accepted because the skills are
available to all agents.

## Changes

### Deletion boundary

Delete: `src/wiki_cli/prompts.py`, `src/wiki_cli/runner.py`,
`src/wiki_cli/result.py` (only consumed by the removed runner/CLI metrics
path), `src/wiki_cli/skill_gen.py`.
Keep: `src/wiki_cli/cli.py` (slimmed), `src/wiki_cli/lint.py`,
`src/wiki_cli/skills.py`, `src/wiki_cli/__init__.py`.

### Slimmed CLI

- `cli.py` keeps only `lint` and `install-skill` subparsers.
- `lint` becomes bare (`wiki lint`, no `--model`/`--verbose`; today those flags
  are accepted but ignored).
- `install-skill` args unchanged (`skill` positional, `--force`, `--dry-run`,
  `--target`).
- Delete `_MODEL_ALIASES`, `_print_metrics`, the `run_wiki` import, and the
  `create`/`update`/`generate-skills` branches.
- `pyproject.toml` keeps the `wiki` entrypoint; `claude-agent-sdk` dependency
  stays (still required by `code_review_cli`).

### Tests

- Delete: `tests/test_wiki_prompts.py`, `tests/test_wiki_runner.py`,
  `tests/test_wiki_skill_gen.py`, `tests/test_wiki_cli_generate_skills.py`,
  plus the `create`/`update` cases in `tests/test_wiki_cli.py`.
- Keep (updating the `lint` cases for the bare no-flag invocation):
  `tests/test_wiki_lint.py`, `tests/test_wiki_skills.py`,
  `tests/test_wiki_cli_install_skill.py`, and the `lint`/`install-skill` cases
  in `tests/test_wiki_cli.py`.
- Success: `pytest tests/ -v` green.

### Docs + release

- `CLAUDE.md`: rewrite the `wiki_cli` architecture section (two helpers +
  slim CLI; drop prompts/runner/result/skill_gen claims and anything
  contradicting the shipped skills).
- `README.md`: remove `wiki create|update|generate-skills` usage.
- `CHANGELOG.md`: entry describing the removal.
- `pyproject.toml`: version `0.2.1` → `0.3.0` (breaking CLI surface).
- Working tree already has unrelated uncommitted changes (skills, prompts);
  the implementation commit must not sweep those in.

## Verification

1. `pytest tests/ -v` — full suite green.
2. `wiki --help` shows only `lint` and `install-skill`.
3. `wiki lint` runs mechanical checks; `wiki install-skill --dry-run` prints
   the install plan.
4. `wiki create` / `wiki update` / `wiki generate-skills` exit non-zero via
   argparse (unknown subcommand).

## Risks

- External scripts calling `wiki create|update` fail hard; mitigated by the
  skills being universally available.
- Stale `Runs wiki_cli's ... workflow` wording in the checked-in SKILL.md
  files now refers to a removed CLI; deliberately left for a separate skill
  cleanup since `.claude/skills/` is byte-frozen in this change.
