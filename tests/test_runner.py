import types

import pytest

import code_review_cli.runner as runner_module
from code_review_cli.result import ReviewResult


def _fake_query_factory(final_message):
    async def _fake_query(prompt, options):
        yield final_message

    return _fake_query


def test_run_review_returns_success_result(monkeypatch, tmp_path):
    final_message = types.SimpleNamespace(
        is_error=False,
        result="No issues found.",
        total_cost_usd=0.05,
        duration_ms=3200,
        num_turns=4,
    )
    monkeypatch.setattr(
        runner_module, "query", _fake_query_factory(final_message)
    )
    monkeypatch.setattr(
        runner_module.tempfile, "mkdtemp", lambda prefix: str(tmp_path)
    )

    result = runner_module.run_review("github", "org/repo", 29)

    assert isinstance(result, ReviewResult)
    assert result.success is True
    assert result.text == "No issues found."
    assert result.cost_usd == 0.05
    assert result.duration_ms == 3200
    assert result.num_turns == 4


def test_run_review_returns_failure_result_when_claude_reports_error(
    monkeypatch, tmp_path
):
    final_message = types.SimpleNamespace(
        is_error=True,
        result="hit max turns before finishing",
        total_cost_usd=0.20,
        duration_ms=9000,
        num_turns=20,
    )
    monkeypatch.setattr(
        runner_module, "query", _fake_query_factory(final_message)
    )
    monkeypatch.setattr(
        runner_module.tempfile, "mkdtemp", lambda prefix: str(tmp_path)
    )

    result = runner_module.run_review("github", "org/repo", 29)

    assert result.success is False
    assert result.error_message == "hit max turns before finishing"


def test_run_review_returns_failure_result_when_no_message_is_produced(
    monkeypatch, tmp_path
):
    async def _empty_query(prompt, options):
        return
        yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(runner_module, "query", _empty_query)
    monkeypatch.setattr(
        runner_module.tempfile, "mkdtemp", lambda prefix: str(tmp_path)
    )

    result = runner_module.run_review("github", "org/repo", 29)

    assert result.success is False
    assert "no result" in result.error_message.lower()


def test_run_review_keeps_workspace_on_failure(monkeypatch, tmp_path):
    final_message = types.SimpleNamespace(
        is_error=True,
        result="boom",
        total_cost_usd=0.0,
        duration_ms=100,
        num_turns=1,
    )
    monkeypatch.setattr(
        runner_module, "query", _fake_query_factory(final_message)
    )
    monkeypatch.setattr(
        runner_module.tempfile, "mkdtemp", lambda prefix: str(tmp_path)
    )

    runner_module.run_review("github", "org/repo", 29)

    assert tmp_path.exists()


def test_run_review_removes_workspace_on_success(monkeypatch, tmp_path):
    final_message = types.SimpleNamespace(
        is_error=False,
        result="all good",
        total_cost_usd=0.0,
        duration_ms=100,
        num_turns=1,
    )
    monkeypatch.setattr(
        runner_module, "query", _fake_query_factory(final_message)
    )
    monkeypatch.setattr(
        runner_module.tempfile, "mkdtemp", lambda prefix: str(tmp_path)
    )

    runner_module.run_review("github", "org/repo", 29)

    assert not tmp_path.exists()


def test_run_review_returns_failure_result_when_workspace_creation_fails(
    monkeypatch
):
    def _boom(prefix):
        raise OSError("disk full")

    monkeypatch.setattr(runner_module.tempfile, "mkdtemp", _boom)

    result = runner_module.run_review("github", "org/repo", 29)

    assert result.success is False
    assert "disk full" in result.error_message


def test_run_review_still_succeeds_if_cleanup_fails(monkeypatch, tmp_path, capsys):
    final_message = types.SimpleNamespace(
        is_error=False,
        result="all good",
        total_cost_usd=0.0,
        duration_ms=100,
        num_turns=1,
    )
    monkeypatch.setattr(
        runner_module, "query", _fake_query_factory(final_message)
    )
    monkeypatch.setattr(
        runner_module.tempfile, "mkdtemp", lambda prefix: str(tmp_path)
    )

    def _boom(path):
        raise OSError("permission denied")

    monkeypatch.setattr(runner_module.shutil, "rmtree", _boom)

    result = runner_module.run_review("github", "org/repo", 29)

    assert result.success is True
    assert "permission denied" in capsys.readouterr().err
