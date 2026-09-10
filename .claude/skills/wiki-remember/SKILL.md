---
name: wiki-remember
description: Use when the user explicitly asks to capture, remember, save, or log a decision, rationale, or finding from the current conversation into the project's .wiki/ knowledge base (e.g. "remember this in the wiki", "capture that as a decision", "log this rationale"). Writes one dated file under .wiki/decisions/<category>/ and updates .wiki/index.md. Never invoke this proactively — explicit ask only.
---

# wiki-remember

Captures a decision or piece of rationale that was actually stated in the current
conversation into this repository's `.wiki/decisions/` log, and keeps `.wiki/index.md`
in sync. This is the interactive counterpart to `wiki_cli`'s headless `wiki create|update`
— it does not touch structural pages and never asserts anything about code that wasn't
explicitly said in this conversation.

**Write in the language the surrounding `.wiki/` pages are written in**, and match their
tone. The wiki is repository-specific; this skill is not.

## When NOT to use this

- Never invoke this on your own initiative. Only run this when the user explicitly asks
  you to capture, remember, or log something.
- Never use this to record an independently-verified claim about what code does (a type's
  fields, a function's behavior). That requires `wiki_cli`'s evidence discipline (reading
  the entrypoint, implementation, callers, and tests) — this skill has no such discipline
  and must not pretend to.
- If it's unclear which specific decision or finding the user wants captured, ask one
  clarifying question before writing anything.

## Procedure

1. **Identify the content.** Restate, in your own words, the decision/rationale/finding
   the user is pointing to. Ground it only in what was actually discussed in this
   conversation — do not add detail you haven't verified was said, and do not
   independently assert how code behaves.

   **Every capture from this skill is human-asserted by definition.** Mark it with the
   marker this wiki uses for "confirmed by a human, not inferred from code" — read the
   provenance-conventions section of `.wiki/index.md` for the house marker, and use
   `[via user]` if the wiki declares none. Anything that is your assumption rather than
   the user's assertion gets the wiki's unverified-assumption marker instead
   (`> ⚠️ Unverified:` by default) — never state it flatly.

   When you reference code, use the citation form the surrounding pages already use.
   Path plus symbol (`src/wiki_cli/prompts.py` (`build_prompt`), or the house
   `file.py::symbol` form) is the preferred form, because a linter can confirm the symbol
   is really defined there. A line anchor (`file.py:42`) is fine wherever the repository's
   own checker verifies it — knowing that anchors drift on merge, prefer path plus symbol
   when both would serve.

   Before writing, check each code citation mechanically:

   ```bash
   grep -n '<symbol>' <path>          # does the symbol actually appear in that file?
   wc -l <path>                       # does the file have at least NNN lines?
   ```

   Not found → fix the citation, or drop it and describe the behavior in prose instead.
   This is a cheap mechanical check, not a substitute for the full evidence discipline of
   `wiki-create`/`wiki-update` — it only catches a citation whose symbol string is already
   wrong or has gone stale.

   Before writing, do one quick sanity check: if a structural page already exists under
   `.wiki/` that's obviously relevant to this topic, skim it for anything that plainly
   contradicts what you're about to capture. Start from the task-routing table in
   `.wiki/index.md`, which already points at the right page for most topics. This is not a
   verification pass — one read if an obviously-relevant page exists, skipped otherwise;
   it's not a research project, and you don't need to go looking for one. If you do find a
   contradiction, don't silently write the decision as if it settled the question — say so
   in your final report to the user instead.

   Two kinds of contradiction are worth special attention, because they are the ones that
   actually recur:

   - **the topic touches an entry in the repository's pitfall register.** If it does, cite
     that entry's ID in the capture and link the register. Those IDs are identity, not
     position, and they are referenced from other pages and sometimes from code comments.
   - **the topic presumes validation by tests.** Check whether the repository has an
     automated test suite at all — data and ML repositories often have none, and there
     validating means running the job by the runbook against a sandbox target. Do not
     capture a decision that rests on tests that do not exist.

2. **Resolve today's date.** Run `date +%Y-%m-%d` — never hardcode a date.

3. **Survey existing categories.** Read the decisions & rationale section of
   `.wiki/index.md` (if present) and list the directories under `.wiki/decisions/` (if the
   tree exists yet — it may not on a repository's first use of this skill, and then this
   run is what creates it). These are the existing categories.

4. **Choose the category.** If the decision genuinely fits an existing category, reuse it
   (use the existing directory name exactly). Otherwise choose a new, short, kebab-case
   category name that describes the topic area, in the language of the rest of the wiki
   (e.g. `calibration`, `infrastructure`, `tooling`, `metrics`). Prefer reuse over
   inventing a near-duplicate category.

5. **Check for a prior entry to supersede.** Search `.wiki/decisions/<category>/` (and, if
   the topic could reasonably live elsewhere, other categories too) for an existing file
   covering the same topic. If this new capture changes or reverses that earlier decision,
   this is a supersede case — carry the old file's path forward into step 7.

6. **Derive the filename.** Derive a short kebab-case slug from the title — the
   distinguishing two-to-four words, not a literal character-for-character transform of the
   full title. The path is:
   `.wiki/decisions/<category>/<date-from-step-2>-<slug>.md`

7. **Write the new file** with exactly this frontmatter and body shape. `supersedes:` is
   always a repo-root-relative path (e.g. `.wiki/decisions/<category>/<file>.md`) — not a
   path relative to this file or to `.wiki/` — or `null` if this capture doesn't supersede
   anything:

   ```yaml
   ---
   type: decision
   category: <category>
   status: active
   supersedes: null   # template: use `null` or path to the file this replaces (from step 5), never copy this comment
   captured: <date-from-step-2>
   ---

   # <short title>

   <statement of what was decided or rejected, and why, in your own words, grounded
   only in what was actually discussed in this conversation> [via user]

   *Captured from a conversation on <date-from-step-2> — not independently verified
   against code.*
   ```

   If the topic touches a pitfall entry, cite its ID and link the register with a relative
   path that resolves from `.wiki/decisions/<category>/` (two levels up).

8. **If superseding**, edit the old file in place: change only its `status:` field from
   `active` to `superseded`. Do not delete it and do not otherwise alter its content —
   history stays visible. Deleting an earlier record because the decision changed is the
   one thing this wiki's governance rules out: nothing is removed without explicit
   confirmation, however superseded it looks.

9. **Update `.wiki/index.md`.** If it does not exist yet, create it first with a minimal
   header — a top-level `# <repo name>` heading and one short sentence noting it documents
   this repository — and nothing else; do not attempt to build out a full wiki structure or
   any structural content, that's `wiki-create`'s job, not this skill's. If it does exist,
   **edit it surgically, never rewrite it from scratch**, and do not touch the sections a
   human maintains — the provenance conventions, the backlog, or the maintenance contract.

   Ensure a decisions & rationale section exists (add it near the end of the file, and
   **before** the sources section, if this is the first-ever capture) containing **one
   single markdown table for all decisions, ever** — the same shape as the file's existing
   task-routing table — with columns `Category | Decision | Status | Captured | File`,
   one row per decision file, newest `Captured` date first within each category, categories
   grouped by adjacent rows sharing a `Category` column value. Do not add per-category
   subsection headings and do not split decisions into separate tables per category — this
   section is always exactly one table, nothing nested beneath it. Add a row for the new
   file (`Status` = `active`, `File` a relative link to it). If step 8 applied, edit the
   existing row for the superseded file in place — change only its `Status` cell to
   `superseded` — rather than removing the row.

   On the first capture, also add an entry for `decisions/` to the index's page list, so
   the new directory is reachable by more than the table alone.

10. **Run the repository's wiki checker, if it versions one** (typically a script under
    `.wiki/`), scoped to the two files you touched:

    ```bash
    python3 .wiki/<checker>.py .wiki/index.md .wiki/decisions/<category>/<file>.md
    ```

    The new page and the index link fall in its scope: it confirms that relative links
    resolve, that section fragments exist in their target, and that line-anchored citations
    are in range. It exits non-zero on failure — fix what it reports before you report
    back. Substitute the actual script this repository ships — glob `.wiki/*.py` to find it;
    if it ships none, at minimum re-check by hand that your relative links resolve.

11. **Never run `git commit`.** Stop after writing the files. Report back to the user, in
    one or two sentences, what was written and where — the developer reviews the diff and
    commits `.wiki/` alongside their own work, same as the other wiki skills. If you found
    a contradiction in step 1, say so in the same report.
