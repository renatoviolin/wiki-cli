import asyncio
import os
import sys

from claude_agent_sdk import ClaudeAgentOptions, query

from .prompts import _RESULT_SCHEMA, build_prompt
from .result import WikiResult

_MAX_TURNS = 150


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


async def _run_wiki_async(
    mode: str, verbose: bool, model: str | None = None
) -> WikiResult:
    try:
        prompt = build_prompt(mode)
        options = ClaudeAgentOptions(
            cwd=os.getcwd(),
            permission_mode="bypassPermissions",
            max_turns=_MAX_TURNS,
            setting_sources=["user", "project"],
            output_format={"type": "json_schema", "schema": _RESULT_SCHEMA},
            model=model,
        )

        last_message = None
        async for message in query(prompt=prompt, options=options):
            if verbose:
                _log_verbose_message(message)
            if hasattr(message, "is_error"):
                last_message = message
    except Exception as exc:
        return WikiResult(success=False, text="", error_message=str(exc))

    if last_message is None:
        return WikiResult(
            success=False,
            text="",
            error_message="Claude Code produced no result message",
        )

    cost_usd = getattr(last_message, "total_cost_usd", None)
    duration_ms = getattr(last_message, "duration_ms", None)
    num_turns = getattr(last_message, "num_turns", None)

    model_usage = getattr(last_message, "model_usage", None)
    if model_usage:
        input_tokens = sum(entry.get("inputTokens", 0) for entry in model_usage.values())
        output_tokens = sum(
            entry.get("outputTokens", 0) for entry in model_usage.values()
        )
        cache_read_tokens = sum(
            entry.get("cacheReadInputTokens", 0) for entry in model_usage.values()
        )
        cache_creation_tokens = sum(
            entry.get("cacheCreationInputTokens", 0) for entry in model_usage.values()
        )
    else:
        input_tokens = None
        output_tokens = None
        cache_read_tokens = None
        cache_creation_tokens = None

    metrics = {
        "cost_usd": cost_usd,
        "duration_ms": duration_ms,
        "num_turns": num_turns,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_creation_tokens": cache_creation_tokens,
    }

    if last_message.is_error:
        errors = getattr(last_message, "errors", None) or []
        detail = (
            getattr(last_message, "result", None)
            or (errors[0] if errors else None)
            or getattr(last_message, "subtype", None)
            or "Claude Code reported an error"
        )
        return WikiResult(success=False, text="", error_message=detail, **metrics)

    structured = getattr(last_message, "structured_output", None)
    if not isinstance(structured, dict) or not structured.get("success"):
        failure_reason = (
            structured.get("failure_reason") if isinstance(structured, dict) else None
        )
        return WikiResult(
            success=False,
            text="",
            error_message=failure_reason or "Claude Code did not complete the wiki run",
            **metrics,
        )

    return WikiResult(
        success=True,
        text=structured.get("summary") or "",
        pages_written=structured.get("pages_written") or [],
        **metrics,
    )


def run_wiki(
    mode: str, verbose: bool = False, model: str | None = None
) -> WikiResult:
    try:
        return asyncio.run(_run_wiki_async(mode, verbose, model))
    except Exception as exc:
        return WikiResult(success=False, text="", error_message=str(exc))
