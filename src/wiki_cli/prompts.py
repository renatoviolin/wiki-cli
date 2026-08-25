_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "summary": {"type": "string"},
        "pages_written": {"type": "array", "items": {"type": "string"}},
        "failure_reason": {"type": "string"},
    },
    "required": ["success", "summary", "pages_written", "failure_reason"],
    "additionalProperties": False,
}

_SHARED_PREAMBLE = """You are running headless inside a developer's local checkout of a \
repository, with full read/write access to the filesystem and the installed CLI tools \
(git). Do the following:

1. Resolve the repository root by running `git rev-parse --show-toplevel`, and treat \
every path below as relative to that root. The knowledge base lives in `.wiki/` at that \
root. If the current directory is not inside a git repository, stop and reply with the \
failure JSON shape below.
{mode_instructions}
3. Reply with a JSON object matching this exact shape:
   - On success: {{"success": true, "summary": "<one short paragraph describing what you \
wrote or changed>", "pages_written": ["<repo-relative path>", ...], "failure_reason": ""}}
   - On failure: {{"success": false, "summary": "", "pages_written": [], \
"failure_reason": "<a short, specific explanation of what went wrong>"}}

{quality_rules}
"""

_QUALITY_RULES = """How to write the pages:

- Write for an AI agent that will read this before reviewing a pull request or building a \
feature in this repository. Favour what someone needs to know that is not obvious from \
reading a single file: how the pieces fit together, what flows through what, which \
invariants hold across the codebase, and where the surprising parts are.
- Cite evidence as `file:line` (for example `src/api/handler.go:42`) for factual claims, \
so any reader can check them against the code.
- Do not invent identifiers. Never state a type, field, function, route, table, or column \
name unless you have read it in the source and are copying it exactly. When you are \
describing something whose exact name you have not verified, describe the behaviour and \
the flow instead of naming the symbol. A confidently wrong name is worse than a general \
description, because an agent will write code against it.
- Prefer accuracy over coverage. A short page that is entirely correct is more useful than \
a thorough page containing invented detail.
- The code is the source of truth. Write nothing that contradicts it, and do not restate \
large amounts of code that a reader could simply open.
- Do not commit anything and do not run `git add`, `git commit`, or `git push`. Write the \
files and stop; the developer reviews and commits them alongside their own work.
"""

_CREATE_INSTRUCTIONS = """2. Create the knowledge base from scratch. Explore the \
repository to understand what it does and how it is organised, then write:
   - `.wiki/index.md` — a short overview of the project plus a linked table of contents \
listing every other page with a one-line description.
   - One page per significant area, named after that area (for example \
`.wiki/authentication.md`, `.wiki/data-model.md`). Judge what counts as significant from \
the repository's own structure; a top-level package, a bounded domain, or a cross-cutting \
concern each make a reasonable page. Prefer a handful of substantial pages over many thin \
ones.
   If a `.wiki/` directory already exists, treat this as a full regeneration: keep the \
directory, rewrite the pages that are now wrong, and remove pages whose subject no longer \
exists."""

_UPDATE_INSTRUCTIONS = """2. Update the existing knowledge base to match the current \
code. Work out what changed since the wiki was last written:
   - Find the commit that last touched the wiki: \
`git log -1 --format=%H -- .wiki/`
   - Diff that commit against `HEAD` to see what has changed since: \
`git diff --name-status <that-commit>..HEAD`
   - If `.wiki/` does not exist yet, or that command returns nothing because the wiki has \
never been committed, fall back to reading the whole repository and creating the pages \
from scratch.
   Then update only the pages affected by those changes, refresh \
`.wiki/index.md` if the set of pages changed, and delete any page whose subject was \
removed from the codebase. Leave unaffected pages untouched."""

_MODE_INSTRUCTIONS = {
    "create": _CREATE_INSTRUCTIONS,
    "update": _UPDATE_INSTRUCTIONS,
}


def build_prompt(mode: str) -> str:
    return _SHARED_PREAMBLE.format(
        mode_instructions=_MODE_INSTRUCTIONS[mode],
        quality_rules=_QUALITY_RULES,
    )
