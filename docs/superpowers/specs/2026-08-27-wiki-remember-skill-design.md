# wiki-remember — Interactive Decision Capture Skill

*Adds a second, interactive path for populating `.wiki/`, alongside the existing headless
`wiki create|update`. Does not modify `wiki_cli` and does not resurrect any of the three
superseded second-brain/pr-memory designs — see `docs/superpowers/specs/2026-08-25-pr-memory-design.md`
and `.wiki/design-history.md` for why those were dropped before reproposing anything close to them.*

## Context

`wiki_cli` maintains `.wiki/` — a set of LLM-authored, evidence-disciplined pages describing
this repository's structure — via one headless `query()` session per `wiki create|update` run.
It writes claims about code only after reading the entrypoint, implementation, callers, and
tests for that claim, because a prior evaluation (documented in `docs/second-brain-alternatives-review.md`
and repeated in this repo's `CLAUDE.md`) found that unverified LLM-authored structural prose
invents roughly half of its identifier-level detail. That discipline is why the current wiki
is trustworthy, and this design must not weaken it.

What `wiki_cli` cannot do: capture something that comes up *in conversation* — a decision made,
a constraint explained, a reason an approach was rejected — at the moment it happens. Today
that knowledge either gets written down by hand or waits for the next `wiki update` to
rediscover it indirectly from a diff, if it can be rediscovered from a diff at all (rationale
usually can't be).

A 2026 practice sweep (Cursor's "Memories," Windsurf/Cascade, a shipped Claude Code
"agent-memory" skill, ADR-as-chat commentary) confirms the shape this design already leans
toward: the industry moved *away* from implicit, personal, unreviewed memory and *toward*
explicit-trigger, file-based, repo-committed, human-reviewed memory. Cursor removed its
implicit Memories feature in late 2025 specifically in favor of exporting to reviewable Rules
files. No product surveyed has solved stale/conflicting entries when a later conversation
revisits the same topic — this design states an explicit rule for that (supersede, don't
duplicate) rather than leaving it unaddressed.

## Goals

- Let a developer, mid-conversation in a normal Claude Code session, ask Claude to persist a
  decision or piece of rationale to `.wiki/` — without a headless subprocess, without leaving
  the session.
- Keep the same trust model `wiki_cli` already uses: the developer is present, sees the file
  written, and reviews the git diff before committing. No new verification machinery.
- Keep `.wiki/index.md` the single navigable entry point, the same way `wiki update` already
  does for structural pages.
- State an explicit rule for revisiting the same topic later (supersede, don't silently
  duplicate) even though no mechanism enforces it yet.

## Non-goals

- **Independently-verified structural claims.** This skill never asserts what code does,
  what a type contains, or how a function behaves unless `wiki_cli`'s evidence discipline
  was followed — that stays `wiki_cli`'s job. This skill only records what was *said* in the
  conversation.
- **Proactive/automatic triggering.** The skill never fires on its own judgment that a moment
  is "wiki-worthy." Explicit ask only.
- **Folding decisions back into structural pages.** `wiki_cli`'s `update` mode does not read
  `.wiki/decisions/`. They remain a separate, permanent category. Worth revisiting later, not
  building now.
- **Mechanical quote verification** (the `pr-memory` design's `verify.py` gate). That design
  needed it because extraction was offline/headless with no human present. This skill has a
  human present in the same turn the file is written, so the git-diff review is the gate.
- **A Python package, tests directory, or `pytest` coverage.** A Skill is prompt content, not
  code; see Testing below for how it's actually validated.
- **Automatic git commit.** Same convention as `wiki_cli`: the skill writes files and stops;
  the developer commits `.wiki/` alongside their own work.

## Design

### Location and packaging

`.claude/skills/wiki-remember/SKILL.md`, committed to the repo — this repository's first
Claude Code Skill (no `.claude/` directory exists yet). Committing it is deliberate: it must
be available to any developer's Claude Code session in this checkout, the same way `CLAUDE.md`
already is.

### Trigger

Explicit only. The `SKILL.md` description is written so Claude invokes it when a user
directly asks to capture, remember, or log a decision/finding into the wiki (e.g. "remember
this in the wiki," "capture that as a decision"). It never fires on its own initiative.

### Execution model

Fully in-session: the current Claude Code conversation reads and edits `.wiki/` files
directly with its normal Read/Edit/Write tools, guided by `SKILL.md`'s instructions. No
subprocess, no separate Agent SDK `query()` call, no temp workspace — unlike `wiki_cli.runner`,
which deliberately does spawn a fresh headless session. The two mechanisms share no code.

### What gets captured

Only rationale/decisions actually stated in *this* conversation: a decision made, an
alternative rejected and why, a constraint or gotcha explained. The skill paraphrases in its
own words but must not add detail beyond what was actually discussed — no independent code
verification, no filling gaps with plausible-sounding inference. If code is referenced, it's
cited the same way `wiki_cli` cites it: repository path plus symbol name, never `file:line`
(line numbers go stale; a path+symbol stays checkable).

### Categorization and index integration

Path shape: `.wiki/decisions/<category>/<date>-<slug>.md` — one file per decision. Filenames
are date+slug so concurrent captures across branches don't collide on the same file.

`<category>` is chosen by the skill, not fixed in advance:

1. Before writing, read existing `.wiki/decisions/*/` category directory names and the
   "Decisions & rationale" section of `.wiki/index.md`.
2. Reuse an existing category if this finding genuinely fits it.
3. Otherwise create a new category directory — the skill's judgment call, not a predefined
   taxonomy.

After writing, update `.wiki/index.md`'s "Decisions & rationale" section (one row per
decision, same task-routing-table shape already used for structural pages) so the index stays
accurate. One row per category, rather than per decision, was considered and rejected: a
single row per category can't carry per-decision status/file links, which the supersede
mechanism needs — a superseded decision and the one that replaced it must each show their
own `Status` and `File`. This mirrors what `wiki update` already does for structural content
— the index is never left to drift.

### Superseding, not duplicating

Before writing a new decision, search existing `.wiki/decisions/` for prior entries on the
same topic. If the new conversation changes or reverses an earlier decision:

- The new file's frontmatter sets `supersedes: <path-to-old-file>`.
- The old file's frontmatter `status` flips from `active` to `superseded` (the file is edited
  in place to update just that field — it is not deleted; history stays visible, same
  philosophy as the superseded specs kept under `docs/superpowers/specs/`).

This is a stated rule the skill follows, not an automated verifier — no product surveyed in
the 2026 practice sweep has a mechanical fix for this, and building one is out of scope here.

### File format

```yaml
---
type: decision
category: prompt-design          # skill-chosen: reused existing or newly created
status: active                    # or: superseded
supersedes: null                  # or path to the file this replaces
captured: 2026-08-27               # date of the conversation, not of any commit
---

# <short title>

<statement of what was decided or rejected, and why, in the skill's own words, grounded
only in what was actually discussed in this conversation>

*Captured from a conversation on 2026-08-27 — not independently verified against code.*
```

The trailing italic line is deliberate: it's the same signal `wiki_cli`'s pages give
implicitly through evidence discipline, made explicit here because this content type doesn't
carry that discipline — a reader (human or agent) should not mistake a captured decision for
a code-verified structural claim.

### Trust model

Unchanged from the repository's existing convention: the developer is present when the file
is written, sees it via the normal Edit/Write tool output, and reviews the git diff before
committing `.wiki/` alongside their own work. No new verification module, no quote-matching
gate — that machinery exists in the superseded `pr-memory` design specifically because it had
no human present at write time; this skill always does.

## Testing

Skills are prompt content, not code, so there is no `pytest` coverage to add and no new
package under `src/`. Validation is manual, exercised in a live session:

- Invoke the skill after a conversation containing a clear decision; confirm the written file
  matches what was actually said (no invented detail) and cites code, if any, by path+symbol.
- Confirm `.wiki/index.md`'s "Decisions & rationale" section is updated to reference the new
  file.
- Revisit the same topic in a later session; confirm the skill finds the prior entry, sets
  `supersedes`, and flips the old file's `status` rather than leaving two active entries that
  silently disagree.
- Confirm the skill never runs `git commit` and never fires without an explicit ask.

## Risks and accepted limitations

- **No mechanical enforcement of the supersede rule.** It depends on the skill's own
  search-before-write; a future session could still miss a prior related entry, especially
  across a large `.wiki/decisions/` tree. Accepted for v1; revisit if it proves to be a real
  problem in practice, not preemptively.
- **Category taxonomy can drift or fragment** since it's chosen live per capture rather than
  fixed. `wiki_cli`'s existing structural task-routing table doesn't have this problem because
  it's page-per-topic, generated by one planning pass; a decisions log built incrementally
  across many separate conversations doesn't get that same up-front planning. Mitigated by
  the skill being instructed to check existing categories before inventing one, not solved
  outright.
- **Confidentiality.** Captured decisions may reference internal C&A systems, architecture, or
  constraints discussed in a session. `.wiki/decisions/` is committed to the same repository
  as everything else here and inherits the same confidentiality posture already stated in
  this repo's `CLAUDE.md` — no additional redaction step is introduced by this design.

## Critical files

- New: `.claude/skills/wiki-remember/SKILL.md` — the entire implementation; this repo's first
  Claude Code Skill.
- No changes to `src/wiki_cli/` or `src/code_review_cli/` — zero coupling, same as the
  existing convention between those two packages.
- Related history: `docs/superpowers/specs/2026-08-25-pr-memory-design.md` (why mechanical
  quote verification and typed provenance were rejected before), `.wiki/design-history.md`
  (map of what shipped vs. what was superseded).
