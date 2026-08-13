import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

from .prompts import build_prompt
from .result import ReviewResult

_MAX_TURNS = 40


async def _run_review_async(provider: str, repo: str, pr: int) -> ReviewResult:
    try:
        workspace = Path(tempfile.mkdtemp(prefix="code-review-"))
        prompt = build_prompt(provider, repo, pr)
        options = ClaudeAgentOptions(
            cwd=str(workspace),
            permission_mode="bypassPermissions",
            max_turns=_MAX_TURNS,
        )

        last_message = None
        async for message in query(prompt=prompt, options=options):
            last_message = message
    except Exception as exc:
        return ReviewResult(success=False, text="", error_message=str(exc))

    if last_message is None or not hasattr(last_message, "is_error"):
        return ReviewResult(
            success=False,
            text="",
            error_message="Claude Code produced no result message",
        )

    cost_usd = getattr(last_message, "total_cost_usd", None)
    duration_ms = getattr(last_message, "duration_ms", None)
    num_turns = getattr(last_message, "num_turns", None)

    if last_message.is_error:
        return ReviewResult(
            success=False,
            text="",
            cost_usd=cost_usd,
            duration_ms=duration_ms,
            num_turns=num_turns,
            error_message=getattr(last_message, "result", None)
            or "Claude Code reported an error",
        )

    try:
        shutil.rmtree(workspace)
    except OSError as exc:
        print(
            f"warning: failed to clean up workspace {workspace}: {exc}",
            file=sys.stderr,
        )

    return ReviewResult(
        success=True,
        text=getattr(last_message, "result", None) or "",
        cost_usd=cost_usd,
        duration_ms=duration_ms,
        num_turns=num_turns,
    )


def run_review(provider: str, repo: str, pr: int) -> ReviewResult:
    return asyncio.run(_run_review_async(provider, repo, pr))
