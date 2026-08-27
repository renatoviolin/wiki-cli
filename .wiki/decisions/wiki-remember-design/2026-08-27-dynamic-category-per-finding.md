---
type: decision
category: wiki-remember-design
status: active
supersedes: .wiki/decisions/wiki-remember-design/2026-08-27-decision-storage-layout.md
captured: 2026-08-27
---

# Category chosen dynamically per finding, not a fixed storage layout

Neither the flat single-file log nor the per-structural-page grouping was adopted as the
final storage layout. Instead, each time wiki-remember captures a finding, it works out
the right category on the spot: if the finding matches a category directory already
present under `.wiki/decisions/`, that directory gets reused; if not, a new one is
created. `.wiki/index.md`'s "Decisions & rationale" section is then kept aligned with
whatever set of categories currently exists — mirroring how `wiki update` already keeps
that same index synchronized with the repository's structural pages.

*Captured from a conversation on 2026-08-27 — not independently verified against code.*
