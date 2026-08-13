from dataclasses import dataclass


@dataclass
class ReviewResult:
    success: bool
    text: str
    cost_usd: float | None = None
    duration_ms: int | None = None
    num_turns: int | None = None
    error_message: str | None = None

    def exit_code(self) -> int:
        return 0 if self.success else 1
