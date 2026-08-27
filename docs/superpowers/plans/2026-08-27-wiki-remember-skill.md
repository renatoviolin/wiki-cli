# wiki-remember Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `.claude/skills/wiki-remember/SKILL.md`, an explicit-trigger, in-session Claude Code Skill that captures conversation-stated decisions/rationale into `.wiki/decisions/<category>/<date>-<slug>.md` and keeps `.wiki/index.md` in sync.

**Architecture:** A single Markdown Skill file, no Python code, no new package. It instructs the Claude Code session that loads it to: identify the decision from conversation, choose or create a category, check for a prior entry on the same topic to supersede, write the decision file, and update the index — all with the session's normal Read/Edit/Write tools, no subprocess.

**Tech Stack:** Markdown (Skill frontmatter + instructions). No libraries, no test framework — this file is prompt content, validated by exercising it live, not by `pytest`.

**Spec:** `docs/superpowers/specs/2026-08-27-wiki-remember-skill-design.md`

## Global Constraints

- No Python code, no changes under `src/`, no `pytest` tests added — validation is a live exercise of the skill (spec's Testing section).
- The skill must never run `git commit`.
- The skill must never fire proactively — explicit user ask only.
- Content scope is rationale/decisions actually stated in conversation only — never an independently-asserted structural code claim (that stays `wiki_cli`'s job).
- Any code reference in a captured decision is cited as repository path + symbol name, never `file:line`.
- File path shape: `.wiki/decisions/<category>/<date>-<slug>.md`, one file per decision.
- `<category>` is chosen live by the skill: reuse an existing `.wiki/decisions/*/` directory if the finding fits, otherwise create a new one.
- Today's date is resolved at runtime (e.g. `date +%Y-%m-%d`), never hardcoded into the skill file.
- Revisiting the same topic supersedes rather than duplicates: new file sets `supersedes: <old-path>`; old file's `status` flips from `active` to `superseded` in place (never deleted).
- `.wiki/index.md`'s "Decisions & rationale" section must be updated in the same pass so it stays accurate.
- Zero coupling with `src/wiki_cli/` or `src/code_review_cli/` — no imports, no shared files.

---

## File Structure

- Create: `.claude/skills/wiki-remember/SKILL.md` — the entire implementation (Task 1).
- Created by exercising the skill (Task 2, not hand-written): `.wiki/decisions/<category>/<date>-<slug>.md` (two real files) and an updated `.wiki/index.md`.

---

### Task 1: Write the wiki-remember Skill

**Files:**
- Create: `.claude/skills/wiki-remember/SKILL.md`

**Interfaces:**
- Produces: a Claude Code Skill discoverable by name `wiki-remember`, invokable via the `Skill` tool (`skill: "wiki-remember"`) or by a matching natural-language ask in any session opened in this repo.
- Consumes: nothing from existing code — reads `.wiki/index.md` and `.wiki/decisions/*/` at runtime, per its own instructions.

- [ ] **Step 1: Write the full SKILL.md content**

Create `.claude/skills/wiki-remember/SKILL.md` with exactly this content:

```markdown
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
   supersedes: null   # or the path to the file this replaces, from step 5
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

9. **Update `.wiki/index.md`.** Ensure a `## Decisions & rationale` section exists (add it,
   near the end of the file, if this is the first-ever capture). Under it, maintain one
   subsection per category as a `### <category>` heading, with a bullet list of that
   category's decision files, newest first, each bullet showing the title, a link to the
   file, and `(superseded)` appended if its status is `superseded`. Add the new file's
   bullet; if step 8 applied, append `(superseded)` to the old entry's existing bullet
   rather than removing it.

10. **Never run `git commit`.** Stop after writing the files. Report back to the user, in
    one or two sentences, what was written and where — the developer reviews the diff and
    commits `.wiki/` alongside their own work, same as `wiki_cli`.
```

- [ ] **Step 2: Self-review against the spec**

Re-read `docs/superpowers/specs/2026-08-27-wiki-remember-skill-design.md` section by
section and confirm the file written in Step 1 covers each of: trigger (explicit-only),
execution model (in-session, no subprocess), content scope (rationale-only, path+symbol
citation), categorization (skill-chosen, reuse-before-invent), superseding (frontmatter
`supersedes` + old file `status` flip, never delete), file format (exact frontmatter
shape), index integration, and "never commit." Fix any gap directly in the file.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/wiki-remember/SKILL.md
git commit -m "feat: add wiki-remember interactive decision-capture skill"
```

---

### Task 2: Validate by dogfooding — capture two real, related decisions

This is the plan's substitute for a test suite: exercise the skill just written against
this actual repository, using two decisions that genuinely happened earlier in this
project's own design process, including one real supersede case. This both validates the
skill and produces the first true entries in `.wiki/decisions/`.

**Files:**
- Create (by following the skill's own procedure, not by hand): two files under
  `.wiki/decisions/`, and an updated `.wiki/index.md`.

**Interfaces:**
- Consumes: the `wiki-remember` skill produced by Task 1 (invoke via the `Skill` tool with
  `skill: "wiki-remember"`, or by directly following `.claude/skills/wiki-remember/SKILL.md`'s
  procedure step by step).

- [ ] **Step 1: Capture the first (superseded) decision**

Invoke the `wiki-remember` skill (or follow its procedure directly) to capture this real
decision from this project's design history:

> Early in designing the interactive wiki-capture feature, storing conversation-derived
> decisions under a single flat `.wiki/decisions.md` log, or one decisions file grouped
> per existing structural topic page, were both considered as the storage layout.

Let the skill choose the category and filename per its own procedure (Steps 3-7 of the
skill). Confirm afterward that:
- The file exists at `.wiki/decisions/<category>/<date>-<slug>.md`.
- Frontmatter has `type: decision`, a `category`, `status: active`, `supersedes: null`,
  and today's date via `date +%Y-%m-%d` (not hardcoded).
- The body accurately reflects only the decision text given above — no invented detail.

- [ ] **Step 2: Capture the second decision, which supersedes the first**

Invoke the skill again to capture the real follow-up decision that changed the first:

> That flat-log/per-page-grouped approach was superseded: the wiki-remember skill instead
> lets the skill choose the category dynamically per finding — reusing an existing
> `.wiki/decisions/<category>/` directory when a finding fits, or creating a new one when
> it doesn't — and keeps `.wiki/index.md`'s "Decisions & rationale" section in sync with
> whichever categories exist, the same way `wiki update` keeps the index in sync with
> structural pages.

Confirm afterward that:
- A second file exists at `.wiki/decisions/<category>/<date>-<slug>.md`.
- Its frontmatter sets `supersedes: <path to the Step 1 file>`.
- The Step 1 file was edited in place: only its `status:` field changed, from `active` to
  `superseded` — no other content altered, file not deleted.

- [ ] **Step 3: Verify the index**

Open `.wiki/index.md` and confirm:
- A `## Decisions & rationale` section exists.
- It has a subsection for the category both files landed in (or two subsections, if the
  skill judged them to belong in different categories — either is a valid outcome of the
  skill's own judgment call, not a bug).
- Both entries are listed, and the first (superseded) entry's bullet is marked
  `(superseded)` rather than removed.

- [ ] **Step 4: Confirm no stray commit and correct trigger behavior**

Run `git status` and confirm the skill itself made no commit (working tree shows the new
`.wiki/` files as uncommitted changes, staged or unstaged — commit itself is this task's
job, not the skill's).

- [ ] **Step 5: Commit**

```bash
git add .wiki/
git commit -m "docs: capture first wiki-remember decisions (dogfood validation)"
```
