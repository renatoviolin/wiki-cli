from code_review_cli.prompts import build_prompt


def test_build_prompt_includes_pr_and_repo():
    prompt = build_prompt("github", "renatoviolin/purabackend", 29)
    assert "renatoviolin/purabackend" in prompt
    assert "29" in prompt


def test_build_prompt_dispatches_code_reviewer_subagent_explicitly():
    prompt = build_prompt("github", "renatoviolin/purabackend", 29)
    assert "voltagent-qa-sec:code-reviewer" in prompt


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


def test_build_prompt_forbids_substituting_a_different_repo_or_pr():
    prompt = build_prompt("github", "renatoviolin/purabackend", 29)
    assert "do not search for or substitute" in prompt.lower()


def test_build_prompt_standard_matches_default_output():
    default_prompt = build_prompt("github", "renatoviolin/purabackend", 29)
    explicit_prompt = build_prompt(
        "github", "renatoviolin/purabackend", 29, level="standard"
    )
    assert default_prompt == explicit_prompt


def test_build_prompt_light_narrows_scope_to_single_agent():
    prompt = build_prompt("github", "renatoviolin/purabackend", 29, level="light")
    assert "voltagent-qa-sec:code-reviewer" in prompt
    assert "high-confidence" in prompt.lower()
    assert "voltagent-qa-sec:security-auditor" not in prompt


def test_build_prompt_hard_dispatches_all_five_agents_and_a_judge():
    prompt = build_prompt("github", "renatoviolin/purabackend", 29, level="hard")
    assert "voltagent-qa-sec:code-reviewer" in prompt
    assert "voltagent-qa-sec:security-auditor" in prompt
    assert "voltagent-qa-sec:performance-engineer" in prompt
    assert "voltagent-qa-sec:architect-reviewer" in prompt
    assert "voltagent-qa-sec:qa-expert" in prompt
    assert "adversarially question" in prompt.lower()
    assert "judge" in prompt.lower()
