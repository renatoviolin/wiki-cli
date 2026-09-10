import argparse
import os
import sys

from .lint import LintFinding, lint_wiki
from .skills import install_all


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wiki",
        description="Local helpers for the .wiki knowledge base: mechanical lint checks and skill installation. Wiki content itself is written by the wiki-create, wiki-update, and wiki-remember skills.",
    )
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("lint", help="mechanical checks over .wiki on disk")
    sub.add_parser("install-skill", help="install wiki skills (wiki-remember, wiki-create, wiki-update) to this checkout and your home directory from github main")
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

    results = install_all()
    exit_code = 0
    for skill_result in results:
        if skill_result.success:
            if skill_result.message:
                print(skill_result.message)
        else:
            print(f"error: {skill_result.error or 'install failed'}", file=sys.stderr)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
