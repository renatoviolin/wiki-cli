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


def test_build_prompt_standard_matches_golden_output():
    expected = 'You are running headless, with full read/write access to this container\'s filesystem, network, and installed CLI tools (git, gh, aws). Do the following:\n\n1. Check out pull request #29 of the repository "renatoviolin/purabackend" using the instructions below.\n2. Once checked out, use the Agent tool to dispatch a subagent with `subagent_type` set to `voltagent-qa-sec:code-reviewer`. Give it a clear task description instructing it to review the code changes introduced by this pull request for code quality, security vulnerabilities, correctness bugs, and best practices, and to report back its complete findings. Wait for the subagent\'s full report before continuing.\n3. Reply with a JSON object matching this exact shape:\n   - On success: {"success": true, "review": "<the subagent\'s complete report, verbatim>", "failure_reason": ""}\n   - On failure: {"success": false, "review": "", "failure_reason": "<a short, specific explanation of what went wrong>"}\n\nBefore dispatching in step 2, check whether a `.wiki/` directory exists at the root of the checked-out repository. If it does, read `.wiki/index.md` and whichever pages it links to are relevant to the files this pull request changes, and include what you learn in the task description you give the subagent(s). That directory is the repository\'s own knowledge base: it describes architecture, conventions, and history that the diff alone does not show, and it is there to make the review better informed. If `.wiki/` does not exist, carry on without it.\n\nThe code is the source of truth, not the wiki. Where the wiki contradicts the code, trust the code, and note the discrepancy in the review so the wiki can be corrected.\n\nIf the named repository or pull request cannot be resolved exactly as given — it does not exist, the name is wrong, the PR number is wrong, or checkout fails for any reason — do not search for or substitute a different repository or pull request. Stop immediately and reply with the failure JSON shape above.\n\nThis PR is hosted on GitHub. To check it out:\n1. Clone the repository: `gh repo clone renatoviolin/purabackend ./workspace`\n2. Run all subsequent commands with the working directory set to `./workspace`.\n3. Check out the pull request: `gh pr checkout 29` (run inside `./workspace`)\n\n'
    assert build_prompt("github", "renatoviolin/purabackend", 29) == expected
    assert (
        build_prompt("github", "renatoviolin/purabackend", 29, level="standard")
        == expected
    )


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
    assert "the judge subagent's final merged and verified report" in prompt
def test_build_prompt_reads_wiki_for_every_level():
    for level in ("light", "standard", "hard"):
        prompt = build_prompt("github", "renatoviolin/purabackend", 29, level=level)
        assert ".wiki/index.md" in prompt


def test_build_prompt_tells_reviewer_code_outranks_wiki():
    for level in ("light", "standard", "hard"):
        prompt = build_prompt("github", "renatoviolin/purabackend", 29, level=level)
        assert "source of truth" in prompt
        assert "trust the code" in prompt


def test_build_prompt_tolerates_a_repository_without_a_wiki():
    prompt = build_prompt("github", "renatoviolin/purabackend", 29)
    assert "does not exist, carry on without it" in prompt
