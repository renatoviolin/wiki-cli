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
- The `voltagent-qa-sec:code-reviewer` subagent (from the `voltagent-subagents`
  plugin) installed in the target environment — this tool does not define or
  install that subagent, it only dispatches it by name

`--provider` accepts exactly two values:

- `github`
- `codecommit`

## Install

```bash
pip install -e .
```

## Usage

```bash
python -m code_review_cli.cli --repo renatoviolin/purabackend --pr 29 --provider github
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
