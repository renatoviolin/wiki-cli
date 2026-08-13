_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "review": {"type": "string"},
        "failure_reason": {"type": "string"},
    },
    "required": ["success", "review", "failure_reason"],
}

_SHARED_PREAMBLE = """You are running headless, with full read/write access to this \
container's filesystem, network, and installed CLI tools (git, gh, aws). Do the \
following:

1. Check out pull request #{pr} of the repository "{repo}" using the instructions below.
2. Once checked out, run `/code-review` explicitly against the current diff, at \
effort level `medium`. Do not omit the target or the effort level — this is a fresh \
headless session with no prior invocation to inherit a default from.
3. Reply with a JSON object matching this exact shape:
   - On success: {{"success": true, "review": "<the complete code review produced by \
that skill, verbatim>", "failure_reason": ""}}
   - On failure: {{"success": false, "review": "", "failure_reason": "<a short, \
specific explanation of what went wrong>"}}

If the named repository or pull request cannot be resolved exactly as given — it \
does not exist, the name is wrong, the PR number is wrong, or checkout fails for any \
reason — do not search for or substitute a different repository or pull request. Stop \
immediately and reply with the failure JSON shape above.

{checkout_instructions}
"""

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


def build_prompt(provider: str, repo: str, pr: int) -> str:
    checkout_instructions = _CHECKOUT_TEMPLATES[provider].format(repo=repo, pr=pr)
    return _SHARED_PREAMBLE.format(
        pr=pr, repo=repo, checkout_instructions=checkout_instructions
    )
