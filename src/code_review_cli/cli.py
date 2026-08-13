import argparse
import sys

from .result import ReviewResult
from .runner import run_review
from .validation import ValidationError, validate_pr, validate_provider, validate_repo


def _print_metrics(result: ReviewResult) -> None:
    parts = []
    if result.cost_usd is not None:
        parts.append(f"cost=${result.cost_usd:.4f}")
    if result.duration_ms is not None:
        parts.append(f"duration={result.duration_ms}ms")
    if result.num_turns is not None:
        parts.append(f"turns={result.num_turns}")
    if result.input_tokens is not None:
        parts.append(f"input_tokens={result.input_tokens}")
    if result.output_tokens is not None:
        parts.append(f"output_tokens={result.output_tokens}")
    if parts:
        print(f"[metrics] {' '.join(parts)}", file=sys.stderr)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="code-review",
        description="Run a headless Claude Code review against a pull request.",
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        provider = validate_provider(args.provider)
        pr = validate_pr(args.pr)
        repo = validate_repo(provider, args.repo)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result: ReviewResult = run_review(provider, repo, pr, verbose=args.verbose)
    _print_metrics(result)

    if result.success:
        print(result.text)
        return 0

    print(f"error: {result.error_message}", file=sys.stderr)
    return result.exit_code()


if __name__ == "__main__":
    sys.exit(main())
