from pathlib import Path

import pytest

from wiki_cli.prompts import build_prompt
from wiki_cli.skill_gen import render_skill_md, write_skill_files

MODES = ("create", "update")


@pytest.mark.parametrize("mode", MODES)
def test_render_skill_md_has_matching_frontmatter_name(mode):
    rendered = render_skill_md(mode)
    assert rendered.startswith("---\n")
    assert f"name: wiki-{mode}\n" in rendered
    assert "description:" in rendered


@pytest.mark.parametrize("mode", MODES)
def test_render_skill_md_body_is_build_prompt_verbatim(mode):
    assert build_prompt(mode) in render_skill_md(mode)


def test_render_skill_md_create_and_update_differ():
    assert render_skill_md("create") != render_skill_md("update")


def test_write_skill_files_writes_both_modes(tmp_path):
    written = write_skill_files(str(tmp_path))

    create_path = tmp_path / "wiki-create" / "SKILL.md"
    update_path = tmp_path / "wiki-update" / "SKILL.md"
    assert set(written) == {create_path, update_path}
    assert create_path.read_text() == render_skill_md("create")
    assert update_path.read_text() == render_skill_md("update")


def test_write_skill_files_defaults_to_claude_skills_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_skill_files()

    assert (tmp_path / ".claude" / "skills" / "wiki-create" / "SKILL.md").exists()
    assert (tmp_path / ".claude" / "skills" / "wiki-update" / "SKILL.md").exists()
