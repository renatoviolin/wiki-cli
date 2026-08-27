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
   independently assert how code behaves. If you reference code, cite it as repository
   path plus symbol name (e.g. `src/wiki_cli/prompts.py` (`build_prompt`)) — never
   `file:line`, since line numbers go stale and a stale reference is itself a false claim.

2. **Resolve today's date.** Run `date +%Y-%m-%d` — never hardcode a date.

3. **Survey existing categories.** Read `.wiki/index.md`'s "Decisions & rationale" section
   (if present) and list the directories under `.wiki/decisions/` (if the tree exists yet
   — it may not on a repo's first use of this skill). These are the existing categories.

4. **Choose the category.** If the decision genuinely fits an existing category, reuse it
   (use the existing directory name exactly). Otherwise choose a new, short, kebab-case
   category name that describes the topic area (e.g. `prompt-design`, `tooling`,
   `review-flow`). Prefer reuse over inventing a near-duplicate category.

5. **Check for a prior entry to supersede.** Search `.wiki/decisions/<category>/` (and, if
   the topic could reasonably live elsewhere, other categories too) for an existing file
   covering the same topic. If this new capture changes or reverses that earlier decision,
   this is a supersede case — carry the old file's path forward into step 7.

6. **Derive the filename.** Slug the title into kebab-case (lowercase, spaces to hyphens,
   strip punctuation). The path is:
   `.wiki/decisions/<category>/<date-from-step-2>-<slug>.md`

7. **Write the new file** with exactly this frontmatter and body shape:

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
   only in what was actually discussed in this conversation>

   *Captured from a conversation on <date-from-step-2> — not independently verified
   against code.*
   ```

8. **If superseding**, edit the old file in place: change only its `status:` field from
   `active` to `superseded`. Do not delete it and do not otherwise alter its content —
   history stays visible, the same way superseded design docs are kept under
   `docs/superpowers/specs/`.

9. **Update `.wiki/index.md`.** Ensure a `## Decisions & rationale` section exists (add
   it, near the end of the file, if this is the first-ever capture) containing a markdown
   table — the same shape as the file's existing "Task-routing table" — with columns
   `Category | Decision | Status | Captured | File`, one row per decision file, newest
   `Captured` date first within each category, categories grouped together. Add a row for
   the new file (`Status` = `active`, `File` a relative link to it). If step 8 applied,
   edit the existing row for the superseded file in place — change only its `Status` cell
   to `superseded` — rather than removing the row.

10. **Never run `git commit`.** Stop after writing the files. Report back to the user, in
    one or two sentences, what was written and where — the developer reviews the diff and
    commits `.wiki/` alongside their own work, same as `wiki_cli`.
