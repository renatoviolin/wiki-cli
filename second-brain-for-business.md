# Second Brain — What It Is and What It Delivers

*A plain-language summary for non-technical stakeholders. This describes a designed capability, not yet built — see "Status" at the end.*

## The problem in one sentence

Every time our AI code reviewer looks at a pull request today, it starts from zero — it has no memory of what it learned reviewing this same codebase yesterday, last week, or last quarter.

## What the Second Brain does

It gives that AI reviewer a memory. Instead of re-discovering the same architecture, conventions, and past decisions on every single review, it reads and maintains a living knowledge base for each codebase — so review quality compounds over time instead of resetting every time.

Think of it as the equivalent of a senior engineer's mental map of a system: "this module handles payments," "we chose this approach because of X," "this pattern was deprecated after an incident." Today, that knowledge lives only in people's heads and scattered PR comments. The Second Brain turns it into an organized, durable, written record — automatically kept up to date.

## How the extraction works, in three steps

**1. Notice what changed — automatically, at no cost.**
Every time the tool runs, it first checks: has anything actually changed in the code, or in pull request discussions, since the last time it looked? If nothing changed, it stops immediately — no AI involved, no cost incurred. This happens purely with standard, deterministic bookkeeping (the same kind of logic that powers version control), not with the AI.

**2. Understand and write it down — this is where the AI does real work.**
Only when there's genuinely new material does the system bring in the AI. It reads what changed, reads what's already recorded, and:
- writes new entries, or updates existing ones, in plain language;
- flags each entry with how confident it is (a directly stated fact vs. an inference vs. a weaker guess);
- checks whether the new information contradicts anything already on record — and if so, marks the old entry as outdated rather than silently deleting it, so the history is never lost.

**3. File it away — automatically, reliably.**
Once the AI has written its update, a second automated pass takes over: it updates the master index, records what changed in a running log, and saves everything as a local draft. A person always reviews that draft before it becomes part of the official, shared record — the AI's output is never published unreviewed.

## What the output actually captures

The knowledge base is organized like a small, focused encyclopedia of the codebase, with three kinds of entries:

| Entry type | What it captures | Example |
|---|---|---|
| **Modules** | What a part of the system does and how it's structured | "The billing module processes monthly charges and integrates with the payment gateway." |
| **Concepts** | Patterns and conventions that cut across the whole codebase | "All customer-facing errors are logged in Portuguese; internal errors, in English." |
| **Decisions** | Why something was built a certain way, with a trail back to the source | "We moved off the old queue system in March because it caused duplicate charges — see PR #482." |

Every entry always answers: *what is this, how confident are we, and where did this come from* (a specific commit, file, or pull request — never just "the AI said so"). Nothing is ever silently overwritten: when something becomes outdated, the old entry is kept and marked as superseded, so the reasoning behind past decisions is never lost.

## What it looks like on disk

Everything the Second Brain produces is plain text — no database, no proprietary format, nothing that requires special software to open. It lives in one folder, `.second-brain`, saved right alongside the code it documents. Here's a sample of what that folder looks like for a repo it's been maintaining for a while:

```
.second-brain/
├── SCHEMA.md                        # the rulebook this tool follows — kept with the project for transparency
├── audit.log                        # a plain record of every automated action taken, for traceability
├── raw/
│   ├── pr-482-2026-08-01.md          # a saved copy of a past pull request's discussion, exactly as written
│   └── pr-510-2026-08-15.md
└── wiki/
    ├── index.md                     # the table of contents — every entry, one line each, always up to date
    ├── log.md                       # a running history of every update this tool has made, and when
    ├── state.json                    # a small bookkeeping file tracking what's already been processed
    ├── modules/
    │   ├── billing.md                # "what is the billing module and how does it work"
    │   └── payments-gateway.md
    ├── concepts/
    │   └── error-logging-convention.md   # a cross-cutting convention, e.g. "how we log errors"
    └── decisions/
        └── 2026-03-queue-migration.md    # "why we moved off the old queue system, and what changed"
```

A business reader would mainly care about two of these: `wiki/index.md` (the one-page overview — good for a quick "what does this tool know about our system" check) and the entries under `decisions/` (the running record of *why* past choices were made, which today only survives in people's memory or buried PR comments).

## What this means for review quality

Once this knowledge base exists for a codebase, the AI code reviewer reads it before starting its review — so it reviews new code with the same context a long-tenured engineer would have, instead of relying only on what it can infer from the diff in front of it.

## What this is *not*

- It is not a chatbot or a search tool (yet) — it's a maintained written record, read the same way anyone reads documentation.
- It does not run automatically on a schedule in this version — it's triggered on demand.
- It does not scan for or redact secrets/personal data before saving — a person still reviews everything before it's shared, the same safeguard already in place for pull request reviews today.

## Status

This describes an approved design, not a shipped feature. It has not been built yet. Figures such as "zero cost when nothing changed" describe the intended behavior of the design, not measured results from a production system.
