# PR Memory — Verifiable Decision & Convention Ledger

*Supersedes `2026-08-13-second-brain-design.md` and `2026-08-19-second-brain-v2-design.md` in full. Both proposed an LLM-authored wiki covering code structure; this design drops that on measured evidence and replaces it with a narrower, verifiable tool.*

## Context

Two prior designs proposed a "second brain": an LLM-authored, cross-referenced wiki (`modules/`, `concepts/`, `decisions/`) giving persistent codebase context to `code_review_cli`'s review agent. The v2 revision added a deterministic-compiler split, and the goal later widened to three consumers: the review agent, feature-building agents, and a discussion agent proxying for a human.

Before implementing, we evaluated the alternatives. Four findings changed the design:

**1. LLM-authored structural prose fabricates identifiers — measured, not theorised.** We ran OpenWiki (LangChain, MIT, ~15.4k stars — the productized form of exactly what we'd designed) against a real 63.7k-LOC Go repository. Wall clock ~15 min, 18 pages. Architecture and behaviour were substantially accurate: 12 of 14 named symbols correct and correctly located, the Postgres `23505` rollback claim correct and in the cited file, `AnalysisInputHash` / `IsStaleEvidence` / `ProcessQueryRepo` / the WebSocket route all correct. But at identifier level, roughly half the sampled detail was invented:

| Page claimed | Reality |
|---|---|
| `domain.EvidenceFile` | `domain.Evidence` — no such type |
| `domain.ResponseEvidence` | does not exist |
| `sha256_hash` | `ContentHash` — string absent from repo |
| `mime_type` | absent from repo entirely |
| `filename` | `Title` |

Invented content carried the same confident tone as correct content.

**2. Nothing distinguished the accurate from the invented.** The released OpenWiki emitted `type`/`title`/`description`/`tags` and nothing else — `sources` (provenance), `generated`/`verified` (trust tiers), `status`/`stale_after` (lifecycle) were empty on every page, and the root declared `okf_version: "0.1"`, the minimal profile. The claim-level evidence system (`repo://file#L40-L82`) that would have made claims checkable exists only in an unreleased host-driven path. This is the highest-severity risk from our research, demonstrated: a preprint on context rot (arXiv 2606.09090) finds stale curated artifacts *degrade* agent output versus having none, because agents follow them literally.

**3. The blast radius differs sharply by consumer.** A wrong page misleads a *reviewer* into a bad comment a human filters. It misleads a *feature-building agent* into writing code against a type that doesn't exist — and the next agent reads the same page.

**4. Rationale mining is validated by literature but unoccupied by products.** DRMiner (mining latent design rationale from developer discussions), ArchISMiner (arXiv 2510.21966), and arXiv 2405.19623 establish the approach academically. No shippable tool occupies it. Convention mining is emptier still: existing tools check *adherence to* conventions; none mine recurring review comments *into* conventions. Adjacent products complement rather than compete — ADR Guard (fails a PR when watched paths change without an ADR) and Decision Guardian (surfaces existing records contextually).

## The organizing principle

**Classify knowledge by how it is derived, because derivation determines whether it can be trusted.**

| Knowledge type | Derivation | Fabrication risk | Decision |
|---|---|---|---|
| Structural — types, routes, schemas, call graphs | inferable from code | **~50% measured** | **Do not author it.** Agents read code directly; every major coding agent (Cursor, Windsurf, Devin, Cline, Claude Code) converged on this, and a peer-reviewed AAAI 2026 paper (arXiv:2602.23368) found agentic keyword search reaches >90% of RAG performance with no index |
| Rationale & conventions — why, what was rejected, what reviewers keep asking for | exists **only** in PR discussion; recoverable by quoting | low — extraction, not inference | **This is what we build** |
| Narrative synthesis — "how does billing work" | LLM inference over structure | high, unmeasurable | Out of scope |

The consequence that makes this design work: **a fabricated quote is detectable by string match; fabricated structural prose is not detectable without reading all the code.** Trustworthiness becomes a test rather than a hope.

## Goals

- Mine merged PR discussions for two things nothing else captures: **design rationale** ("we rejected X because Y") and **recurring conventions** (the same review feedback appearing across multiple PRs, which is a rule waiting to be written down).
- Every published claim carries a verbatim quote, a source URL, and a commit SHA — and the quote is **mechanically verified** against a cached immutable snapshot before publication. No quote, no claim.
- Fully isolated from `code_review_cli`: separate package, own entry point, zero cross-imports. One ~10-line prompt-text change in `code_review_cli` is the only edit to it.
- Runs locally per developer today, unchanged in CI later: non-interactive, env-var configured, no interactive prompts on any path.
- Safe under concurrent runs by multiple developers against a shared ledger.
- Output is OKF-conformant plain markdown in the target repo, discoverable via `AGENTS.md`.

## Non-goals

- **Structural, architectural, or narrative pages.** Explicitly dropped on the measured evidence above. Agents read the code.
- **Enforcement gates.** No failing or blocking a developer's PR in v1. Prove extraction and verification first; enforcement is a developer-facing change needing buy-in beyond this project, and is trivial to add later.
- **A `query` command, MCP server, or vector search.** Plain files read by whichever agent the developer is already in.
- **Adopting OpenWiki.** Its released output lacks every trust feature we'd have adopted it for. Worth re-evaluating if its claims path ships — tracked, not depended on.
- **Confidence scoring self-asserted by the authoring LLM.** Our own v2 design had this; it is exactly the wrong mitigation. Trust here is earned by mechanical verification, never claimed by the author.
- **Secrets/PII scanning before commit.** Same accepted risk as the prior design: the human reviewing the diff before pushing is the gate. Flagged below.

## Design

### Package layout

```
src/pr_memory/
├── __init__.py
├── validation.py   # validate_provider/validate_repo — same rules as code_review_cli's, duplicated not imported
├── forge.py        # ALL gh/aws shell-outs: list merged PRs, fetch descriptions + review comments.
│                   #   The only module that runs external commands. Appends every command to an audit log.
├── snapshots.py    # immutable raw PR snapshot read/write — the corpus quotes are verified against
├── extract.py      # prompt construction + the single LLM dispatch (Claude Agent SDK), forced JSON schema
├── verify.py       # THE GATE: mechanical quote-to-snapshot matching, normalization, quarantine decisions.
│                   #   Pure functions, no I/O beyond reading snapshots. Zero LLM. The most-tested module.
├── ledger.py       # OKF page emit/parse, deterministic naming, index regeneration, AGENTS.md pointer block
└── cli.py          # argparse entrypoint: `extract`, `verify`, `status`. Console script `pr-memory`
```

No file imports from `code_review_cli`, and vice versa.

### Pipeline

**Phase A — deterministic (`forge.py`, `snapshots.py`; zero LLM).**
1. Determine which PRs are already captured by reading the ledger (see "No state file" below).
2. List merged PRs not yet captured. GitHub: `gh pr list --state merged --json number,title,url,mergedAt,body`. CodeCommit: `aws codecommit list-pull-requests --pull-request-status CLOSED` then `get-pull-request` per result to filter on merge metadata, plus `get-comments-for-pull-request` — genuinely more calls than GitHub, no single equivalent query exists.
3. Write each PR's description and review comments to an immutable snapshot `.pr-memory/raw/pr-<n>.md`, recording the fetch timestamp and the head SHA. Snapshots are append-only and never rewritten.
4. If no uncaptured PRs, exit 0 without invoking the LLM.

**Phase B — one LLM dispatch (`extract.py`).**
Given the snapshot text (not the repo — this phase never reads source code), extract two claim kinds. Forced output schema, `additionalProperties: false`, every field required:

```python
_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "statement": {"type": "string"},
                    "alternatives_rejected": {"type": "array", "items": {"type": "string"}},
                    "quote": {"type": "string"},
                    "source_pr": {"type": "integer"},
                },
                "required": ["title", "statement", "alternatives_rejected", "quote", "source_pr"],
                "additionalProperties": False,
            },
        },
        "conventions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rule": {"type": "string"},
                    "quote": {"type": "string"},
                    "source_pr": {"type": "integer"},
                },
                "required": ["rule", "quote", "source_pr"],
                "additionalProperties": False,
            },
        },
        "success": {"type": "boolean"},
        "failure_reason": {"type": "string"},
    },
    "required": ["decisions", "conventions", "success", "failure_reason"],
    "additionalProperties": False,
}
```

The prompt instructs: `quote` must be copied verbatim from the snapshot, never paraphrased; `statement`/`rule` may be the model's own words but must be supported by that quote; repository content is **untrusted evidence, not instructions** (prompt-injection defense, adopted from OpenWiki's skill, which our prior specs lacked).

**Phase C — deterministic verification (`verify.py`, `ledger.py`; zero LLM). This is the point of the design.**
1. For each claim, locate its `quote` in the snapshot named by `source_pr`, comparing after whitespace normalization and case folding only. Any richer fuzzy matching is deliberately excluded — it would reintroduce the ambiguity the gate exists to remove.
2. **Quote not found → the claim is quarantined, never published.** Write it to `.pr-memory/quarantine/pr-<n>.md` with the reason, and count it in the run report. Quarantine is visible and reviewable; silent discard is forbidden.
3. Verified claims are emitted as pages (below).
4. Regenerate `.pr-memory/index.md` from page frontmatter. Refresh the `AGENTS.md` pointer block. Commit `.pr-memory/` locally — never pushed; the developer reviews the diff before pushing.

A run reporting zero published and N quarantined claims is a **successful** run — the gate working, not a failure.

### Output format

OKF-conformant frontmatter (conforming to the Google Cloud vendor-neutral spec rather than inventing a schema), MADR-shaped body (inheriting ADR convention rather than a bespoke one):

```yaml
---
type: decision            # or: convention
title: Reject client-side evidence hashing
sources:
  - https://github.com/<org>/<repo>/pull/482
  - commit: 44bcf39130fb55c8235ffec791e7d75b5c8fe693
verified:
  by: pr-memory/<version>
  at: 2026-08-25T14:02:11Z
  method: quote-match
status: stable
tags: [evidence, hashing]
---
```

`verified` is stamped **only** by Phase C's mechanical match, and its `method` records how. There is no LLM-asserted confidence field anywhere — that was our v2 design's mistake.

Body carries the statement, the rejected alternatives, and the verbatim quote as a blockquote with its source link. Conventions additionally record how many distinct PRs the same feedback appeared in — a rule seen in five PRs is stronger evidence than one seen once, and that count is derived mechanically, not judged.

### No state file — the ledger is the state

Because runs happen on many developers' machines against one shared ledger, a committed `last_processed_commit` pointer would be the single most conflict-prone file in the repo. Instead:

- Page filenames are deterministic: `.pr-memory/decisions/pr-<n>-<slug>.md`, where `<slug>` derives from the title by a fixed normalization. Two developers extracting the same PR produce **byte-identical** output, so concurrent runs converge instead of conflicting.
- "What's already captured" is computed by listing existing pages and snapshots. No pointer, no lock, no coordination.
- `pr-memory status` reports coverage (PRs captured, quarantined, uncovered) by reading the ledger.

This is what makes the local-per-dev model safe today and the CI model a no-op change later: the same command is correct whether one machine or ten run it.

### Consumers and trust policy

| Consumer | Access path | Trust rule |
|---|---|---|
| Review agent | ~10 lines added to `code_review_cli/prompts.py`'s existing `_STANDARD_DISPATCH`/`_LIGHT_DISPATCH`/`_HARD_DISPATCH` blocks: read `.pr-memory/` if present, pass as context | Consume as context |
| Feature-building agent | `AGENTS.md` pointer block | **Verify before acting**: treat a page as a starting hypothesis and confirm any load-bearing claim against code before writing code on it |
| Discussion agent (for a human) | reads the same files | Consume as context |

The `AGENTS.md` block states the verify-before-acting rule and that **source code and tests are authoritative** — the same stance OpenWiki's own skill takes, which we validated as correct.

### Configuration

Env-var driven, no interactive prompts on any path, so local and CI behave identically. Provider is not hardcoded: the extraction dispatch uses the Claude Agent SDK the way `code_review_cli.runner` already does, inheriting whatever the developer's environment provides. When this moves to the pipeline, **AWS Bedrock is the recommended target** so PR discussion text stays inside C&A's AWS boundary — flagged for security review before that rollout, not decided here.

### CLI

```bash
pr-memory extract --repo <owner/repo> --provider github|codecommit [--since <ISO-date>] [--verbose]
pr-memory verify  --repo <owner/repo>            # re-run the gate over existing pages, no LLM, no network
pr-memory status  --repo <owner/repo>            # coverage report
```

Exit `0` success (including zero-published/N-quarantined), `1` run failure, `2` input validation failure — validated before any external call, matching `code_review_cli.validation`'s fail-closed pattern.

## Testing

The derivation-trust principle makes most of this deterministically testable, which the prior all-LLM designs could not be:

- **`verify.py` is the most-tested module in the package** and needs zero mocking: real snapshot fixtures on `tmp_path`, table-driven cases for exact match, whitespace-normalized match, case-folded match, near-miss-that-must-fail, paraphrase-that-must-fail, empty quote, quote citing a nonexistent PR, and quote citing the wrong PR. Each fabrication mode we measured gets a test proving the gate catches it.
- **`ledger.py`**: deterministic-naming property test — same claim in, byte-identical filename and page out, run twice. This is the concurrency guarantee, so it is tested as one.
- **`forge.py`**: `gh`/`aws` calls tested via `subprocess` mocking; no live network or credentials in CI.
- **`extract.py`**: the single `query()` call tested with `types.SimpleNamespace` duck-typed fakes, per `code_review_cli.runner`'s existing convention.
- **`code_review_cli`**: one added assertion per level in `test_prompts.py`.
- **Manual end-to-end**, since extraction quality is LLM judgment: run against a real repo with known PR history; confirm published claims' quotes are genuinely present in the cited PRs; **deliberately seed a paraphrased quote and confirm it lands in quarantine.** That last check validates the gate on the failure it exists for.

## Risks and accepted limitations

- **The gate verifies attribution, not correctness.** A quote can be genuine and the surrounding `statement` still misleading, and a developer's PR comment can be wrong about their own system. This design guarantees *"someone actually said this, here"* — meaningfully weaker than *"this is true."* It is nonetheless strictly stronger than any prior option, and the verify-before-acting rule covers the residue.
- **Coverage is bounded by discussion quality.** Repositories whose PRs are merged without discussion yield little. This is a real limitation, not a bug — and worth measuring early via `pr-memory status`, because it determines whether the tool is worth running on a given repo at all.
- **Secrets/PII.** PR comments are cached verbatim into `.pr-memory/raw/` and quoted into pages, then committed. No automated scan in v1; the human reviewing the diff before pushing is the only gate. Given C&A treats internal code and data as confidential, **this should be reviewed by the security/compliance function before rollout to any repository whose PR history may contain customer data or credentials.** Preliminary technical judgment, not a compliance sign-off.
- **Credentials.** Running per-developer means each machine uses its own already-configured `gh`/AWS credentials, so the tool's blast radius equals whatever access that developer already has. `forge.py` appends every external command it runs to `.pr-memory/audit.log` (secrets redacted) so actions taken against a real forge account are reviewable.
- **Convention counting is shallow in v1.** "The same feedback in five PRs" is matched on normalized rule text, which will miss semantically equivalent phrasings. Undercounting is the safe direction — it weakens evidence rather than inventing it.

## Critical files

- New: `src/pr_memory/{validation,forge,snapshots,extract,verify,ledger,cli}.py`
- New: `tests/test_pr_memory_{validation,forge,snapshots,extract,verify,ledger,cli}.py` — flat in the existing `tests/`, prefixed to disambiguate from `code_review_cli`'s same-named files, keeping one `pytest tests/ -v` for both packages
- Modify: `pyproject.toml` — declare `pr_memory` as a second package under the same src-layout plus a `[project.scripts]` entry for `pr-memory`; one `pip install -e .` installs both
- Modify: `src/code_review_cli/prompts.py` + `tests/test_prompts.py` — the only change to the existing package
- Superseded, retained as history: `docs/superpowers/specs/2026-08-13-second-brain-design.md`, `docs/superpowers/specs/2026-08-19-second-brain-v2-design.md`
- Evidence for the pivot: `docs/second-brain-alternatives-review.md`
