"""Test configuration and fixtures."""

import pytest
from dotenv import find_dotenv, load_dotenv


def pytest_configure(config):
    """Load .env.test file before any tests run."""
    load_dotenv(find_dotenv(".env.test"))


@pytest.fixture
def clean_gitlab_env(monkeypatch):
    """Clear GitLab environment variables for isolated testing."""
    gitlab_env_vars = [
        "GITLAB_PRIVATE_TOKEN",
        "GITLAB_OAUTH_TOKEN",
        "GITLAB_JOB_TOKEN",
        "CI_JOB_TOKEN",
    ]
    for var in gitlab_env_vars:
        monkeypatch.delenv(var, raising=False)
