import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

from .prompts import _RESULT_SCHEMA, build_prompt
from .result import ReviewResult

_MAX_TURNS = 60


async def _run_review_async(provider: str, repo: str, pr: int) -> ReviewResult:
    try:
        workspace = Path(tempfile.mkdtemp(prefix="code-review-"))
        prompt = build_prompt(provider, repo, pr)
        options = ClaudeAgentOptions(
            cwd=str(workspace),
            permission_mode="bypassPermissions",
            max_turns=_MAX_TURNS,
            setting_sources=["user", "project"],
            output_format={"type": "json_schema", "schema": _RESULT_SCHEMA},
        )

        last_message = None
        async for message in query(prompt=prompt, options=options):
            if hasattr(message, "is_error"):
                last_message = message
    except Exception as exc:
        return ReviewResult(success=False, text="", error_message=str(exc))

    if last_message is None:
        return ReviewResult(
            success=False,
            text="",
            error_message="Claude Code produced no result message",
        )

    cost_usd = getattr(last_message, "total_cost_usd", None)
    duration_ms = getattr(last_message, "duration_ms", None)
    num_turns = getattr(last_message, "num_turns", None)

    if last_message.is_error:
        subtype = getattr(last_message, "subtype", None)
        errors = getattr(last_message, "errors", None) or []
        detail = (
            getattr(last_message, "result", None)
            or (errors[0] if errors else None)
            or subtype
            or "Claude Code reported an error"
        )
        return ReviewResult(
            success=False,
            text="",
            cost_usd=cost_usd,
            duration_ms=duration_ms,
            num_turns=num_turns,
            error_message=detail,
        )

    structured = getattr(last_message, "structured_output", None)
    if not isinstance(structured, dict) or not structured.get("success"):
        failure_reason = (
            structured.get("failure_reason") if isinstance(structured, dict) else None
        )
        return ReviewResult(
            success=False,
            text="",
            cost_usd=cost_usd,
            duration_ms=duration_ms,
            num_turns=num_turns,
            error_message=failure_reason or "Claude Code did not complete the review",
        )

    review_text = structured.get("review") or ""
    if not review_text:
        return ReviewResult(
            success=False,
            text="",
            cost_usd=cost_usd,
            duration_ms=duration_ms,
            num_turns=num_turns,
            error_message="Claude Code reported success but returned an empty review",
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
        text=review_text,
        cost_usd=cost_usd,
        duration_ms=duration_ms,
        num_turns=num_turns,
    )


def run_review(provider: str, repo: str, pr: int) -> ReviewResult:
    try:
        return asyncio.run(_run_review_async(provider, repo, pr))
    except Exception as exc:
        return ReviewResult(success=False, text="", error_message=str(exc))
