# code-review-cli

Headless code review for pull requests, powered by dispatching the
`voltagent-qa-sec:code-reviewer` subagent from within headless Claude Code.
This CLI does not review code itself — it validates input, builds a task
prompt, and hands off to headless Claude Code, which checks out the PR itself
(via `gh`/`git`/`aws`) and dispatches that subagent to run the review.

## Requirements

- Python 3.11+
- The `claude` CLI installed and authenticated (`ANTHROPIC_API_KEY` set) in
  this environment
- `gh` authenticated (for `--provider github`) or AWS credentials/region
  configured (for `--provider codecommit`)
- The `voltagent-qa-sec` plugin installed in the target environment — this
  tool does not define or install it, it only dispatches its subagents
  (`code-reviewer`, and at `--level hard` also `security-auditor`,
  `performance-engineer`, `architect-reviewer`, `qa-expert`) by name:

  ```bash
  claude plugin marketplace add VoltAgent/awesome-claude-code-subagents
  claude plugin install voltagent-qa-sec@voltagent-subagents
  ```

`--provider` accepts exactly two values:

- `github`
- `codecommit`

## Install

From a local checkout:

```bash
pip install -e .
```

Directly from GitHub, always the latest commit on `main`:

```bash
pip install git+https://github.com/renatoviolin/wiki-cli.git
```

Either install exposes two console scripts from the same `pyproject.toml`:
`code-review` (documented below) and `wiki`, which generates and maintains
the `.wiki/` knowledge base this repo's review prompt reads for context —
see `.wiki/wiki-cli.md` or `CLAUDE.md` for its usage. See
[CHANGELOG.md](CHANGELOG.md) for what changed in each release.

## Usage

```bash
code-review --repo renatoviolin/wiki-cli --pr 29 --provider github
```

An optional `--verbose` flag streams a human-readable line per SDK message to
stderr, live, as the headless Claude Code run progresses. It has no effect on
stdout, which always carries only the final review text on success.

```bash
code-review --repo renatoviolin/wiki-cli --pr 29 --provider github --verbose
```

An optional `--model` flag selects the model Claude Code uses for the review,
accepting the case-insensitive aliases `haiku`, `sonnet`, or `opus`. When
omitted, Claude Code uses its own default model.

```bash
code-review --repo renatoviolin/wiki-cli --pr 29 --provider github --model opus
```

An optional `--level` flag controls review depth, accepting `light`,
`standard`, or `hard`. `standard` is the default and reviews the PR with a
single subagent. `light` narrows that same subagent's task to only
high-confidence correctness and security findings, and — unless `--model` is
also given explicitly — defaults the model to `haiku`. `hard` dispatches five
specialized subagents (code review, security, performance, architecture, test
coverage) and a final judge subagent that merges their findings and drops
anything that doesn't survive an adversarial recheck.

```bash
code-review --repo renatoviolin/wiki-cli --pr 29 --provider github --level hard
```

On success, the review text is printed to stdout and the process exits 0.
On failure (invalid input, or Claude Code failing to complete the review),
an error is printed to stderr and the process exits non-zero (`2` for input
validation failures, `1` for a failed review run). A failed run leaves its
temporary workspace in place on disk rather than deleting it, so it can be
inspected for post-mortem debugging.

## Scope

This CLI intentionally does not: trigger from CI, post PR comments, produce
structured/JSON output, redact secrets/PII, or define the review's actual
criteria (it dispatches the pre-existing `voltagent-qa-sec:code-reviewer`
subagent by name). These are deferred to future work.

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
`--verbose` flags as `code-review-cli`:

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

### Install the wiki-remember Skill

```bash
wiki install-skill                                    # both Claude + Copilot
wiki install-skill --target claude                    # only .claude/skills/
wiki install-skill --target copilot                   # only .github/skills/ (VS Code)
wiki install-skill --dry-run
wiki install-skill --force
wiki install-skill wiki-remember --force --target all
```

Copies the `wiki-remember` skill from `renatoviolin/wiki-cli` main branch
(`raw.githubusercontent.com`) into the current checkout. By default installs
to both **Claude Code** (`./.claude/skills/wiki-remember/SKILL.md`) and
**GitHub Copilot / VS Code** (`./.github/skills/wiki-remember/SKILL.md` —
the `SKILL.md` format is identical for both agents; VS Code also discovers
`.claude/skills/` but the `.github/` copy makes it explicit for Copilot).
Use `--target claude|copilot|all` to restrict, `--dry-run` to preview without
writing, and `--force` to overwrite an existing file. The skill is updated
without needing a `pip install` bump — it always fetches the latest `SKILL.md`
from GitHub `main`. If the destination file exists and is identical, the
command reports "already up to date"; if it exists and differs without
`--force`, it fails with "already exists (use --force)".

## What gets captured: `wiki_cli` vs `wiki-remember`

`.wiki/` has a second, independent writer besides this CLI: `wiki-remember`,
an interactive Claude Code Skill (`.claude/skills/wiki-remember/SKILL.md`)
that captures a decision or rationale from the *current conversation* on
explicit request (e.g. "remember this in the wiki") — it never runs
proactively, and it's not a `wiki_cli` mode. Both write under `.wiki/`, but
they capture fundamentally different kinds of knowledge, verified
differently:

| | `wiki_cli` (`create`/`update`) | `wiki-remember` (interactive Skill) |
|---|---|---|
| **Captures** | WHAT the code is — architecture, module responsibilities, data flow, invariants, entrypoints, test coverage | WHY — decisions, rejected alternatives, and rationale actually discussed in a conversation |
| **Source of truth** | Source code and tests, read directly by the headless session | The conversation itself — never independently re-derives how code behaves |
| **Trigger** | Explicit CLI command (`wiki create`/`update`), run whenever a developer chooses | Explicit user ask mid-conversation — never invoked on its own initiative |
| **Where it writes** | `.wiki/*.md` structural pages (one per component/system) plus `index.md`'s task-routing table | One dated file per decision under `.wiki/decisions/<category>/`, plus one row in `index.md`'s "Decisions & rationale" table |
| **Verification** | Evidence discipline (must read the entrypoint, implementation, callers, and tests before writing) plus a mechanical `wiki lint` pass (checks every page ends with a real `## Sources` section and every code citation resolves) — both enforced before the session can finish | A quick sanity check against an obviously-relevant existing page, plus a mechanical grep confirming any cited symbol exists — no full evidence-discipline pass, and it must not independently assert how code behaves |
| **Regenerates/rewrites** | Yes — `update` re-derives affected pages from current source every run; `create` fully regenerates | No — append-only. A changed decision gets a new dated file; the old one's `status` flips to `superseded`, never edited or deleted |
| **Example finding** | "`is_error=False` does not mean the review succeeded. A session can complete normally while the underlying task failed (bad checkout, unresolvable repo). Real success/failure comes from `structured_output.success` — checked as a second, independent gate after `is_error` — not from `is_error` alone." (`.wiki/code-review-cli.md`, verified against `runner.py`'s `_run_review_async`) | "The flat log was rejected because it doesn't scale well once many decisions accumulate. Grouping by existing structural topic pages was rejected because a conversation-derived decision doesn't always map cleanly onto one existing structural page." (`.wiki/decisions/wiki-remember-design/2026-08-27-decision-storage-layout.md` — itself later superseded, `status` flipped in place) |

In short: `wiki_cli` answers "what does this code do and how is it put
together," continuously re-verified against source; `wiki-remember` answers
"why did we decide this," a durable record of intent that source code alone
can't reconstruct.

### Prior art that shaped this design

- **OpenWiki** (LangChain) — the "LLM Wiki" pattern productized: a CLI that
  writes a wiki directory, updates `AGENTS.md`/`CLAUDE.md`, and re-runs
  incrementally against git diffs. Running OpenWiki 0.3.3 against a real
  63.7k-LOC Go repository found architecture/behavior claims substantially
  accurate, but roughly half the sampled *identifier*-level detail invented
  — the direct source of `wiki_cli`'s evidence-discipline rule against
  naming any symbol not read verbatim in source, and of citing evidence as
  path-plus-symbol rather than `file:line`.
- **AGENTS.md** — an open convention (60k+ repos, 25+ tools, Linux
  Foundation stewardship) for giving coding agents repo-specific
  instructions. Inspired `_WIKI_POINTER`: writing `.wiki/`'s existence into
  `CLAUDE.md`/`AGENTS.md` so a general-purpose agent session, not just this
  CLI's own review flow, knows to consult it.
- **ADRs** (Nygard / MADR format) — lightweight, git-tracked
  Architecture Decision Records, in ThoughtWorks' *Adopt* ring since 2018.
  Inspired `wiki-remember`'s decision frontmatter (`status`, `supersedes`,
  `captured`) over a bespoke schema.
- **"Keyword search is all you need"** (AAAI 2026, arXiv:2602.23368) — found
  agentic keyword search reaches >90% of RAG performance with no vector
  database, corroborating the choice to skip embeddings/vector search
  entirely in favor of plain grep/read tools.
- **An arXiv preprint on "context rot"** (2606.09090) — found that stale
  AI-configuration artifacts can *degrade* agent performance versus having
  no file at all, because agents tend to follow them literally rather than
  reading skeptically. Part of why this design stayed deliberately simple —
  plain Markdown, human-reviewed before commit — instead of adding
  confidence-tag metadata that would look authoritative even when stale.
- **Rationale-mining literature** (DRMiner, ArchISMiner —
  arXiv:2510.21966, arXiv:2405.19623) — validates mining decision rationale
  from development history as a real, under-served niche, corroborating
  `wiki-remember`'s focus on the `decisions/` layer specifically.

Full research trail: `docs/second-brain-alternatives-review.md` and
`.wiki/design-history.md`.
