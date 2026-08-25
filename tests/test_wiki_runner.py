import os
import types

import wiki_cli.runner as runner_module
from wiki_cli.result import WikiResult


def _fake_query_factory(*messages):
    async def _fake_query(prompt, options):
        for message in messages:
            yield message

    return _fake_query


def _success_message(**overrides):
    payload = {
        "is_error": False,
        "result": "wiki written",
        "structured_output": {
            "success": True,
            "summary": "Wrote 4 pages",
            "pages_written": [".wiki/index.md", ".wiki/api.md"],
            "failure_reason": "",
        },
        "total_cost_usd": 0.03,
        "duration_ms": 2500,
        "num_turns": 7,
    }
    payload.update(overrides)
    return types.SimpleNamespace(**payload)


def test_run_wiki_returns_success_result(monkeypatch):
    monkeypatch.setattr(runner_module, "query", _fake_query_factory(_success_message()))

    result = runner_module.run_wiki("create")

    assert isinstance(result, WikiResult)
    assert result.success is True
    assert result.text == "Wrote 4 pages"
    assert result.pages_written == [".wiki/index.md", ".wiki/api.md"]
    assert result.cost_usd == 0.03
    assert result.duration_ms == 2500
    assert result.num_turns == 7


def test_run_wiki_runs_in_current_directory_not_a_temp_workspace(monkeypatch):
    captured = {}

    async def _fake_query(prompt, options):
        captured["options"] = options
        yield _success_message()

    monkeypatch.setattr(runner_module, "query", _fake_query)

    runner_module.run_wiki("create")

    assert captured["options"].cwd == os.getcwd()


def test_run_wiki_wires_setting_sources_output_format_and_max_turns(monkeypatch):
    captured = {}

    async def _fake_query(prompt, options):
        captured["options"] = options
        yield _success_message()

    monkeypatch.setattr(runner_module, "query", _fake_query)

    runner_module.run_wiki("create")

    options = captured["options"]
    assert options.setting_sources == ["user", "project"]
    assert options.output_format == {
        "type": "json_schema",
        "schema": runner_module._RESULT_SCHEMA,
    }
    assert options.max_turns == 150
    assert options.model is None


def test_run_wiki_threads_mode_through_to_build_prompt(monkeypatch):
    captured = {}

    def _fake_build_prompt(mode):
        captured["mode"] = mode
        return "prompt text"

    monkeypatch.setattr(runner_module, "build_prompt", _fake_build_prompt)
    monkeypatch.setattr(runner_module, "query", _fake_query_factory(_success_message()))

    runner_module.run_wiki("update")

    assert captured["mode"] == "update"


def test_run_wiki_threads_model_through_to_options(monkeypatch):
    captured = {}

    async def _fake_query(prompt, options):
        captured["options"] = options
        yield _success_message()

    monkeypatch.setattr(runner_module, "query", _fake_query)

    runner_module.run_wiki("create", model="claude-opus-5")

    assert captured["options"].model == "claude-opus-5"


def test_run_wiki_aggregates_token_counts_from_model_usage(monkeypatch):
    message = _success_message(
        model_usage={
            "claude-opus-5": {
                "inputTokens": 1000,
                "outputTokens": 200,
                "cacheReadInputTokens": 5000,
                "cacheCreationInputTokens": 300,
            },
            "claude-haiku-4-5": {
                "inputTokens": 500,
                "outputTokens": 100,
                "cacheReadInputTokens": 2000,
                "cacheCreationInputTokens": 100,
            },
        }
    )
    monkeypatch.setattr(runner_module, "query", _fake_query_factory(message))

    result = runner_module.run_wiki("create")

    assert result.input_tokens == 1500
    assert result.output_tokens == 300
    assert result.cache_read_tokens == 7000
    assert result.cache_creation_tokens == 400


def test_run_wiki_returns_failure_when_claude_reports_error(monkeypatch):
    message = types.SimpleNamespace(
        is_error=True,
        result="hit max turns",
        total_cost_usd=0.1,
        duration_ms=9000,
        num_turns=150,
    )
    monkeypatch.setattr(runner_module, "query", _fake_query_factory(message))

    result = runner_module.run_wiki("create")

    assert result.success is False
    assert result.error_message == "hit max turns"


def test_run_wiki_returns_failure_when_task_itself_failed(monkeypatch):
    message = _success_message(
        structured_output={
            "success": False,
            "summary": "",
            "pages_written": [],
            "failure_reason": "not a git repository",
        }
    )
    monkeypatch.setattr(runner_module, "query", _fake_query_factory(message))

    result = runner_module.run_wiki("create")

    assert result.success is False
    assert result.error_message == "not a git repository"


def test_run_wiki_returns_failure_when_no_message_is_produced(monkeypatch):
    async def _empty_query(prompt, options):
        return
        yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(runner_module, "query", _empty_query)

    result = runner_module.run_wiki("create")

    assert result.success is False
    assert "no result" in result.error_message.lower()


def test_run_wiki_does_not_raise_when_asyncio_run_raises(monkeypatch):
    def _boom(coro):
        coro.close()
        raise RuntimeError("cannot be called from a running event loop")

    monkeypatch.setattr(runner_module.asyncio, "run", _boom)

    result = runner_module.run_wiki("create")

    assert isinstance(result, WikiResult)
    assert result.success is False
    assert "running event loop" in result.error_message


def test_run_wiki_verbose_logs_assistant_text(monkeypatch, capsys):
    assistant = types.SimpleNamespace(
        content=[types.SimpleNamespace(text="Reading the repository")],
        model="claude-sonnet-5",
    )
    monkeypatch.setattr(
        runner_module,
        "query",
        _fake_query_factory(assistant, _success_message()),
    )

    result = runner_module.run_wiki("create", verbose=True)

    assert "Reading the repository" in capsys.readouterr().err
    assert result.success is True


def test_run_wiki_default_verbose_produces_no_intermediate_output(monkeypatch, capsys):
    assistant = types.SimpleNamespace(
        content=[types.SimpleNamespace(text="Reading the repository")],
        model="claude-sonnet-5",
    )
    monkeypatch.setattr(
        runner_module,
        "query",
        _fake_query_factory(assistant, _success_message()),
    )

    runner_module.run_wiki("create")

    assert "Reading the repository" not in capsys.readouterr().err
