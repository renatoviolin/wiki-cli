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
python -m code_review_cli.cli --repo renatoviolin/purabackend --pr 29 --provider github
```

If you installed via pip (see Install above), the `code-review` console
script does the same thing and is shorter — every `python -m
code_review_cli.cli ...` example below also works as `code-review ...`:

```bash
code-review --repo renatoviolin/purabackend --pr 29 --provider github
```

An optional `--verbose` flag streams a human-readable line per SDK message to
stderr, live, as the headless Claude Code run progresses. It has no effect on
stdout, which always carries only the final review text on success.

```bash
python -m code_review_cli.cli --repo renatoviolin/purabackend --pr 29 --provider github --verbose
```

An optional `--model` flag selects the model Claude Code uses for the review,
accepting the case-insensitive aliases `haiku`, `sonnet`, or `opus`. When
omitted, Claude Code uses its own default model.

```bash
python -m code_review_cli.cli --repo renatoviolin/purabackend --pr 29 --provider github --model opus
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
python -m code_review_cli.cli --repo renatoviolin/purabackend --pr 29 --provider github --level hard
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
python -m wiki_cli.cli create
```

If you installed via pip (see Install above), the `wiki` console script
does the same thing and is shorter — every `python -m wiki_cli.cli ...`
example below also works as `wiki ...`:

```bash
wiki create
```

`create` inventories the repository, plans the wiki's structure, and writes
it from scratch — or fully regenerates it if `.wiki/` already exists,
rewriting what's wrong and deleting pages whose subject no longer exists.

```bash
python -m wiki_cli.cli update
```

`update` instead scopes itself to what changed since the wiki's last
commit, rewriting only the affected pages; it falls back to `create`'s
from-scratch workflow if `.wiki/` has no prior commit history.

Both modes accept the same optional `--model haiku|sonnet|opus` and
`--verbose` flags as `code-review-cli`:

```bash
python -m wiki_cli.cli update --model opus --verbose
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
