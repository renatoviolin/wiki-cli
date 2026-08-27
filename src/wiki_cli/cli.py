import argparse
import os
import sys

from .lint import LintFinding, lint_wiki
from .result import WikiResult
from .runner import run_wiki

_MODEL_ALIASES = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-5",
    "opus": "claude-opus-5",
}


def _print_metrics(result: WikiResult, mode: str) -> None:
    parts = [f"mode={mode}"]
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
    if result.cache_read_tokens is not None:
        parts.append(f"cache_read_tokens={result.cache_read_tokens}")
    if result.cache_creation_tokens is not None:
        parts.append(f"cache_creation_tokens={result.cache_creation_tokens}")
    print(f"[metrics] {' '.join(parts)}", file=sys.stderr)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wiki",
        description=(
            "Generate or update the .wiki knowledge base for the current repository."
        ),
    )
    parser.add_argument("mode", choices=["create", "update", "lint"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--verbose", action="store_true")
    return parser


def _print_lint_report(findings: list[LintFinding]) -> int:
    for finding in findings:
        print(f"{finding.severity}: {finding.file}:{finding.line}: {finding.message}")

    errors = [f for f in findings if f.severity == "error"]
    advisories = [f for f in findings if f.severity == "advisory"]
    print(f"{len(errors)} error(s), {len(advisories)} advisory(ies)")

    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.mode == "lint":
        return _print_lint_report(lint_wiki(os.getcwd()))

    model = None
    if args.model is not None:
        model = _MODEL_ALIASES.get(args.model.lower())
        if model is None:
            print(
                f"error: --model must be one of {sorted(_MODEL_ALIASES)}, "
                f"got {args.model!r}",
                file=sys.stderr,
            )
            return 2

    result: WikiResult = run_wiki(args.mode, verbose=args.verbose, model=model)
    _print_metrics(result, args.mode)

    if result.success:
        print(result.text)
        for page in result.pages_written:
            print(page)
        return 0

    print(f"error: {result.error_message}", file=sys.stderr)
    return result.exit_code()


if __name__ == "__main__":
    sys.exit(main())
