---
type: decision
category: wiki-cli-prompt-design
status: active
supersedes: null
captured: 2026-09-02
---

# Wiki pointer in AGENTS.md/CLAUDE.md now appends at end of file and opens with a brief description

`src/wiki_cli/prompts.py`'s `_WIKI_POINTER` section (assembled into the final prompt by
`build_prompt`) previously instructed `wiki create`/`update` to insert the `.wiki/`
pointer paragraph near the top of `AGENTS.md`/`CLAUDE.md`, close to other documentation
pointers, and to phrase it purely as a directive ("check `.wiki/index.md` first") with no
description of what `.wiki/` actually is.

Changed, at explicit request, to two things: the paragraph is now appended at the end of
the file (after a blank line, without touching existing content) instead of inserted near
the top; and it now opens with a one-sentence description — that `.wiki/` is the
repository's source-grounded knowledge base of its architecture, domains, and operations —
before the existing instruction to check `.wiki/index.md` first and the note that code is
authoritative over the wiki wherever they disagree.

The idempotency rule (skip entirely if the file already references `.wiki/`) and the
"create `CLAUDE.md` from nothing" fallback were left unchanged — neither depends on where
in the file the pointer lands.

Shipped in the same PR as the subagent-delegation fix (see
[wiki-cli-performance](../wiki-cli-performance/2026-09-02-subagent-delegation-for-context-budget.md)):
PR #7 (`renatoviolin/wiki-cli`, branch `fix/wiki-create-token-burn`), reviewed via
`/code-review` with no findings.

*Captured from a conversation on 2026-09-02 — not independently verified against code.*
