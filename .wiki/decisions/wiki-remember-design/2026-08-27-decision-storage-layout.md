---
type: decision
category: wiki-remember-design
status: superseded
supersedes: null
captured: 2026-08-27
---

# Decisions stored as one dated file per category directory, not a flat log or per-page grouping

For wiki-remember's captured decisions, the layout is `.wiki/decisions/<category>/<date>-<slug>.md`
— one file per decision, filed under a category directory chosen dynamically per finding
rather than a fixed taxonomy. This was chosen over two alternatives considered: a single
flat `.wiki/decisions.md` log, or one decisions file grouped per existing structural topic
page.

The flat log was rejected because it doesn't scale well once many decisions accumulate.
Grouping by existing structural topic pages was rejected because a conversation-derived
decision doesn't always map cleanly onto one existing structural page. Filenames combine
date and slug so that concurrent captures made across different branches don't collide on
the same file.

*Captured from a conversation on 2026-08-27 — not independently verified against code.*
