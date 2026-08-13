from code_review_cli.prompts import build_prompt


def test_build_prompt_includes_pr_and_repo():
    prompt = build_prompt("github", "renatoviolin/purabackend", 29)
    assert "renatoviolin/purabackend" in prompt
    assert "29" in prompt


def test_build_prompt_invokes_code_review_skill_explicitly():
    prompt = build_prompt("github", "renatoviolin/purabackend", 29)
    assert "/code-review" in prompt


def test_build_prompt_github_uses_gh_pr_checkout():
    prompt = build_prompt("github", "renatoviolin/purabackend", 29)
    assert "gh pr checkout 29" in prompt


def test_build_prompt_codecommit_uses_aws_codecommit():
    prompt = build_prompt("codecommit", "pura-backend", 7)
    assert "aws codecommit get-pull-request" in prompt
    assert "pull-request-id 7" in prompt


def test_build_prompt_states_final_message_is_the_deliverable():
    prompt = build_prompt("github", "renatoviolin/purabackend", 29)
    assert "reply with a json object" in prompt.lower()


def test_build_prompt_pins_an_explicit_effort_level():
    prompt = build_prompt("github", "renatoviolin/purabackend", 29)
    assert "effort level `medium`" in prompt


def test_build_prompt_forbids_substituting_a_different_repo_or_pr():
    prompt = build_prompt("github", "renatoviolin/purabackend", 29)
    assert "do not search for or substitute" in prompt.lower()
