from code_review_cli.result import ReviewResult


def test_successful_result_has_exit_code_zero():
    result = ReviewResult(success=True, text="looks good")
    assert result.exit_code() == 0


def test_failed_result_has_exit_code_one():
    result = ReviewResult(success=False, text="", error_message="boom")
    assert result.exit_code() == 1


def test_result_carries_optional_metadata():
    result = ReviewResult(
        success=True,
        text="looks good",
        cost_usd=0.12,
        duration_ms=4500,
        num_turns=6,
    )
    assert result.cost_usd == 0.12
    assert result.duration_ms == 4500
    assert result.num_turns == 6
