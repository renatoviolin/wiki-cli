_SHARED_PREAMBLE = """You are running headless, with full read/write access to this \
container's filesystem, network, and installed CLI tools (git, gh, aws). Do the \
following:

1. Check out pull request #{pr} of the repository "{repo}" using the instructions below.
2. Once checked out, run `/code-review` explicitly against the current diff, at \
effort level `medium`. Do not omit the target or the effort level — this is a fresh \
headless session with no prior invocation to inherit a default from.
3. Your final message must be the complete code review produced by that skill, and \
nothing else — it will be shown to a user verbatim.

{checkout_instructions}
"""

_GITHUB_CHECKOUT = """This PR is hosted on GitHub. To check it out:
1. Clone the repository: `gh repo clone {repo} ./workspace`
2. Enter the cloned directory: `cd ./workspace`
3. Check out the pull request: `gh pr checkout {pr}`
"""

_CODECOMMIT_CHECKOUT = """This PR is hosted on AWS CodeCommit. To check it out:
1. Resolve the pull request's refs: `aws codecommit get-pull-request \
--pull-request-id {pr}`
2. Clone the repository via the CodeCommit git remote: `git clone codecommit://{repo} \
./workspace`
3. Enter the cloned directory and check out the source commit id reported by step 1: \
`cd ./workspace && git checkout <source-commit-id>`

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
