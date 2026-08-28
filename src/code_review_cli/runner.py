import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

from .prompts import _RESULT_SCHEMA, build_prompt
from .result import ReviewResult

_MAX_TURNS = 150

_FALLBACK_ERROR = "Claude Code reported an error"
_MSG_RATE_LIMIT = "API error 429: rate limit or usage limit reached — check `claude status` for reset time and try again later"
_MSG_OVERLOADED = "API error 529: Anthropic API overloaded — retry shortly"
_SDK_SUCCESS_SENTINEL = "Claude Code returned an error result: success"
_SDK_GENERIC_FALLBACK = "Claude Code returned an error — check `claude status` for usage limit or try again later"


def _extract_error_detail(message) -> str:
    result = getattr(message, "result", None)
    if isinstance(result, str) and result.strip():
        return result.strip()
    errors = getattr(message, "errors", None) or []
    if errors:
        joined = "; ".join(str(e).strip() for e in errors if str(e).strip())
        if joined:
            return joined
    subtype = getattr(message, "subtype", None)
    if isinstance(subtype, str) and subtype.strip() and subtype != "success":
        return subtype.strip()
    api_error_status = getattr(message, "api_error_status", None)
    if api_error_status is not None:
        if api_error_status == 429:
            return _MSG_RATE_LIMIT
        if api_error_status == 529:
            return _MSG_OVERLOADED
        subtype_str = subtype.strip() if isinstance(subtype, str) and subtype.strip() else "unknown"
        return f"API error {api_error_status}: Claude Code returned an error (subtype={subtype_str}) — check `claude status` for details"
    return _FALLBACK_ERROR


def _extract_metrics(message) -> dict:
    cost_usd = getattr(message, "total_cost_usd", None)
    duration_ms = getattr(message, "duration_ms", None)
    num_turns = getattr(message, "num_turns", None)
    model_usage = getattr(message, "model_usage", None)
    if model_usage:
        input_tokens = sum(entry.get("inputTokens", 0) for entry in model_usage.values())
        output_tokens = sum(entry.get("outputTokens", 0) for entry in model_usage.values())
        cache_read_tokens = sum(entry.get("cacheReadInputTokens", 0) for entry in model_usage.values())
        cache_creation_tokens = sum(entry.get("cacheCreationInputTokens", 0) for entry in model_usage.values())
    else:
        input_tokens = None
        output_tokens = None
        cache_read_tokens = None
        cache_creation_tokens = None
    return {
        "cost_usd": cost_usd,
        "duration_ms": duration_ms,
        "num_turns": num_turns,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_creation_tokens": cache_creation_tokens,
    }


def _finalize_review_result(message) -> ReviewResult:
    metrics = _extract_metrics(message)
    if getattr(message, "is_error", False):
        return ReviewResult(success=False, text="", error_message=_extract_error_detail(message), **metrics)
    structured = getattr(message, "structured_output", None)
    if not isinstance(structured, dict) or not structured.get("success"):
        failure_reason = structured.get("failure_reason") if isinstance(structured, dict) else None
        return ReviewResult(success=False, text="", error_message=failure_reason or "Claude Code did not complete the review", **metrics)
    review_text = structured.get("review") or ""
    if not review_text:
        return ReviewResult(success=False, text="", error_message="Claude Code reported success but returned an empty review", **metrics)
    return ReviewResult(success=True, text=review_text, **metrics)


def _log_verbose_message(message) -> None:
    if hasattr(message, "is_error"):
        print(
            f"[result] is_error={message.is_error} num_turns={message.num_turns}",
            file=sys.stderr,
        )
    elif hasattr(message, "content") and hasattr(message, "model"):
        for block in message.content:
            if hasattr(block, "text"):
                print(f"[assistant] {block.text}", file=sys.stderr)
            elif hasattr(block, "name") and hasattr(block, "input"):
                print(f"[tool call] {block.name}({block.input})", file=sys.stderr)
            elif hasattr(block, "thinking"):
                print(f"[thinking] {block.thinking}", file=sys.stderr)
            else:
                print(f"[message] {block!r}", file=sys.stderr)
    elif hasattr(message, "content"):
        if isinstance(message.content, str):
            print(f"[user] {message.content}", file=sys.stderr)
        else:
            for block in message.content:
                if hasattr(block, "tool_use_id"):
                    print(f"[tool result] {block.content}", file=sys.stderr)
                else:
                    print(repr(block), file=sys.stderr)
    elif hasattr(message, "subtype") and hasattr(message, "data"):
        print(f"[system:{message.subtype}] {message.data}", file=sys.stderr)
    else:
        print(f"[message] {message!r}", file=sys.stderr)


async def _run_review_async(
    provider: str,
    repo: str,
    pr: int,
    verbose: bool,
    model: str | None = None,
    level: str = "standard",
) -> ReviewResult:
    last_message = None
    try:
        workspace = Path(tempfile.mkdtemp(prefix="code-review-"))
        prompt = build_prompt(provider, repo, pr, level)
        options = ClaudeAgentOptions(
            cwd=str(workspace),
            permission_mode="bypassPermissions",
            max_turns=_MAX_TURNS,
            setting_sources=["user", "project"],
            output_format={"type": "json_schema", "schema": _RESULT_SCHEMA},
            model=model,
        )

        async for message in query(prompt=prompt, options=options):
            if verbose:
                _log_verbose_message(message)
            if hasattr(message, "is_error"):
                last_message = message
    except Exception as exc:
        exc_str = str(exc)
        if _SDK_SUCCESS_SENTINEL not in exc_str:
            if last_message is not None and getattr(last_message, "is_error", False):
                return ReviewResult(success=False, text="", error_message=_extract_error_detail(last_message), **_extract_metrics(last_message))
            return ReviewResult(success=False, text="", error_message=exc_str)
        if last_message is None:
            return ReviewResult(success=False, text="", error_message=_SDK_GENERIC_FALLBACK)
        detail = _extract_error_detail(last_message)
        if detail == _FALLBACK_ERROR:
            return ReviewResult(success=False, text="", error_message=_SDK_GENERIC_FALLBACK)
        if getattr(last_message, "is_error", False):
            return ReviewResult(success=False, text="", error_message=detail, **_extract_metrics(last_message))
        return ReviewResult(success=False, text="", error_message=detail)

    if last_message is None:
        return ReviewResult(success=False, text="", error_message="Claude Code produced no result message")
    result = _finalize_review_result(last_message)
    if result.success:
        try:
            shutil.rmtree(workspace)
        except OSError as exc:
            print(f"warning: failed to clean up workspace {workspace}: {exc}", file=sys.stderr)
    return result


def run_review(
    provider: str,
    repo: str,
    pr: int,
    verbose: bool = False,
    model: str | None = None,
    level: str = "standard",
) -> ReviewResult:
    try:
        return asyncio.run(
            _run_review_async(provider, repo, pr, verbose, model, level)
        )
    except Exception as exc:
        return ReviewResult(success=False, text="", error_message=str(exc))
