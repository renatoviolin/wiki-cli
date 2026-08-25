from wiki_cli.prompts import _RESULT_SCHEMA, build_prompt


def test_build_prompt_create_mentions_wiki_folder():
    prompt = build_prompt("create")
    assert ".wiki" in prompt


def test_build_prompt_update_mentions_wiki_folder():
    prompt = build_prompt("update")
    assert ".wiki" in prompt


def test_build_prompt_create_and_update_differ():
    assert build_prompt("create") != build_prompt("update")


def test_build_prompt_create_writes_index_and_area_pages():
    prompt = build_prompt("create")
    assert "index.md" in prompt


def test_build_prompt_update_diffs_against_last_wiki_commit():
    prompt = build_prompt("update")
    assert "git log" in prompt
    assert "HEAD" in prompt


def test_build_prompt_resolves_repository_root():
    for mode in ("create", "update"):
        assert "git rev-parse --show-toplevel" in build_prompt(mode)


def test_build_prompt_requires_file_line_citations():
    for mode in ("create", "update"):
        assert "file:line" in build_prompt(mode)


def test_build_prompt_warns_against_inventing_identifiers():
    for mode in ("create", "update"):
        prompt = build_prompt(mode).lower()
        assert "do not invent" in prompt


def test_build_prompt_states_it_must_not_commit():
    for mode in ("create", "update"):
        assert "do not commit" in build_prompt(mode).lower()


def test_build_prompt_asks_for_json_reply():
    for mode in ("create", "update"):
        assert "reply with a json object" in build_prompt(mode).lower()


def test_result_schema_is_strict():
    assert _RESULT_SCHEMA["additionalProperties"] is False
    assert set(_RESULT_SCHEMA["required"]) == {
        "success",
        "summary",
        "pages_written",
        "failure_reason",
    }
