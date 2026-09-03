import wiki_cli.cli as cli_module


def test_cli_generate_skills_writes_both_files(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code = cli_module.main(["generate-skills"])
    assert code == 0

    create_path = tmp_path / ".claude" / "skills" / "wiki-create" / "SKILL.md"
    update_path = tmp_path / ".claude" / "skills" / "wiki-update" / "SKILL.md"
    assert create_path.exists()
    assert update_path.exists()

    out = capsys.readouterr().out
    assert "wiki-create/SKILL.md" in out
    assert "wiki-update/SKILL.md" in out
