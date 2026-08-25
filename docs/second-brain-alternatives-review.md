# Second Brain — Review Against Alternative Approaches

*Research review of `docs/superpowers/specs/2026-08-19-second-brain-v2-design.md`, August 2026. Four independent web-research passes (code-index tools, agent-memory systems, GraphRAG/retrieval, established low-tech methods), each instructed to discard methods lacking real adoption evidence.*

**Confidentiality note:** internal review document. Contains architecture decisions for C&A systems — keep local, do not publish to external hosting.

**Evidence caveat:** star counts, customer lists, and cost figures below are drawn from public sources and vendor claims as reported. Several are flagged as self-reported or disputed. Validate directly before any procurement or build commitment.

---

## Verdict up front

The proposal's **core technical bets hold up well**. Two of its more contested choices are actively vindicated by the evidence:

- **Rejecting vector search/embeddings was correct.** GraphRAG's indexing cost is the single most-repeated complaint in that ecosystem, with no incremental-update path — and Microsoft's own cost-reduced successor (LazyGraphRAG) moves *away* from heavy pre-indexing. For code specifically, a peer-reviewed AAAI 2026 paper ("Keyword search is all you need," arXiv:2602.23368) found agentic keyword search reaches >90% of RAG performance with no vector DB, and every major coding agent (Cursor, Windsurf, Devin, Cline, Claude Code) has converged on grep/read tools over pre-indexing.
- **Plain files in git, self-hosted, was correct.** It's the one requirement that eliminates most of the commercial field on confidentiality grounds alone.

But the research surfaced **three findings that should change the proposal before implementation.** Two are potentially serious.

---

## What survived the evidence bar

| Method | Captures | Deterministic? | Self-host? | Adoption evidence | Verdict for us |
|---|---|---|---|---|---|
| **Our proposal** | WHY + WHAT | Mechanical yes, authoring no | Yes | **None — bespoke schema** | See below |
| **OpenWiki** (LangChain) | WHY + WHAT | No | Yes | ~15.2k stars, ~1.9k in first 2 weeks | **Build-vs-adopt candidate** |
| **AGENTS.md** | Conventions | Human-authored | Yes | 60k+ repos, 25+ tools, Linux Foundation | **Adopt as an output target** |
| **ADRs** (Nygard/MADR) | WHY | Human-authored | Yes | ThoughtWorks *Adopt* since 2018; AWS, UK Gov | **Adopt the format** |
| **CodeGraph** | WHAT | Yes | Yes (fully local) | ~47k stars, but pre-1.0, single-maintainer | **Already installed here** |
| **Aider repo map** | WHAT | Yes (tree-sitter + PageRank) | Yes | ~44k stars, 6.8M installs | Complement |
| **Cognee** | WHY + WHAT | No | Yes (needs graph DB) | $7.5M seed, ~12k stars, 70+ companies | Conflicts with plain-files req |
| **Sourcegraph** | WHAT | Index yes | Yes (on-prem) | Uber, Lyft, Dropbox, Databricks | ~$150k–500k/yr — too heavy |
| **DeepWiki** (Cognition) | WHY-ish | No | **No** | 50k+ repos indexed (vendor claim) | **Disqualified** — private repos require indexing on their infra |
| GraphRAG / LightRAG / RAPTOR | Retrieval | No | Yes | Real papers, real stars | Cost + no incremental path |
| Mem0 / Zep / Letta | Conversational memory | No | Yes | Real funding, **disputed benchmarks** | Solving a different problem |

**Discarded:** Glean (Meta) and Kythe (Google) — real internally, zero documented adoption outside their origin companies, and Kythe's US team was reportedly cut in 2024. Sphinx/Doxygen-style autodocs — restate signatures the agent already reads. `code2prompt`/`Repomix` — flat context dumps, different category. Most 2025–26 "agentic memory" papers — self-reported numbers, no replication.

**On the memory-systems benchmarks specifically:** treat the entire Mem0-vs-Zep benchmark war as unreliable. Zep's rebuttal showed a naive full-context baseline outscoring Mem0's own best result, and an independent audit found the underlying LoCoMo benchmark's answer key is ~6.4% wrong with an LLM judge that accepts 63% of deliberately wrong answers. Neither vendor's claims should inform this decision.

---

## The three findings that should change the proposal

### 1. Something very close to this already exists, with real traction

**OpenWiki** (LangChain) is the Karpathy LLM-Wiki pattern productized: a CLI that writes an `openwiki/` directory, updates `AGENTS.md`/`CLAUDE.md`, and re-runs incrementally via a GitHub Action against git diffs since the last run. Self-hosted, your own API keys. ~15.2k stars.

That is a substantial overlap with our Phase A/B/C design. What our proposal adds that OpenWiki lacks: typed relations, `confidence` tags, required provenance, and a deterministic `lint`. Those are real additions — but they're now *increments on an existing tool*, not a from-scratch build.

**This warrants an explicit build-vs-adopt evaluation before writing `src/second_brain/`.** Forking OpenWiki and adding the frontmatter rigor may be materially cheaper than building seven modules, and it inherits validation our bespoke schema doesn't have.

### 2. A stale knowledge base may be *worse than none* — and our design amplifies the risk

This is the finding I'd weight highest. An arXiv preprint on "context rot" (2606.09090) reports that stale AI-configuration artifacts (CLAUDE.md/AGENTS.md-style files) can *degrade* agent performance versus having no file at all, because agents follow them literally rather than reading skeptically the way a human would.

Our proposal makes this risk worse in one specific way: confident-looking metadata. Typed relations and an explicit `confidence: high` tag signal rigor to both the AI reviewer and any human reading it. If the content behind that tag has quietly drifted, we've built something that is confidently wrong — strictly worse than an ADR everyone already assumes might be stale.

Independent context: technical docs go materially stale within 30–90 days; 68% of enterprise content goes untouched for 6+ months; ~60% of employees distrust their internal knowledge base, citing staleness first. Every documentation initiative in history has hit this.

**Implication:** `lint` stops being a nice-to-have and becomes the feature the whole thing lives or dies on. It's also, conveniently, the part of our design that's already fully deterministic and free to run. It should be elevated to first-class in the spec, run on every review (not on-demand), and the reviewer prompt should be told to *distrust* pages flagged `needs-review` rather than treating all pages equally.

### 3. The WHAT layer is already solved deterministically — and partly already installed here

Every deterministic code-index tool surveyed (Aider's repo map, CodeGraph, Sourcegraph, Glean, Kythe, CodeQL) captures **only what the code is** — structure, symbols, call graphs. **None capture why decisions were made.** Only DeepWiki and OpenWiki attempt the "why," and DeepWiki is disqualified for private repos.

That's a clean split, and it tells us where our proposal is actually defensible: the `decisions/` layer. Meanwhile this environment already has CodeGraph indexing available via MCP — a deterministic, local, zero-cost WHAT layer.

**Implication:** our `modules/` and `concepts/` pages are the weakest part of the proposal. They're LLM-authored prose restating structure that a deterministic tool already extracts more reliably and for free. The `decisions/` pages — the institutional "why," mined from PR history, which today survives only in people's heads — are the part nothing else does.

---

## The strongest case against the proposal

Stated plainly, because it deserves a fair hearing: **`AGENTS.md` + ADRs may be enough.** `AGENTS.md` has 60k+ repos and Linux Foundation stewardship; lightweight ADRs have been in ThoughtWorks' *Adopt* ring since 2018, with AWS, Spotify, Red Hat, and a UK-Government-wide framework behind them. Both are git-tracked, human-readable, need zero LLM pipeline, and our proposal's typed relations, confidence tags, and provenance schema are bespoke inventions with **no cited adoption evidence anywhere**.

Also worth weighing: GitHub reports Copilot code review has passed 60M+ reviews — better than 1 in 5 PR reviews on GitHub — with no pre-built knowledge base at all, just search/read over the live repo.

What genuinely survives that challenge, in my read: ADRs' documented failure mode is that **humans stop writing them** ("ADR theatre" — written once, never read, status never updated after the author leaves). An LLM that mines merged PR discussions for rationale automatically attacks exactly that failure mode. That's the defensible core. The rest is scaffolding around it.

---

## Recommendation

1. **Evaluate OpenWiki before building.** A short spike: run it against a real repo, see what it produces, decide fork-vs-build. This is cheap and could save the whole implementation.
2. **Narrow v1 to the `decisions/` layer.** Drop `modules/`/`concepts/` from v1 and let CodeGraph (already available) serve the WHAT layer. This cuts scope substantially and concentrates effort where nothing else competes.
3. **Adopt ADR/MADR format for `decisions/` pages** rather than a bespoke schema — inherit 8+ years of convention, tooling, and reviewer familiarity, and keep our additions (provenance, confidence, `lint`-checked staleness) as a thin layer on top.
4. **Promote `lint` to first-class**, run on every review, with the reviewer prompt instructed to distrust `needs-review` pages. This is the mitigation for the highest-severity risk found.
5. **Write to `AGENTS.md`** as an output target so the knowledge base is consumable by tools beyond our own CLI.

Item 2 is the significant scope change and needs a human decision — it materially narrows what was approved. Items 1, 3, 4, 5 are refinements to an already-sound design.

**Unchanged and validated:** no embeddings, plain files in git, deterministic-mechanical/LLM-semantic split, self-hosted, incremental with a zero-cost no-op path.

---

## Spike outcome (2026-08-25) — this supersedes the Recommendation above

Recommendation item 1 (evaluate OpenWiki before building) was executed. **Its result invalidates items 2–5 and the adopt case generally.** See `docs/superpowers/specs/2026-08-25-pr-memory-design.md` for the design that replaced them.

**What we ran.** OpenWiki 0.3.3 (`gemini-3.6-flash`) against a real private 63.7k-LOC Go repository, in a throwaway clone. ~15 min wall clock, 18 pages, 116K.

**Finding 1 — the trust machinery we would have adopted it for is absent from the released version.** `sources` (provenance), `generated`/`verified` (trust tiers), and `status`/`stale_after` (lifecycle) were empty on all 11 content pages; the root declared `okf_version: "0.1"`, the minimal profile. No `.claims/` directory and zero `repo://` evidence references — the claim-level evidence system lives only in an unreleased host-driven MCP path (`src/cli/integrations.ts` exists on `main`, 404s at tag `v0.3.3`; the published bundle contains no `openwiki_begin`).

**Finding 2 — LLM-authored structural prose fabricates identifiers at scale.** Architecture and behaviour were substantially accurate (12/14 named symbols correct and correctly located; the Postgres `23505` rollback claim correct and in the cited file; the WebSocket route correct). But roughly half the sampled entity/field detail was invented — `domain.EvidenceFile` (real: `domain.Evidence`), `domain.ResponseEvidence` (nonexistent), `sha256_hash` (real: `ContentHash`), `mime_type` (absent from the repo) — stated in the same confident tone as the correct content, with no provenance field to tell them apart.

**Finding 3 — the conclusion is not "build our own instead."** Our v2 design would fabricate identically, because it is the same act: an LLM writing prose about code structure. Worse, its `confidence` field was self-asserted by that same LLM, which per the context-rot finding is worse than no metadata.

**What actually follows.** Trustworthiness depends on how a claim is derived. Structural claims are inferred and unverifiable without reading all the code; quoted claims are verifiable by string match. So: stop authoring structural prose, and build only the quote-anchored rationale/convention layer, with mechanical quote verification as a publication gate. Corroborating evidence: rationale mining is validated in the literature (DRMiner, ArchISMiner / arXiv:2510.21966, arXiv:2405.19623) but unoccupied by products, and convention mining from recurring review comments is emptier still — existing tools check adherence to conventions rather than deriving them.

**Also worth recording:** OpenWiki's own injected `AGENTS.md` guidance tells agents to *"Treat source code and tests as authoritative"* and calls its wiki *"optional just-in-time context, not required startup reading"* — independent convergence on the verify-before-acting policy, and an implicit acknowledgement that generated content may be wrong. Two adjacent products complement rather than compete: **ADR Guard** (fails a PR when watched paths change without an ADR) and **Decision Guardian** (surfaces existing records contextually on a PR).
