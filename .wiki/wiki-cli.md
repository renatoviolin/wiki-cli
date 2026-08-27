# wiki-cli

`wiki_cli` generates and maintains the `.wiki/` knowledge base you are reading right now.
It is fully independent from `code-review-cli.md`'s package — **zero imports between
them** — sharing only this repository. It takes no repo/provider arguments: it operates on
whatever repository the process is currently inside, writes files under `.wiki/`, and
stops without committing; the developer commits `.wiki/` alongside their own work. The
only coupling in the other direction is a convention read by `code-review-cli.md`'s
prompt: if `.wiki/` happens to exist in the checked-out PR repo, the review session reads
it for context.

```bash
python -m wiki_cli.cli create|update [--model haiku|sonnet|opus] [--verbose]
```

Four modules under `src/wiki_cli/`.

## Prompt construction — `prompts.py`

`build_prompt(mode)` assembles `_SHARED_PREAMBLE` from labelled section constants plus one
mode-specific workflow block from `_MODE_INSTRUCTIONS`. The preamble has the session
resolve its own repository root (`git rev-parse --show-toplevel`) and treat every path as
relative to that root — the wrapper itself never runs `git`. If the current directory
isn't inside a git repository, the session is told to stop and reply with the failure JSON
shape immediately.

**`create`** (`_CREATE_INSTRUCTIONS`) is a seven-step, plan-before-writing workflow:
Inventory the repo's services/entrypoints/public surfaces/tests → Rank by runtime
importance and other signals → Group related files into systems (not directories) → write
the complete planned structure to `.wiki/_plan.md` before any page → satisfy the evidence
gate per planned page → write pages, then `.wiki/index.md` last → delete `.wiki/_plan.md`
(scaffolding, not documentation). If `.wiki/` already exists, `create` is a full
regeneration: keep the directory, rewrite what's wrong, delete pages whose subject no
longer exists.

**`update`** (`_UPDATE_INSTRUCTIONS`) instead scopes to what changed: find the wiki's last
commit with `git log -1 --format=%H -- .wiki/`, diff that commit against `HEAD` with
`git diff --name-status`, and read the actual diffs (not just filenames) for the affected
areas. If there's no prior wiki commit, it falls back to the same from-scratch workflow as
`create`. It maps changes to the pages they affect (including a page describing a system
one hop away, if a contract between two systems moved), re-satisfies the evidence gate
against current source rather than trusting what a page already claims, updates
`.wiki/index.md`'s routing table if the page/entrypoint set changed, and fixes any diagram
that no longer matches the code in the same edit as the surrounding prose — a stale
diagram is a false claim, not existing structure worth preserving.

Both modes share five section blocks that are the actual content contract for every page
in this wiki:

- **`_HARD_CONSTRAINTS`** — write only under `.wiki/`; never read/document secrets,
  credentials, or `.env` values; never `git add`/`commit`/`push`; use targeted
  glob/grep/reads, not whole-tree scans.
- **`_EVIDENCE_DISCIPLINE`** — the load-bearing section (see below).
- **`_PAGE_CONTRACT`** — what a substantive page must cover: what/why, owning
  entrypoints/symbols, dependencies and data flow, invariants, extension points, covering
  tests, the narrowest validation command, and scope boundaries.
- **`_STRUCTURE_RULES`** — `.wiki/index.md` as entrypoint with a task-routing table;
  one page per substantial component; decompose large components by domain; no directory
  tree copies; one canonical home per concept.
- **`_WRITING_STYLE`**, **`_DIAGRAMS`**, **`_FINISHING_CHECKS`** — dense prose over bare
  link lists; Mermaid diagrams only where every element is source-backed; and, before
  finishing, reconcile against the plan, re-verify specific claims, simulate navigating a
  couple of realistic changes starting only from `index.md`, and remove low-value stubs.

The reply contract, checked by `_RESULT_SCHEMA`, is
`{"success": bool, "summary": str, "pages_written": [str], "failure_reason": str}` —
one field more than `code-review-cli.md`'s schema (`pages_written`), and `additionalProperties: false`
is asserted directly by `tests/test_wiki_prompts.py::test_result_schema_is_strict`.

### Why the evidence-discipline section is written the way it is

`_EVIDENCE_DISCIPLINE` requires inspecting, for each substantial component: its entrypoint
and composition, its primary implementation, its important public types/schemas/config,
any persistence/cache/queue/state handling, at least one caller upstream and one
dependency downstream, and its most representative tests — before drafting any prose.
Manifests, READMEs, and import lines are *discovery* evidence (where to look), not
sufficient evidence for behavior claims. It forbids stating any type/field/route/command
name that wasn't read verbatim in source, and requires citing evidence as repository path
plus symbol name (e.g. `internal/api/handler.go` (`HandleUpload`)) rather than `file:line`
— line numbers go stale within days, making a stale line reference itself a false claim; an
earlier prompt revision required `file:line` and was reverted.

This rule exists because of a measured failure mode, not a stylistic preference: a review
of OpenWiki (LangChain's similar tool) run against a real 63.7k-LOC Go repository found
architecture/behavior descriptions substantially accurate, but roughly half the sampled
*identifier* detail invented — a nonexistent type name, a wrong field name, a field that
didn't exist at all — all stated in the same confident tone as correct content. Full
evidence trail: `design-history.md`.

## Execution — `runner.py`

`run_wiki(mode, verbose=False, model=None)` has the same overall shape as
`code-review-cli.md`'s `run_review` — same `ClaudeAgentOptions` fields
(`permission_mode="bypassPermissions"`, `max_turns=150`,
`setting_sources=["user", "project"]`, `output_format` forcing `_RESULT_SCHEMA`), same
`is_error` vs `structured_output.success` two-gate failure handling, same
`model_usage`-summing for token/cost metrics, same duck-typed `_log_verbose_message` for
`--verbose`, same never-raises contract around `asyncio.run`. See that page's sequence
diagram — it applies here unchanged except for one deliberate divergence:

**`options.cwd` is `os.getcwd()`, with no temp workspace and no cleanup.** Unlike
`code-review-cli.md`'s runner, which isolates each PR review in a fresh temp directory it
deletes on success, `run_wiki` runs directly in the developer's real checkout because it is
*supposed* to write into it — that's the whole point of the tool
(`tests/test_wiki_runner.py::test_run_wiki_runs_in_current_directory_not_a_temp_workspace`
asserts `options.cwd == os.getcwd()`).

On success, `run_wiki` returns a `WikiResult` with `text` set from `structured_output["summary"]`
and `pages_written` from `structured_output["pages_written"]`.

## CLI entrypoint — `cli.py`

`main(argv)` parses one positional `mode` argument constrained to `create`/`update` via
argparse `choices` (invalid mode exits `2` without calling `run_wiki` — no separate
`validation.py` module exists here, since `mode` and `--model` are the only inputs and
`choices`/an inline alias map cover both). `--model` resolves through this module's own
`_MODEL_ALIASES` dict — a separate literal from, but identical in content to,
`code-review-cli.md`'s `validation._MODEL_ALIASES` (`haiku`/`sonnet`/`opus`). `_print_metrics`
writes a `[metrics] mode=... cost=$... ...` line to stderr unconditionally. On success,
`result.text` (the summary) prints to stdout, followed by one line per entry in
`result.pages_written`; on failure, `result.error_message` goes to stderr and `main`
returns `1`.

## Where to make a change

| Change | Start here | Validate with |
|---|---|---|
| What a page must cover, structure rules, evidence requirements | `prompts.py`'s section constants (`_EVIDENCE_DISCIPLINE`, `_PAGE_CONTRACT`, `_STRUCTURE_RULES`, ...) | `pytest tests/test_wiki_prompts.py -v` |
| `create` vs `update` workflow steps | `prompts.py`'s `_CREATE_INSTRUCTIONS`/`_UPDATE_INSTRUCTIONS` | `pytest tests/test_wiki_prompts.py -v` |
| SDK invocation, metrics, cwd handling | `runner.py` | `pytest tests/test_wiki_runner.py -v` |
| CLI flags, mode handling, stdout/stderr contract | `cli.py` | `pytest tests/test_wiki_cli.py -v` |

Full suite: `pytest tests/ -v`; this package's tests are the `test_wiki_*.py` files
alongside `code-review-cli.md`'s tests in the same `tests/` directory.
