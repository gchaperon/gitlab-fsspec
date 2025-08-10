"""Tests for private repository access and authentication.

Tests use the private test repository at:
https://gitlab.com/gitlab-filesystem-test-repos/private
"""

import os

import fsspec
import gitlab
import pytest

from gitlab_fsspec.gitlab import create_gitlab_client

HAS_GITLAB_TOKEN = bool(os.getenv("GITLAB_PRIVATE_TOKEN"))


def test_fsspec_open_private_repo_fails_without_auth(monkeypatch):
    """Test that fsspec.open fails when accessing private repo without auth."""
    # Clear all GitLab env vars to ensure no authentication
    monkeypatch.delenv("GITLAB_PRIVATE_TOKEN", raising=False)
    monkeypatch.delenv("GITLAB_OAUTH_TOKEN", raising=False) 
    monkeypatch.delenv("GITLAB_JOB_TOKEN", raising=False)
    monkeypatch.delenv("CI_JOB_TOKEN", raising=False)
    
    with (
        pytest.raises(gitlab.GitlabGetError),
        fsspec.open("gitlab://gitlab-filesystem-test-repos/private:README.md") as f,
    ):
        f.read()


@pytest.mark.skipif(not HAS_GITLAB_TOKEN, reason="GITLAB_PRIVATE_TOKEN environment variable not set")
def test_gitlab_client_authentication_from_env():
    """Test GitLab client can authenticate using token from environment."""
    # Create client without explicit auth - should load from environment
    client = create_gitlab_client("https://gitlab.com", None)
    
    # Test that authentication actually works
    client.auth()  # This makes API call to validate token
    assert client.user is not None
    assert hasattr(client.user, 'username')


@pytest.mark.skipif(not HAS_GITLAB_TOKEN, reason="GITLAB_PRIVATE_TOKEN environment variable not set") 
def test_fsspec_open_private_repo_with_env_token():
    """Test fsspec.open can access private repo when token is in environment."""
    # Test fsspec.open integration
    with fsspec.open("gitlab://gitlab-filesystem-test-repos/private:README.md") as f:
        content = f.read()
        assert len(content) > 0
        assert isinstance(content, bytes)
        # Verify it contains some reasonable content
        assert len(content) > 10
