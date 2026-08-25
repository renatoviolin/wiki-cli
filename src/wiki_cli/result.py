from dataclasses import dataclass, field


@dataclass
class WikiResult:
    success: bool
    text: str
    pages_written: list[str] = field(default_factory=list)
    cost_usd: float | None = None
    duration_ms: int | None = None
    num_turns: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None
    error_message: str | None = None

    def exit_code(self) -> int:
        return 0 if self.success else 1
