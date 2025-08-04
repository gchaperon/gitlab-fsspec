# GitLab fsspec

A read-only filesystem interface for GitLab repositories compatible with fsspec.

## Features

- **Read-Only GitLab Access**: Browse files and directories in GitLab repositories using standard filesystem operations
- **fsspec Integration**: Automatic registration with fsspec ecosystem - works with pandas, dask, and other fsspec-compatible libraries
- **Flexible URI Parsing**: Custom URL parsing with regex support for `gitlab://project/path@ref/file/path` format
- **Nested Project Support**: Handle deeply nested GitLab projects (e.g., `group/subgroup/project`)
- **Branch/Tag/Commit Support**: Access different branches, tags, or specific commit SHAs
- **Authentication**: Support for GitLab private tokens for accessing private repositories  
- **Self-hosted GitLab**: Configurable GitLab instance URL (defaults to gitlab.com)
- **Glob Pattern Support**: Built-in support for glob patterns to find multiple files
- **Pydantic Validation**: Uses Pydantic models for robust API response validation
- **Byte Range Reading**: Support for reading specific byte ranges from files
- **Proper File Sizes**: Custom `info()` implementation to get actual file sizes from GitLab's files API

## Installation

```bash
# Using uv (recommended)
uv add gitlab-fsspec

# Using pip
pip install gitlab-fsspec
```

The GitLab filesystem is automatically registered with fsspec upon installation via entry points, so no additional setup is required.

## Quick Start

```python
import fsspec

# Basic usage with public repository (new format)
with fsspec.open('gitlab://gitlab-org/gitlab@master/README.md', 'rb', 
                 project_path='gitlab-org/gitlab') as f:
    content = f.read().decode('utf-8')
    print(content[:100])

# Using the filesystem directly
from gitlab_fsspec import GitLabFileSystem

fs = GitLabFileSystem(project_path='gitlab-org/gitlab')
files = fs.ls('/')
print(f"Found {len(files)} files in repository")

# For user projects
fs_user = GitLabFileSystem(project_path='gitlab-filesystem-test-repos/public')
user_files = fs_user.ls('/')
print(f"Found {len(user_files)} files in user repository")

# Deeply nested projects are now supported
fs_nested = GitLabFileSystem(project_path='gitlab-org/monetization/monetization-platform')
nested_files = fs_nested.ls('/')
print(f"Found {len(nested_files)} files in nested project")
```

## Usage Examples

### URI Syntax

The GitLab filesystem supports URIs in the format:

```
gitlab://<repo/path>[@<ref>][:<path/to/file>]
```

Where:
- `<repo/path>`: GitLab project path (can be deeply nested, e.g., `group/subgroup/project`)
- `[@<ref>]`: Optional branch name, tag, or commit SHA (defaults to default branch)
- `[:<path/to/file>]`: Optional path to the file within the repository

Examples:
- `gitlab://gitlab-org/gitlab@master:README.md` (simple project with branch and file)
- `gitlab://gitlab-org/monetization/monetization-platform@main:README.md` (nested project)
- `gitlab://gitlab-org/gitlab:README.md` (uses default branch)
- `gitlab://gitlab-org/gitlab` (repository root)

### Authentication

For private repositories, provide authentication:

```python
from gitlab_fsspec import GitLabFileSystem

# Using private token (new format)
fs = GitLabFileSystem(
    project_path='your-group/subgroup/private-repo',
    private_token='your-private-token'
)

# Using OAuth token (new format)
fs = GitLabFileSystem(
    project_path='your-group/private-repo',
    oauth_token='your-oauth-token'
)

# Using job token (for CI/CD)
fs = GitLabFileSystem(
    project_path='your-group/private-repo',
    job_token='your-job-token'
)

# Backward compatibility still supported
fs = GitLabFileSystem(org='your-org', repo='private-repo', private_token='token')
```

### Self-hosted GitLab

```python
fs = GitLabFileSystem(
    project_path='your-group/your-repo',
    url='https://gitlab.example.com',
    private_token='your-token'
)
```

### Different Branches/Tags

```python
# Access specific branch (new format)
fs = GitLabFileSystem(project_path='group/repo', sha='develop')

# Access specific tag (new format)
fs = GitLabFileSystem(project_path='group/repo', sha='v1.0.0')

# Access specific commit (new format)
fs = GitLabFileSystem(project_path='group/repo', sha='abc123def456')
```

### File Operations

```python
from gitlab_fsspec import GitLabFileSystem

fs = GitLabFileSystem(project_path='group/repo')

# List files
files = fs.ls('/')
print(files)

# Check if file exists
if fs.exists('README.md'):
    print("README exists")

# Get file info
info = fs.info('README.md')
print(f"File size: {info['size']} bytes")

# Read file content
with fs.open('README.md', 'rb') as f:
    content = f.read()

# Use glob patterns to find files
txt_files = fs.glob('**/*.txt')
print(f"Found {len(txt_files)} .txt files")
```

## Development

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Install dependencies and set up development environment
uv sync

# Run the full test suite (parallel execution enabled by default)
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_basic.py
uv run pytest tests/test_url_parsing.py

# Code quality checks
uv run ruff check          # Linting
uv run ruff format         # Code formatting
uv run ruff check --fix    # Auto-fix linting issues
```

### Test Structure

- `tests/test_basic.py`: Core filesystem functionality, glob patterns, fsspec integration
- `tests/test_url_parsing.py`: URL parsing and regex pattern validation
- Tests use the public repository `gitlab-filesystem-test-repos/public` for validation
- Parallel test execution is enabled by default via pytest-xdist

## License

MIT License

## Implementation Details

This package uses the recommended fsspec entry point registration method. The GitLab filesystem is registered automatically when the package is installed via the entry point defined in `pyproject.toml`:

```toml
[project.entry-points."fsspec.specs"]
gitlab = "gitlab_fsspec:GitLabFileSystem"
```

This ensures the filesystem is available immediately after installation without requiring explicit imports.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.