"""Tests for GitLabAuth settings class and authentication functionality."""

import pytest

from gitlab_fsspec.gitlab import GitLabAuth


def test_gitlab_auth_loads_from_env_private_token(clean_gitlab_env, monkeypatch):
    """Test loading GITLAB_PRIVATE_TOKEN from environment."""
    monkeypatch.setenv("GITLAB_PRIVATE_TOKEN", "test_private_token")
    auth = GitLabAuth()
    assert auth.private_token == "test_private_token"
    assert auth.oauth_token is None
    assert auth.job_token is None


def test_gitlab_auth_loads_from_env_oauth_token(clean_gitlab_env, monkeypatch):
    """Test loading GITLAB_OAUTH_TOKEN from environment."""
    monkeypatch.setenv("GITLAB_OAUTH_TOKEN", "test_oauth_token")
    auth = GitLabAuth()
    assert auth.oauth_token == "test_oauth_token"
    assert auth.private_token is None
    assert auth.job_token is None


def test_gitlab_auth_loads_ci_job_token_alias(clean_gitlab_env, monkeypatch):
    """Test that CI_JOB_TOKEN maps to job_token field."""
    monkeypatch.setenv("CI_JOB_TOKEN", "test_ci_token")
    auth = GitLabAuth()
    assert auth.job_token == "test_ci_token"
    assert auth.private_token is None
    assert auth.oauth_token is None


def test_gitlab_auth_loads_gitlab_job_token_alias(clean_gitlab_env, monkeypatch):
    """Test that GITLAB_JOB_TOKEN maps to job_token field."""
    monkeypatch.setenv("GITLAB_JOB_TOKEN", "test_gitlab_job_token")
    auth = GitLabAuth()
    assert auth.job_token == "test_gitlab_job_token"
    assert auth.private_token is None
    assert auth.oauth_token is None


def test_gitlab_auth_precedence_private_over_oauth(clean_gitlab_env, monkeypatch):
    """Test private_token takes precedence over oauth_token."""
    monkeypatch.setenv("GITLAB_PRIVATE_TOKEN", "private_token")
    monkeypatch.setenv("GITLAB_OAUTH_TOKEN", "oauth_token")
    auth = GitLabAuth()
    kwargs = auth.get_auth_kwargs()
    assert kwargs == {"private_token": "private_token"}


def test_gitlab_auth_precedence_oauth_over_job(clean_gitlab_env, monkeypatch):
    """Test oauth_token takes precedence over job_token."""
    monkeypatch.setenv("GITLAB_OAUTH_TOKEN", "oauth_token")
    monkeypatch.setenv("CI_JOB_TOKEN", "job_token")
    auth = GitLabAuth()
    kwargs = auth.get_auth_kwargs()
    assert kwargs == {"oauth_token": "oauth_token"}


def test_gitlab_auth_precedence_private_over_job(clean_gitlab_env, monkeypatch):
    """Test private_token takes precedence over job_token."""
    monkeypatch.setenv("GITLAB_PRIVATE_TOKEN", "private_token")
    monkeypatch.setenv("CI_JOB_TOKEN", "job_token")
    auth = GitLabAuth()
    kwargs = auth.get_auth_kwargs()
    assert kwargs == {"private_token": "private_token"}


def test_explicit_params_override_env(clean_gitlab_env, monkeypatch):
    """Test explicit parameters override environment variables."""
    monkeypatch.setenv("GITLAB_PRIVATE_TOKEN", "env_token")
    auth = GitLabAuth(private_token="explicit_token")
    kwargs = auth.get_auth_kwargs()
    assert kwargs == {"private_token": "explicit_token"}


def test_get_auth_kwargs_returns_correct_precedence(clean_gitlab_env):
    """Test get_auth_kwargs returns the highest precedence token."""
    auth = GitLabAuth(private_token="private", oauth_token="oauth", job_token="job")
    kwargs = auth.get_auth_kwargs()
    assert kwargs == {"private_token": "private"}


def test_get_auth_kwargs_oauth_when_no_private(clean_gitlab_env):
    """Test get_auth_kwargs returns oauth when no private token."""
    auth = GitLabAuth(oauth_token="oauth", job_token="job")
    kwargs = auth.get_auth_kwargs()
    assert kwargs == {"oauth_token": "oauth"}


def test_get_auth_kwargs_job_when_only_job(clean_gitlab_env):
    """Test get_auth_kwargs returns job token when only job token provided."""
    auth = GitLabAuth(ci_job_token="job")
    kwargs = auth.get_auth_kwargs()
    assert kwargs == {"job_token": "job"}


def test_get_auth_kwargs_empty_when_no_tokens(clean_gitlab_env):
    """Test get_auth_kwargs returns empty dict when no tokens provided."""
    auth = GitLabAuth()
    kwargs = auth.get_auth_kwargs()
    assert kwargs == {}


def test_gitlab_auth_loads_from_env_file(clean_gitlab_env, tmp_path, monkeypatch):
    """Test loading auth from .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text("GITLAB_PRIVATE_TOKEN=file_token")

    # Clear any existing environment variables
    monkeypatch.delenv("GITLAB_PRIVATE_TOKEN", raising=False)

    auth = GitLabAuth(_env_file=str(env_file))
    assert auth.private_token == "file_token"


def test_env_file_precedence_over_defaults(clean_gitlab_env, tmp_path):
    """Test .env file values take precedence over defaults."""
    env_file = tmp_path / ".env"
    env_file.write_text("GITLAB_OAUTH_TOKEN=file_oauth_token")

    auth = GitLabAuth(_env_file=str(env_file))
    kwargs = auth.get_auth_kwargs()
    assert kwargs == {"oauth_token": "file_oauth_token"}


def test_explicit_params_override_env_file(clean_gitlab_env, tmp_path):
    """Test explicit parameters override .env file values."""
    env_file = tmp_path / ".env"
    env_file.write_text("GITLAB_PRIVATE_TOKEN=file_token")

    auth = GitLabAuth(private_token="explicit_token", _env_file=str(env_file))
    kwargs = auth.get_auth_kwargs()
    assert kwargs == {"private_token": "explicit_token"}


def test_multiple_env_sources_precedence(clean_gitlab_env, tmp_path, monkeypatch):
    """Test precedence: explicit > env vars > .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text("GITLAB_PRIVATE_TOKEN=file_token")

    monkeypatch.setenv("GITLAB_PRIVATE_TOKEN", "env_var_token")

    # Explicit parameter should win
    auth = GitLabAuth(private_token="explicit_token", _env_file=str(env_file))
    kwargs = auth.get_auth_kwargs()
    assert kwargs == {"private_token": "explicit_token"}

    # Env var should win over file
    auth_no_explicit = GitLabAuth(_env_file=str(env_file))
    kwargs_no_explicit = auth_no_explicit.get_auth_kwargs()
    assert kwargs_no_explicit == {"private_token": "env_var_token"}


def test_ci_job_token_precedence_in_env(clean_gitlab_env, monkeypatch):
    """Test CI_JOB_TOKEN works in precedence hierarchy."""
    monkeypatch.setenv("GITLAB_OAUTH_TOKEN", "oauth_token")
    monkeypatch.setenv("CI_JOB_TOKEN", "ci_job_token")

    auth = GitLabAuth()
    kwargs = auth.get_auth_kwargs()
    # oauth_token should take precedence over job_token
    assert kwargs == {"oauth_token": "oauth_token"}

    # With only CI_JOB_TOKEN
    monkeypatch.delenv("GITLAB_OAUTH_TOKEN")
    auth_job_only = GitLabAuth()
    kwargs_job_only = auth_job_only.get_auth_kwargs()
    assert kwargs_job_only == {"job_token": "ci_job_token"}
