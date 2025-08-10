# GitLab fsspec

[![CI](https://github.com/gchaperon/gitlab-fsspec/workflows/CI/badge.svg)](https://github.com/gchaperon/gitlab-fsspec/actions)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A read-only filesystem interface for GitLab repositories compatible with fsspec.

## Features

- **Read-Only GitLab Access**: Browse files and directories in GitLab repositories using standard filesystem operations
- **fsspec Integration**: Automatic registration with fsspec ecosystem - works with pandas, dask, and other fsspec-compatible libraries
- **Flexible URI Parsing**: Custom URL parsing with regex support for `gitlab://project/path@ref:file/path` format
- **Authentication**: Support for GitLab private tokens for accessing private repositories

## Installation

```bash
pip install gitlab-fsspec
```

## Quick Start

```python
import fsspec

# Basic usage with public repository
with fsspec.open('gitlab://gitlab-filesystem-test-repos/public:README.md', 'rt') as f:
    lines = f.readlines()
    print(''.join(lines[:5]))

# Using the filesystem directly
from gitlab_fsspec import GitLabFileSystem

fs = GitLabFileSystem(project_path='gitlab-filesystem-test-repos/public')
files = fs.ls('/')
print(f"Found {len(files)} files in repository")
```

## Usage Guide

### Authentication

For private repositories, use a private token (other token types like OAuth and job tokens are also available). Authentication arguments are passed to the underlying python-gitlab object - see the [python-gitlab docs](https://python-gitlab.readthedocs.io/en/stable/api/gitlab.html#gitlab.Gitlab) for all options:

```python
import fsspec
from gitlab_fsspec import GitLabFileSystem

# Using private token with filesystem object
auth = {"private_token": "your-private-token"}
fs = GitLabFileSystem("gitlab-filesystem-test-repos/private", auth_kwargs=auth)

# Using environment variable (recommended)
# Set GITLAB_PRIVATE_TOKEN in your environment
fs = GitLabFileSystem("gitlab-filesystem-test-repos/private")

# Using fsspec.open with environment variable
with fsspec.open("gitlab://gitlab-filesystem-test-repos/private:data/sample.json") as f:
    content = f.read()
```

Authentication follows this precedence: `private_token` > `oauth_token` > `job_token`. The following environment variables are automatically loaded: `GITLAB_PRIVATE_TOKEN`, `GITLAB_OAUTH_TOKEN`, `GITLAB_JOB_TOKEN`, and `CI_JOB_TOKEN`.

### URI Format

GitLab URIs follow the format: `gitlab://project/path[@ref]:file/path`

Examples:
- `gitlab://gitlab-filesystem-test-repos/public:README.md`
- `gitlab://gitlab-filesystem-test-repos/public@main:data/data.csv`
- `gitlab://gitlab-filesystem-test-repos/public:scripts/example.py` (uses default branch)

### Basic Operations

```python
from gitlab_fsspec import GitLabFileSystem
import fsspec

fs = GitLabFileSystem(project_path='gitlab-filesystem-test-repos/public')

# Using filesystem object
with fs.open('README.md', 'rb') as f:
    content = f.read()

# Using fsspec.open
with fsspec.open('gitlab://gitlab-filesystem-test-repos/public:README.md') as f:
    content = f.read()

# Glob patterns with multiple files
files = fsspec.open_files('gitlab://gitlab-filesystem-test-repos/public:**/*.py')
for f in files:
    print(f.path)
```

### Working with Branches

```python
# Access specific branch
with fsspec.open('gitlab://gitlab-filesystem-test-repos/public@main:data/config.xml') as f:
    content = f.read()
```

### Pandas Integration

```python
import pandas as pd

# Read CSV from GitLab
df = pd.read_csv('gitlab://gitlab-filesystem-test-repos/public:data/data.csv')
```

## Development

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Install dependencies and set up development environment
uv sync

# Run the full test suite
uv run pytest

# Code quality checks
uv run ruff check          # Linting
uv run ruff format         # Code formatting
uv run ruff check --fix    # Auto-fix linting issues
```

### Private Repository Testing

To run tests against private repositories:

```bash
# Copy the template and add your GitLab private access token
cp .env.test.template .env.test
# Edit .env.test and add your GITLAB_PRIVATE_TOKEN

# Run all tests (including private repo tests if token is configured)
uv run pytest

# Run only private repository tests
uv run pytest tests/test_private_repo.py
```

**Note**: Private repository tests will be automatically skipped if no GitLab token is configured.