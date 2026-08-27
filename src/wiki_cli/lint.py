import os
import re
from dataclasses import dataclass

_HEADER_WITH_FILE_RE = re.compile(r"^##\s.*—\s*`([^`\s]+\.\w+)`\s*$")
_HEADER_RE = re.compile(r"^##\s")
_SOURCES_HEADING_RE = re.compile(r"^##\s+Sources\s*$")
_ANY_HEADING_RE = re.compile(r"^#{1,6}\s")
_SOURCES_BULLET_PATH_RE = re.compile(r"`([\w./-]+\.\w+)`")
_PYTEST_CITATION_RE = re.compile(r"`([\w./-]+\.py)::([A-Za-z_][A-Za-z0-9_]*)`")
_BARE_SYMBOL_RE = re.compile(r"`(_?[A-Za-z][A-Za-z0-9_]*)`")
_DEF_OR_CLASS_RE_TEMPLATE = r"^\s*(def|class)\s+{}\b"

_COMMON_KEYWORD_STOPLIST = {
    "haiku", "sonnet", "opus", "create", "update", "lint", "light", "standard",
    "hard", "github", "codecommit", "verbose", "model", "level", "provider",
    "repo", "pr", "gh", "aws", "git", "wiki", "json", "python", "true", "false",
    "none", "null", "mode",
}


@dataclass
class LintFinding:
    file: str
    line: int
    severity: str
    message: str


def lint_wiki(repo_root: str) -> list[LintFinding]:
    wiki_dir = os.path.join(repo_root, ".wiki")
    findings: list[LintFinding] = []

    for page_path in _iter_wiki_pages(wiki_dir):
        rel_page = os.path.relpath(page_path, repo_root)
        lines = _read_lines(page_path)
        is_decision = "decisions" in os.path.relpath(page_path, wiki_dir).split(os.sep)
        is_index = os.path.basename(page_path) == "index.md"

        if not is_decision and not is_index:
            findings.extend(_check_sources_section(rel_page, lines, repo_root))

        findings.extend(_check_pytest_citations(rel_page, lines, repo_root))
        findings.extend(_check_header_attributed_symbols(rel_page, lines, repo_root))

    return findings


def _iter_wiki_pages(wiki_dir: str) -> list[str]:
    pages = []
    for dirpath, _dirnames, filenames in os.walk(wiki_dir):
        for filename in filenames:
            if filename.endswith(".md"):
                pages.append(os.path.join(dirpath, filename))
    return sorted(pages)


def _read_lines(path: str) -> list[str]:
    with open(path, encoding="utf-8") as handle:
        return handle.read().splitlines()


def _check_sources_section(rel_page: str, lines: list[str], repo_root: str) -> list[LintFinding]:
    start = None
    for i, line in enumerate(lines):
        if _SOURCES_HEADING_RE.match(line):
            start = i
            break

    if start is None:
        return [
            LintFinding(
                file=rel_page,
                line=len(lines) or 1,
                severity="error",
                message="page is missing a `## Sources` section",
            )
        ]

    body_end = len(lines)
    for i in range(start + 1, len(lines)):
        if _ANY_HEADING_RE.match(lines[i]):
            body_end = i
            break

    findings = []
    found_path = False
    for i in range(start + 1, body_end):
        for match in _SOURCES_BULLET_PATH_RE.finditer(lines[i]):
            found_path = True
            cited_path = match.group(1)
            if not os.path.exists(os.path.join(repo_root, cited_path)):
                findings.append(
                    LintFinding(
                        file=rel_page,
                        line=i + 1,
                        severity="error",
                        message=f"Sources entry `{cited_path}` does not exist",
                    )
                )

    if not found_path:
        findings.append(
            LintFinding(
                file=rel_page,
                line=start + 1,
                severity="error",
                message="`## Sources` section has no recognizable path entries",
            )
        )

    return findings


def _check_pytest_citations(rel_page: str, lines: list[str], repo_root: str) -> list[LintFinding]:
    findings = []
    for i, line in enumerate(lines):
        for match in _PYTEST_CITATION_RE.finditer(line):
            cited_path, symbol = match.group(1), match.group(2)
            abs_path = os.path.join(repo_root, cited_path)
            if not os.path.exists(abs_path):
                findings.append(
                    LintFinding(
                        file=rel_page,
                        line=i + 1,
                        severity="error",
                        message=f"citation `{cited_path}::{symbol}` — file does not exist",
                    )
                )
                continue

            with open(abs_path, encoding="utf-8") as handle:
                content = handle.read()

            if not re.search(_DEF_OR_CLASS_RE_TEMPLATE.format(re.escape(symbol)), content, re.MULTILINE):
                findings.append(
                    LintFinding(
                        file=rel_page,
                        line=i + 1,
                        severity="error",
                        message=f"citation `{cited_path}::{symbol}` — symbol not found in file",
                    )
                )

    return findings


def _check_header_attributed_symbols(rel_page: str, lines: list[str], repo_root: str) -> list[LintFinding]:
    findings = []
    active_file = None
    flagged_in_file = set()

    for i, line in enumerate(lines):
        header_match = _HEADER_WITH_FILE_RE.match(line)
        if header_match:
            active_file = _resolve_bare_filename(header_match.group(1), repo_root)
            flagged_in_file = set()
            continue

        if _HEADER_RE.match(line):
            active_file = None
            flagged_in_file = set()
            continue

        if active_file is None:
            continue

        if "::" in line:
            continue

        for match in _BARE_SYMBOL_RE.finditer(line):
            symbol = match.group(1)
            key = symbol.lower()
            if key in _COMMON_KEYWORD_STOPLIST or symbol in flagged_in_file:
                continue

            with open(active_file, encoding="utf-8") as handle:
                content = handle.read()

            if symbol not in content:
                flagged_in_file.add(symbol)
                findings.append(
                    LintFinding(
                        file=rel_page,
                        line=i + 1,
                        severity="advisory",
                        message=(
                            f"possible stale reference: `{symbol}` not found in "
                            f"{os.path.relpath(active_file, repo_root)}"
                        ),
                    )
                )

    return findings


def _resolve_bare_filename(filename: str, repo_root: str) -> str | None:
    if os.sep in filename or "/" in filename:
        candidate = os.path.join(repo_root, filename)
        return candidate if os.path.exists(candidate) else None

    matches = []
    for dirpath, _dirnames, filenames in os.walk(os.path.join(repo_root, "src")):
        if filename in filenames:
            matches.append(os.path.join(dirpath, filename))

    return matches[0] if len(matches) == 1 else None
