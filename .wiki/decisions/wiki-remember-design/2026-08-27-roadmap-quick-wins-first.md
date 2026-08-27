---
type: decision
category: wiki-remember-design
status: active
supersedes: null
captured: 2026-08-27
---

# Quick, low-risk wiki-remember improvements implemented first; deeper memory tooling deferred

After the `wiki-remember` skill shipped, a roadmap of further improvements was discussed:
handling a missing `.wiki/index.md`, fixing an inaccurate `CLAUDE.md` claim about the
`wiki_cli` guard's scope, a cheap staleness sanity-check in the capture procedure, a
mechanical decisions-audit script, wiring `.wiki/decisions/` into `code_review_cli`'s review
prompt, retrieval/injection of relevant decisions into future sessions, and mechanical
dedup of near-duplicate categories.

Only the first three — the empty-index case, the `CLAUDE.md` wording fix, and the staleness
check — were implemented immediately. They were cheap, low-risk, and required no new
mechanism beyond editing existing prompt/doc text.

The rest were deliberately deferred rather than built preemptively: the audit script and
review-prompt integration until there's a clearer need for them, and retrieval/injection
plus dedup tooling until the problems they would solve — people not checking the decisions
log manually, or categories drifting into near-duplicates — are actually observed in
practice rather than anticipated. This follows the same pattern already established in this
project's history of rejecting premature complexity, most directly in the two earlier
"second-brain" designs that were superseded before being built.

*Captured from a conversation on 2026-08-27 — not independently verified against code.*
