---
type: decision
category: wiki-remember-design
status: active
supersedes: .wiki/decisions/wiki-remember-design/2026-08-27-decision-storage-layout.md
captured: 2026-08-27
---

# Category chosen dynamically per finding, not a fixed storage layout

The flat-log/per-page-grouped storage layout was superseded: the wiki-remember skill
instead lets the skill choose the category dynamically per finding — reusing an existing
`.wiki/decisions/<category>/` directory when a finding fits, or creating a new one when
it doesn't — and keeps `.wiki/index.md`'s "Decisions & rationale" section in sync with
whichever categories exist, the same way `wiki update` keeps the index in sync with
structural pages.

*Captured from a conversation on 2026-08-27 — not independently verified against code.*
