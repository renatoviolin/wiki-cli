_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "review": {"type": "string"},
        "failure_reason": {"type": "string"},
    },
    "required": ["success", "review", "failure_reason"],
    "additionalProperties": False,
}

_SHARED_PREAMBLE = """You are running headless, with full read/write access to this \
container's filesystem, network, and installed CLI tools (git, gh, aws). Do the \
following:

1. Check out pull request #{pr} of the repository "{repo}" using the instructions below.
{dispatch_instructions}
3. Reply with a JSON object matching this exact shape:
   - On success: {{"success": true, "review": "<{review_source}>", "failure_reason": ""}}
   - On failure: {{"success": false, "review": "", "failure_reason": "<a short, \
specific explanation of what went wrong>"}}

If the named repository or pull request cannot be resolved exactly as given — it \
does not exist, the name is wrong, the PR number is wrong, or checkout fails for any \
reason — do not search for or substitute a different repository or pull request. Stop \
immediately and reply with the failure JSON shape above.

{checkout_instructions}
"""

_STANDARD_DISPATCH = """2. Once checked out, use the Agent tool to dispatch a subagent with `subagent_type` \
set to `voltagent-qa-sec:code-reviewer`. Give it a clear task description instructing \
it to review the code changes introduced by this pull request for code quality, \
security vulnerabilities, correctness bugs, and best practices, and to report back its \
complete findings. Wait for the subagent's full report before continuing."""

_LIGHT_DISPATCH = """2. Once checked out, use the Agent tool to dispatch a subagent with `subagent_type` \
set to `voltagent-qa-sec:code-reviewer`. Give it a clear task description instructing \
it to review the code changes introduced by this pull request, but to report ONLY \
high-confidence correctness bugs and security vulnerabilities — explicitly instruct it \
to skip style issues, best-practice suggestions, and any low-confidence or nit-level \
findings. Wait for the subagent's full report before continuing."""

_HARD_DISPATCH = """2. Once checked out, use the Agent tool to dispatch each of the following five \
subagents in turn, each with a clear task description instructing it to review the \
code changes introduced by this pull request from its own area of focus, and to \
report back its complete findings. Wait for each subagent's full report before \
dispatching the next:
   - `voltagent-qa-sec:code-reviewer` — code quality, security vulnerabilities, \
correctness bugs, and best practices.
   - `voltagent-qa-sec:security-auditor` — security vulnerabilities and compliance gaps.
   - `voltagent-qa-sec:performance-engineer` — performance bottlenecks in the changed code.
   - `voltagent-qa-sec:architect-reviewer` — design and architectural fit of the change.
   - `voltagent-qa-sec:qa-expert` — test coverage and quality-assurance gaps.
   Once all five reports are in hand, use the Agent tool once more to dispatch a \
final subagent (no specific `subagent_type`) as judge. Give the judge all five \
reports verbatim and instruct it to: merge overlapping or duplicate findings into \
one coherent list; for each remaining finding, adversarially question whether it is \
a genuine issue or a false positive, and drop it if it does not survive that check; \
and produce a final merged, verified report. Wait for the judge's full report before \
continuing."""

_LEVEL_INSTRUCTIONS = {
    "light": _LIGHT_DISPATCH,
    "standard": _STANDARD_DISPATCH,
    "hard": _HARD_DISPATCH,
}

_REVIEW_SOURCE = {
    "light": "the subagent's complete report, verbatim",
    "standard": "the subagent's complete report, verbatim",
    "hard": "the judge subagent's final merged and verified report, verbatim",
}

_GITHUB_CHECKOUT = """This PR is hosted on GitHub. To check it out:
1. Clone the repository: `gh repo clone {repo} ./workspace`
2. Run all subsequent commands with the working directory set to `./workspace`.
3. Check out the pull request: `gh pr checkout {pr}` (run inside `./workspace`)
"""

_CODECOMMIT_CHECKOUT = """This PR is hosted on AWS CodeCommit. To check it out:
1. Resolve the pull request's refs: `aws codecommit get-pull-request \
--pull-request-id {pr}`
2. Clone the repository via the CodeCommit git remote: `git clone codecommit://{repo} \
./workspace`
3. Run all subsequent commands with the working directory set to `./workspace`, and \
check out the source commit id reported by step 1: `git checkout <source-commit-id>` \
(run inside `./workspace`)

AWS region and credentials are already configured in this environment.
"""

_CHECKOUT_TEMPLATES = {
    "github": _GITHUB_CHECKOUT,
    "codecommit": _CODECOMMIT_CHECKOUT,
}


def build_prompt(provider: str, repo: str, pr: int, level: str = "standard") -> str:
    checkout_instructions = _CHECKOUT_TEMPLATES[provider].format(repo=repo, pr=pr)
    return _SHARED_PREAMBLE.format(
        pr=pr,
        repo=repo,
        dispatch_instructions=_LEVEL_INSTRUCTIONS[level],
        review_source=_REVIEW_SOURCE[level],
        checkout_instructions=checkout_instructions,
    )
