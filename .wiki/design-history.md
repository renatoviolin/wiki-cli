# Design history

`docs/` holds two different kinds of material that are easy to conflate: implementation
plans that were actually executed and are kept in sync with the code, and design proposals
that were superseded before any of their code was built. This page is the map between
them, so a reader doesn't mistake an abandoned proposal for current behavior.

## Plans that were built (kept in sync with code)

- `docs/superpowers/plans/2026-08-13-code-review-cli.md` — the original implementation
  plan for `code-review-cli.md`: src-layout package, one module per responsibility,
  Claude Code (not the wrapper) performing checkout. The shipped code diverged from this
  plan in two ways later recorded in `docs/superpowers/specs/2026-08-13-second-brain-design.md`'s
  Context section: the review mechanism moved from a built-in `/code-review` skill to
  explicitly dispatching `voltagent-qa-sec:code-reviewer` by name (`git log` commit
  `cf8cf51 fix: dispatch voltagent-qa-sec:code-reviewer subagent instead of
  /code-review skill`), and the reply moved from free text to structured JSON via
  `ClaudeAgentOptions(output_format=...)`.
- `docs/superpowers/plans/2026-08-19-review-levels.md` — the plan for the `--level`
  flag now implemented in `code-review-cli.md`'s `prompts.py`/`validation.py`/`cli.py`,
  including the constraint (upheld by the current code) that `standard` must stay
  byte-for-byte identical to pre-`--level` output.

Both plans are the reference for *why* behind decisions not obvious from the code alone,
per the top-level `CLAUDE.md`.

## Proposals that were superseded before being built

Three specs under `docs/superpowers/specs/` proposed increasingly elaborate designs for
giving the review agent persistent memory of a codebase — typed relation graphs,
provenance/confidence tags, an `ingest`/`lint`/`query` operation set, a deterministic
compiler split, quote-verification gates:

1. `2026-08-13-second-brain-design.md` — the original `/second-brain` skill proposal,
   following the "LLM Wiki" pattern (raw sources → structured cross-referenced wiki →
   schema contract).
2. `2026-08-19-second-brain-v2-design.md` — revised the same idea into an isolated
   package with mechanical bookkeeping split from LLM-authored content, in response to
   research findings recorded in `docs/second-brain-alternatives-review.md` (below).
3. `2026-08-25-pr-memory-design.md` — explicitly supersedes both prior specs "in full,"
   replacing the wiki-covering-code-structure idea with a narrower, verifiable
   decision/convention ledger.

None of these three shipped. What actually shipped is `wiki-cli.md` — a materially
simpler design than any of the three: no typed relations, no confidence tags, no
`ingest`/`lint`/`query` split, just an LLM session writing plain Markdown pages under
`.wiki/` guided by an evidence-discipline prompt. The specs are kept for history; the
top-level `CLAUDE.md` is explicit that they should not be resurrected without first
reading why they were dropped.

`second-brain-for-business.md` — formerly at the repo root, a plain-language summary of the
second/v2 design aimed at non-technical stakeholders — was itself deleted as stale (commit
`02e3cec chore: ignore ruff/superpowers caches and xml reports, drop stale
second-brain-for-business.md`, whose message notes the doc summarized an unshipped design
superseded by `wiki-cli.md`). It no longer exists in the repository; this entry is kept
only so a reader who finds a stray reference to it elsewhere knows why it's gone.

## The evidence review that shaped what actually shipped

`docs/second-brain-alternatives-review.md` is a research review of the v2 design,
commissioned to check its bets against prior art (code-index tools, agent-memory systems,
GraphRAG/retrieval, and established low-tech methods like ADRs). Two findings from it are
directly visible in `wiki-cli.md`'s shipped prompt:

- An evaluation of OpenWiki (LangChain's productized version of the same "LLM Wiki"
  pattern) run against a real 63.7k-LOC Go repository found architecture/behavior claims
  substantially accurate, but roughly half the sampled *identifier*-level detail invented
  — this is the direct source of `wiki-cli.md`'s evidence-discipline rule against naming
  any symbol not read verbatim in source.
- A finding that a stale AI-authored knowledge base can be *worse than none*, because
  agents tend to follow written artifacts literally rather than reading them skeptically
  — part of the argument for keeping the shipped design deliberately simple (plain
  Markdown, human-reviewed before commit) rather than adding confidence-tag metadata that
  would look authoritative even when stale.

This document itself carries a confidentiality note: it contains architecture decisions
for internal systems and should stay local, not be published externally — consistent with
this repository's status as C&A internal engineering material.

## Sources

- `docs/superpowers/plans/2026-08-13-code-review-cli.md`
- `docs/superpowers/plans/2026-08-19-review-levels.md`
- `docs/superpowers/specs/2026-08-13-second-brain-design.md`
- `docs/superpowers/specs/2026-08-19-second-brain-v2-design.md`
- `docs/superpowers/specs/2026-08-25-pr-memory-design.md`
- `docs/second-brain-alternatives-review.md`
