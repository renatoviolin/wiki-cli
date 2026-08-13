import re

VALID_PROVIDERS = {"github", "codecommit"}

_SEGMENT = r"[A-Za-z0-9_][\w.-]*"
_GITHUB_REPO_RE = re.compile(rf"^(github\.com/)?{_SEGMENT}/{_SEGMENT}$")
_CODECOMMIT_REPO_RE = re.compile(rf"^{_SEGMENT}$")

_REPO_PATTERNS = {
    "github": _GITHUB_REPO_RE,
    "codecommit": _CODECOMMIT_REPO_RE,
}


class ValidationError(ValueError):
    """Raised when a CLI input fails validation before Claude Code is invoked."""


def validate_provider(provider: str) -> str:
    if provider not in VALID_PROVIDERS:
        raise ValidationError(
            f"--provider must be one of {sorted(VALID_PROVIDERS)}, got {provider!r}"
        )
    return provider


def validate_pr(pr: str) -> int:
    try:
        value = int(pr)
    except ValueError as exc:
        raise ValidationError(f"--pr must be an integer, got {pr!r}") from exc
    if value <= 0:
        raise ValidationError(f"--pr must be a positive integer, got {value}")
    return value


def validate_repo(provider: str, repo: str) -> str:
    pattern = _REPO_PATTERNS.get(provider)
    if pattern is None:
        raise ValidationError(
            f"--repo cannot be validated: unrecognized provider {provider!r}"
        )
    if not pattern.fullmatch(repo):
        raise ValidationError(
            f"--repo {repo!r} is not a valid {provider} repository identifier"
        )
    return repo
