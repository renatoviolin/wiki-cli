# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.2.0] - 2026-08-28

### wiki_cli

- Add `wiki install-skill` — installs `.claude/skills/wiki-remember/SKILL.md` (and `.github/skills/` for Copilot/VS Code) into the current checkout from GitHub main (`renatoviolin/wiki-cli@main` via raw.githubusercontent.com). Simple interface: `wiki install-skill [--force] [--dry-run] [--target claude|copilot|all] [skill]` (default `--target all`). Supports --force, --dry-run, idempotent "already up to date" reporting.

## [0.1.0] - 2026-08-27

Initial public release. Two independent CLIs, packaged together:

### `code-review-cli`

- Validates `--repo`/`--pr`/`--provider`/`--model`/`--level` input, then hands
  off to a headless Claude Code session that checks out the PR (GitHub via
  `gh`, or CodeCommit via `aws`) and dispatches the
  `voltagent-qa-sec:code-reviewer` subagent to review it.
- `--level light|standard|hard` controls review depth: a single scoped
  subagent, a single full-scope subagent, or five specialist subagents plus a
  merging judge.
- `--model haiku|sonnet|opus` selects the model; `--verbose` streams SDK
  messages to stderr.
- Success/failure is read from the session's structured JSON output, not from
  the SDK's `is_error` flag alone, so a session that completes normally but
  fails its task (bad checkout, unresolvable repo) is reported as a failure.
- Token/cost metrics are summed across every model the run touches, including
  cache read/write tokens.

### `wiki_cli`

- `create`/`update` generate and maintain a source-grounded `.wiki/`
  knowledge base for the current checkout, under an evidence-discipline
  prompt: no symbol/field/route name may be stated unless it was read
  verbatim in source.
- `update` scopes itself to what changed since the wiki's last commit,
  falling back to a full rebuild when there's no prior wiki history.
- `create`/`update` also add a short, idempotent pointer to `.wiki/` inside
  `CLAUDE.md` or `AGENTS.md` (whichever exists; `CLAUDE.md` is created if
  neither does), so a general Claude Code session in the repo knows to
  consult the wiki.
- The interactive `wiki-remember` Skill captures decisions and rationale from
  conversation into `.wiki/decisions/`, kept deliberately separate from
  `wiki_cli`'s own evidence-gated regeneration.
- `code-review-cli`'s review prompt reads `.wiki/` for context when present,
  treating the code as authoritative over the wiki wherever they disagree.
