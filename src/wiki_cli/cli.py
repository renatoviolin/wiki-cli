import argparse
import os
import sys

from .lint import LintFinding, lint_wiki
from .result import WikiResult
from .skill_gen import write_skill_files
from .skills import DEFAULT_SKILLS, install_skill

try:
    from .runner import run_wiki
except ModuleNotFoundError:
    run_wiki = None  # type: ignore

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
        description="Generate or update the .wiki knowledge base for the current repository.",
    )
    sub = parser.add_subparsers(dest="mode", required=True)
    p_create = sub.add_parser("create", help="inventory and write .wiki from scratch")
    p_create.add_argument("--model", default=None, help="model alias: haiku|sonnet|opus (default: sonnet)")
    p_create.add_argument("--verbose", action="store_true")
    p_update = sub.add_parser("update", help="update .wiki for changes since last wiki commit")
    p_update.add_argument("--model", default=None, help="model alias: haiku|sonnet|opus (default: sonnet)")
    p_update.add_argument("--verbose", action="store_true")
    p_lint = sub.add_parser("lint", help="mechanical checks over .wiki on disk")
    p_lint.add_argument("--model", default=None, help="model alias: haiku|sonnet|opus (default: sonnet, ignored for lint)")
    p_lint.add_argument("--verbose", action="store_true")
    p_install = sub.add_parser("install-skill", help="install wiki skills from github main (default: wiki-remember, wiki-create, wiki-update)")
    p_install.add_argument("skill", nargs="?", default=None, help="skill name (default: installs wiki-remember, wiki-create, and wiki-update)")
    p_install.add_argument("--force", action="store_true", help="overwrite existing SKILL.md")
    p_install.add_argument("--dry-run", action="store_true", help="print what would happen without writing")
    p_install.add_argument("--target", choices=["claude", "copilot", "all"], default="all", help="install target: claude (.claude/skills), copilot (.github/skills), or all (default)")
    sub.add_parser("generate-skills", help="regenerate .claude/skills/wiki-create and wiki-update SKILL.md from prompts.py (dev-only)")
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

    if args.mode == "generate-skills":
        for path in write_skill_files():
            print(path)
        return 0

    if args.mode == "install-skill":
        names = [args.skill] if args.skill else DEFAULT_SKILLS
        exit_code = 0
        for name in names:
            skill_result = install_skill(skill=name, target_dir=os.getcwd(), force=args.force, dry_run=args.dry_run, target=args.target)
            if skill_result.success:
                if skill_result.message:
                    print(skill_result.message)
            else:
                print(f"error: {skill_result.error or 'install failed'}", file=sys.stderr)
                exit_code = 1
        return exit_code

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
    else:
        if args.mode in ("create", "update"):
            model = _MODEL_ALIASES["sonnet"]

    if run_wiki is None:
        print("error: wiki create/update requires claude-agent-sdk (not installed)", file=sys.stderr)
        return 1
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
