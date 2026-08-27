import textwrap

from wiki_cli.lint import lint_wiki


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content))


def _mod_py(tmp_path):
    mod = tmp_path / "src" / "pkg" / "mod.py"
    _write(
        mod,
        """
        _CONST = 1

        def real_func():
            return _CONST
        """,
    )
    return mod


def test_lint_flags_page_missing_sources_section(tmp_path):
    _mod_py(tmp_path)
    _write(
        tmp_path / ".wiki" / "page.md",
        """
        # Page

        Some prose with no Sources section at all.
        """,
    )

    findings = lint_wiki(str(tmp_path))

    assert any(
        f.severity == "error" and "Sources" in f.message and f.file.endswith("page.md")
        for f in findings
    )


def test_lint_accepts_page_with_valid_sources_section(tmp_path):
    _mod_py(tmp_path)
    _write(
        tmp_path / ".wiki" / "page.md",
        """
        # Page

        Some prose.

        ## Sources

        - `src/pkg/mod.py`
        """,
    )

    findings = lint_wiki(str(tmp_path))

    assert not any("Sources" in f.message for f in findings)


def test_lint_flags_sources_path_that_does_not_exist(tmp_path):
    _mod_py(tmp_path)
    _write(
        tmp_path / ".wiki" / "page.md",
        """
        # Page

        ## Sources

        - `src/pkg/missing.py`
        """,
    )

    findings = lint_wiki(str(tmp_path))

    assert any(
        f.severity == "error" and "src/pkg/missing.py" in f.message for f in findings
    )


def test_lint_skips_index_and_decisions_for_sources_check(tmp_path):
    _mod_py(tmp_path)
    _write(
        tmp_path / ".wiki" / "index.md",
        """
        # Index

        No Sources section here, and that's fine.
        """,
    )
    _write(
        tmp_path / ".wiki" / "decisions" / "cat" / "d.md",
        """
        ---
        type: decision
        ---

        # A decision

        No Sources section here either.
        """,
    )

    findings = lint_wiki(str(tmp_path))

    assert findings == []


def test_lint_accepts_valid_pytest_style_citation(tmp_path):
    _mod_py(tmp_path)
    _write(
        tmp_path / ".wiki" / "page.md",
        """
        # Page

        See `src/pkg/mod.py::real_func` for details.

        ## Sources

        - `src/pkg/mod.py`
        """,
    )

    findings = lint_wiki(str(tmp_path))

    assert not any("real_func" in f.message for f in findings)


def test_lint_flags_pytest_style_citation_with_missing_symbol(tmp_path):
    _mod_py(tmp_path)
    _write(
        tmp_path / ".wiki" / "page.md",
        """
        # Page

        See `src/pkg/mod.py::fake_func` for details.

        ## Sources

        - `src/pkg/mod.py`
        """,
    )

    findings = lint_wiki(str(tmp_path))

    assert any(
        f.severity == "error" and "fake_func" in f.message for f in findings
    )


def test_lint_flags_pytest_style_citation_with_missing_file(tmp_path):
    _mod_py(tmp_path)
    _write(
        tmp_path / ".wiki" / "page.md",
        """
        # Page

        See `src/pkg/missing.py::whatever` for details.
        """,
    )

    findings = lint_wiki(str(tmp_path))

    assert any(
        f.severity == "error" and "src/pkg/missing.py" in f.message for f in findings
    )


def test_lint_advisory_flags_header_attributed_symbol_not_in_file(tmp_path):
    _mod_py(tmp_path)
    _write(
        tmp_path / ".wiki" / "page.md",
        """
        ## Section — `src/pkg/mod.py`

        Discusses `_FAKE_SYMBOL` which doesn't exist.

        ## Sources

        - `src/pkg/mod.py`
        """,
    )

    findings = lint_wiki(str(tmp_path))

    assert any(
        f.severity == "advisory" and "_FAKE_SYMBOL" in f.message for f in findings
    )


def test_lint_does_not_flag_header_attributed_symbol_that_exists(tmp_path):
    _mod_py(tmp_path)
    _write(
        tmp_path / ".wiki" / "page.md",
        """
        ## Section — `src/pkg/mod.py`

        Discusses `_CONST`, which is real.

        ## Sources

        - `src/pkg/mod.py`
        """,
    )

    findings = lint_wiki(str(tmp_path))

    assert not any("_CONST" in f.message for f in findings)


def test_lint_header_without_file_clears_active_file_context(tmp_path):
    _mod_py(tmp_path)
    _write(
        tmp_path / ".wiki" / "page.md",
        """
        ## Section — `src/pkg/mod.py`

        `_CONST` is fine here.

        ## Where to make a change

        `_NOTHING_HERE` should not be checked since no file is attributed.

        ## Sources

        - `src/pkg/mod.py`
        """,
    )

    findings = lint_wiki(str(tmp_path))

    assert not any("_NOTHING_HERE" in f.message for f in findings)


def test_lint_ignores_common_keyword_tokens_in_header_attributed_symbols(tmp_path):
    _mod_py(tmp_path)
    _write(
        tmp_path / ".wiki" / "page.md",
        """
        ## Section — `src/pkg/mod.py`

        Accepts `haiku`, `sonnet`, or `opus`.

        ## Sources

        - `src/pkg/mod.py`
        """,
    )

    findings = lint_wiki(str(tmp_path))

    assert findings == []


def test_lint_wiki_returns_empty_list_for_clean_wiki(tmp_path):
    _mod_py(tmp_path)
    _write(
        tmp_path / ".wiki" / "page.md",
        """
        ## Section — `src/pkg/mod.py`

        `real_func` calls `_CONST`. See `src/pkg/mod.py::real_func`.

        ## Sources

        - `src/pkg/mod.py`
        """,
    )
    _write(
        tmp_path / ".wiki" / "index.md",
        """
        # Index
        """,
    )

    findings = lint_wiki(str(tmp_path))

    assert findings == []
