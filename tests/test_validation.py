import pytest

from code_review_cli.validation import (
    ValidationError,
    validate_model,
    validate_pr,
    validate_provider,
    validate_repo,
)


def test_validate_provider_accepts_github():
    assert validate_provider("github") == "github"


def test_validate_provider_accepts_codecommit():
    assert validate_provider("codecommit") == "codecommit"


def test_validate_provider_rejects_unknown_value():
    with pytest.raises(ValidationError):
        validate_provider("bitbucket")


def test_validate_pr_accepts_positive_integer_string():
    assert validate_pr("42") == 42


def test_validate_pr_rejects_non_numeric():
    with pytest.raises(ValidationError):
        validate_pr("abc")


def test_validate_pr_rejects_zero():
    with pytest.raises(ValidationError):
        validate_pr("0")


def test_validate_pr_rejects_negative():
    with pytest.raises(ValidationError):
        validate_pr("-5")


def test_validate_repo_accepts_github_owner_slash_repo():
    assert validate_repo("github", "renatoviolin/purabackend") == "renatoviolin/purabackend"


def test_validate_repo_accepts_github_full_url_form():
    repo = "github.com/renatoviolin/purabackend"
    assert validate_repo("github", repo) == repo


def test_validate_repo_rejects_malformed_github_repo():
    with pytest.raises(ValidationError):
        validate_repo("github", "not a repo; rm -rf /")


def test_validate_repo_accepts_codecommit_repo_name():
    assert validate_repo("codecommit", "pura-backend") == "pura-backend"


def test_validate_repo_rejects_codecommit_repo_with_slash():
    with pytest.raises(ValidationError):
        validate_repo("codecommit", "org/pura-backend")


def test_validate_repo_rejects_trailing_newline():
    with pytest.raises(ValidationError):
        validate_repo("github", "renatoviolin/purabackend\n")


def test_validate_repo_rejects_github_leading_dash_segment():
    with pytest.raises(ValidationError):
        validate_repo("github", "--foo/--bar")


def test_validate_repo_rejects_codecommit_leading_dash():
    with pytest.raises(ValidationError):
        validate_repo("codecommit", "--profile")


def test_validate_repo_rejects_unrecognized_provider():
    with pytest.raises(ValidationError):
        validate_repo("bitbucket", "org/repo")


def test_validate_model_accepts_haiku():
    assert validate_model("haiku") == "claude-haiku-4-5"


def test_validate_model_accepts_sonnet():
    assert validate_model("sonnet") == "claude-sonnet-5"


def test_validate_model_accepts_opus():
    assert validate_model("opus") == "claude-opus-5"


def test_validate_model_accepts_none():
    assert validate_model(None) is None


def test_validate_model_accepts_mixed_case():
    assert validate_model("Opus") == "claude-opus-5"


def test_validate_model_rejects_unknown_value():
    with pytest.raises(ValidationError):
        validate_model("gpt4")
