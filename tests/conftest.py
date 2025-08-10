"""Test configuration and fixtures."""

from dotenv import find_dotenv, load_dotenv


def pytest_configure(config):
    """Load .env.test file before any tests run."""
    load_dotenv(find_dotenv(".env.test"))