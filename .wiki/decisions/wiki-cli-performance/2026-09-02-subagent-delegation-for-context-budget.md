---
type: decision
category: wiki-cli-performance
status: active
supersedes: null
captured: 2026-09-02
---

# Delegate wiki create/update research to subagents to avoid token-burn from missing context compaction

A real `wiki create` run against a Go backend repo hit `cache_read_tokens=25,270,456`
across 65 turns and exhausted an entire 5-hour Claude session limit in under 10 minutes,
even though the run itself was only ~15 minutes of wall clock and ~$18.55 of API cost.

Root cause: the Claude Agent SDK's `ClaudeAgentOptions` (used by
`src/wiki_cli/runner.py`'s `_run_wiki_async`) exposes no context-compaction knob —
confirmed by inspecting the installed SDK's dataclass fields directly, not just its docs.
A `compaction_control` field exists in Anthropic's context-editing docs, but that
parameter belongs to the low-level `anthropic` package's `tool_runner` method, not to
`claude_agent_sdk`. So every direct `Read`/`Bash`/`Grep` tool call made in the root
session's own context stays resident for the rest of the run, and its cost is re-paid
(as a cache read) on every subsequent turn — unlike an interactive Claude Code session,
where auto-compaction would trim old history before it could balloon like this.

Fix: `src/wiki_cli/prompts.py` (`build_prompt`) now instructs `create` and `update` to
dispatch one subagent per domain (or per page, during the evidence-gate step) to do
detailed source reading, and report back only a condensed summary — reserving direct
reads in the root session for top-level discovery (manifests, `AGENTS.md`/`CLAUDE.md`,
directory listings) and small targeted checks. This was chosen over two other options
considered: adding `max_budget_usd`/`task_budget` as a safety net only (rejected — treats
the symptom, not the cause), and investigating the SDK's schema-validation internals
further (dead-ended — validation happens inside the closed-source, compiled `claude` CLI
binary via a bundled `ajv` validator, nothing left to fix upstream from this repo).

Verified empirically on two real repos, including the one that originally failed:
- `pura-admin` (Next.js, smaller): completed clean, 3.97M cache-read tokens.
- `pura-backend` (Go, the repo that originally exhausted the session): 25.27M → 15.99M
  cache-read tokens, 65 → 36 turns, completed instead of erroring. Verbose trace showed
  `Agent(...)` subagent dispatches per domain, matching the new instruction.

A related but separate finding surfaced while validating this fix and was deliberately
left unaddressed: the model can occasionally submit placeholder/dummy structured output
(e.g. `summary: "test"`) after its real final answer gets rejected by the CLI's `ajv`
schema validator, causing `runner.py` (`_finalize_result`) to report `success=True` with a
bogus summary even though the actual `.wiki/` writes on disk are unaffected (confirmed by
inspecting the filesystem after the failing run). A sanity guard in `_finalize_result` was
proposed but explicitly declined for now, since the underlying wiki content was safe
either way.

An unrelated environment issue also blocked validation of this fix initially: a stale,
orphaned, non-editable `wiki_cli` copy in the global `site-packages` directory was
shadowing this repo's editable install (and a second local clone's), so `wiki create`
would have kept running old code regardless of any change made here. Removed and
reinstalled via `pip install -e .` from this checkout before the fix could be verified.

Shipped as PR #7 (`renatoviolin/wiki-cli`, branch `fix/wiki-create-token-burn`), reviewed
via `/code-review` with no findings.

*Captured from a conversation on 2026-09-02 — not independently verified against code.*
