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
python -m wiki_cli.cli lint
```

Five modules under `src/wiki_cli/`: `prompts.py`, `runner.py`, `cli.py`, `result.py`, and
`lint.py` (the mechanical self-checker described below, wired into `cli.py` as a third
mode alongside `create`/`update`).

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

Both modes share six section blocks that are the actual content contract for every page
in this wiki:

- **`_HARD_CONSTRAINTS`** — write only under `.wiki/`, with one carved-out exception for
  `_WIKI_POINTER` below; never read/document secrets, credentials, or `.env` values; never
  `git add`/`commit`/`push`; use targeted glob/grep/reads, not whole-tree scans.
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
- **`_WIKI_POINTER`** — the one instruction in the prompt that targets a file outside
  `.wiki/` (see below).

### The `CLAUDE.md`/`AGENTS.md` pointer — `_WIKI_POINTER`

Both `create` and `update` end with an explicit, narrow exception to "write only under
`.wiki/`": after writing the wiki, the session checks the repository root for `CLAUDE.md`,
falling back to `AGENTS.md` if that doesn't exist, and edits whichever one exists (or
creates `CLAUDE.md` if neither does). Before touching it, the session must check whether
the file already references `.wiki/` anywhere — if it does, `_WIKI_POINTER` requires
leaving the file untouched rather than adding a second pointer, which is why running
`update` against *this* repository's own `CLAUDE.md` (which already describes `wiki-cli.md`
and `code-review-cli.md` in detail, including several `.wiki/` references) is a no-op on
that file. When the file has no existing `.wiki/` reference, the instruction is to insert
one short paragraph (two to three sentences) near the top, saying the repository has a
source-grounded knowledge base starting at `.wiki/index.md` that should be consulted before
exploring the codebase from scratch, and that code outranks the wiki where they disagree —
without rewriting or reformatting the rest of the file. If the session creates `CLAUDE.md`
from nothing, `_WIKI_POINTER` restricts it to a top-level heading plus that one paragraph,
nothing else. Any `CLAUDE.md`/`AGENTS.md` path touched this way must be included in
`pages_written` alongside the `.wiki/` pages, per `_WIKI_POINTER` and
`_SHARED_PREAMBLE`'s reply-contract instructions. Covered by
`tests/test_wiki_prompts.py::test_build_prompt_points_claude_or_agents_md_at_wiki` and four
sibling tests asserting the idempotency check, the "short paragraph, not a rewrite"
constraint, the explicit hard-constraint exception, and the `pages_written` inclusion.

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

`main(argv)` parses one positional `mode` argument constrained to `create`/`update`/`lint`
via argparse `choices` (invalid mode exits `2` without calling `run_wiki` — no separate
`validation.py` module exists here, since `mode` and `--model` are the only inputs and
`choices`/an inline alias map cover both). For `mode == "lint"`, `main` short-circuits
before any model resolution and returns `_print_lint_report(lint_wiki(os.getcwd()))`
directly — `run_wiki` is never called, and `--model`/`--verbose` are parsed but ignored for
this mode. For `create`/`update`, `--model` resolves through this module's own
`_MODEL_ALIASES` dict — a separate literal from, but identical in content to,
`code-review-cli.md`'s `validation._MODEL_ALIASES` (`haiku`/`sonnet`/`opus`). `_print_metrics`
writes a `[metrics] mode=... cost=$... ...` line to stderr unconditionally. On success,
`result.text` (the summary) prints to stdout, followed by one line per entry in
`result.pages_written`; on failure, `result.error_message` goes to stderr and `main`
returns `1`.

## Wiki linting — `lint.py`

`lint_wiki(repo_root)` is a mechanical, non-LLM checker over every `.md` file already
written under `.wiki/` (`_iter_wiki_pages` walks the tree and sorts the paths), returning a
list of `LintFinding(file, line, severity, message)`. It exists so `_FINISHING_CHECKS` in
`prompts.py` has something to actually run rather than just tell the session to
self-report: both `create` and `update` end by instructing the session to run
`python -m wiki_cli.cli lint` (or the `wiki lint` console script) and fix every error before
finishing. `cli.py`'s `main` wires it in as the `lint` mode, via `_print_lint_report`, which
prints one `{severity}: {file}:{line}: {message}` line per finding plus a trailing
`N error(s), M advisory(ies)` summary, and returns exit code `1` if any finding is
`error`-severity, `0` otherwise — advisories never fail the run.

Three independent checks, run per page:

- **Sources section** (error) — every page except `index.md` and anything under
  `.wiki/decisions/` must contain a `## Sources` heading; the section must contain at least
  one backtick-quoted path (`` `src/pkg/mod.py` ``-shaped); and every such path must exist
  on disk relative to `repo_root`. This directly enforces `_PAGE_CONTRACT`'s "at least five
  distinct source files" rule mechanically, though the count itself isn't checked — only
  that the section exists and every path it lists is real.
- **Pytest-style citations** (error) — anywhere on any page, a citation shaped like a
  pytest node id (a `.py` path, `::`, then an identifier) is checked two ways: the file
  must exist, and a `def `/`class ` matching the identifier must appear in that file's text
  (a regex search, not an AST parse — it cannot tell a citation is technically valid but
  points at the wrong kind of symbol).
- **Header-attributed bare symbols** (advisory only) — a heading shaped like
  `## Section — \`file.py\`` (`_HEADER_WITH_FILE_RE`) sets an "active file" for every line
  until the next heading of any level; any backtick-quoted bare identifier in that span
  (skipping lines that already contain a `::` pytest-style citation) is flagged if the
  literal string doesn't appear anywhere in the attributed file's text. A same-directory
  bare filename with no path separator is resolved by an unambiguous search under `src/`
  (`_resolve_bare_filename`); an ambiguous or missing match disables the check for that
  header instead of guessing. A stoplist (`_COMMON_KEYWORD_STOPLIST`) excludes common
  non-symbol tokens (`haiku`, `create`, `mode`, `json`, ...) from ever being flagged, and
  each stale symbol is only reported once per attributed file. Because the heuristic only
  matches the identifier string against raw file text — not scope — it can't distinguish a
  genuinely stale reference from a symbol mentioned in prose while discussing a different
  file under the same header; that's why it's advisory rather than error severity.

`tests/test_wiki_lint.py` covers all three checks plus the `index.md`/`decisions/`
exemption and the stoplist; `tests/test_wiki_cli.py` covers `lint` mode's exit codes
(`test_main_lint_mode_does_not_invoke_run_wiki`,
`test_main_lint_reports_errors_and_returns_one`,
`test_main_lint_advisory_only_returns_zero`).

## Where to make a change

| Change | Start here | Validate with |
|---|---|---|
| What a page must cover, structure rules, evidence requirements | `prompts.py`'s section constants (`_EVIDENCE_DISCIPLINE`, `_PAGE_CONTRACT`, `_STRUCTURE_RULES`, ...) | `pytest tests/test_wiki_prompts.py -v` |
| `create` vs `update` workflow steps | `prompts.py`'s `_CREATE_INSTRUCTIONS`/`_UPDATE_INSTRUCTIONS` | `pytest tests/test_wiki_prompts.py -v` |
| The `CLAUDE.md`/`AGENTS.md` pointer behavior | `prompts.py`'s `_WIKI_POINTER` | `pytest tests/test_wiki_prompts.py -v` |
| SDK invocation, metrics, cwd handling | `runner.py` | `pytest tests/test_wiki_runner.py -v` |
| CLI flags, mode handling, stdout/stderr contract | `cli.py` | `pytest tests/test_wiki_cli.py -v` |
| A false-positive/negative in the mechanical `lint` checks | `lint.py`'s `_check_sources_section`/`_check_pytest_citations`/`_check_header_attributed_symbols` | `pytest tests/test_wiki_lint.py -v` |

Full suite: `pytest tests/ -v`; this package's tests are the `test_wiki_*.py` files
alongside `code-review-cli.md`'s tests in the same `tests/` directory.

## Sources

- `src/wiki_cli/prompts.py` (`build_prompt`, `_CREATE_INSTRUCTIONS`, `_UPDATE_INSTRUCTIONS`, `_WIKI_POINTER`, `_FINISHING_CHECKS`)
- `src/wiki_cli/runner.py` (`run_wiki`, `_run_wiki_async`)
- `src/wiki_cli/cli.py` (`main`, `_print_lint_report`, `build_arg_parser`)
- `src/wiki_cli/lint.py` (`lint_wiki`, `LintFinding`, `_check_sources_section`, `_check_pytest_citations`, `_check_header_attributed_symbols`)
- `src/wiki_cli/result.py` (`WikiResult`)
- `tests/test_wiki_lint.py`
- `tests/test_wiki_cli.py`
- `tests/test_wiki_prompts.py`
