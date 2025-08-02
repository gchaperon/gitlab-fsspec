# GitLab fsspec

A filesystem interface for GitLab repositories compatible with fsspec.

## Features

- **GitLab Repository Access**: Browse files and directories in GitLab repositories
- **fsspec Compatible**: Use with any fsspec-compatible library (pandas, dask, etc.)
- **URI Support**: Access files using `gitlab://project/path@ref/path/to/file` syntax with support for deeply nested projects
- **Authentication**: Support for private tokens, OAuth tokens, and job tokens
- **Branch/Tag Support**: Access different branches, tags, or specific commits
- **Self-hosted GitLab**: Works with self-hosted GitLab instances

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
gitlab://project/path@ref/path/to/file
```

Where:
- `project/path`: GitLab project path (can be deeply nested, e.g., `group/subgroup/project`)
- `ref`: Branch name, tag, or commit SHA (optional, defaults to default branch)
- `path/to/file`: Path to the file within the repository

Examples:
- `gitlab://gitlab-org/gitlab@master/README.md` (simple project)
- `gitlab://gitlab-org/monetization/monetization-platform@main/README.md` (nested project)
- `gitlab://gitlab-org/gitlab/README.md` (uses default branch)

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

### Integration with pandas

```python
import pandas as pd

# Read CSV from GitLab repository (new format)
df = pd.read_csv('gitlab://group/repo@main/data/file.csv',
                 storage_options={'project_path': 'group/repo'})

# Read with authentication (new format)
df = pd.read_csv(
    'gitlab://group/repo@main/data/file.csv',
    storage_options={
        'project_path': 'group/repo',
        'private_token': 'your-token',
        'url': 'https://gitlab.example.com'
    }
)
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

# Standard filesystem operations only
# Use python-gitlab directly for branches/tags if needed
```

## API Reference

### GitLabFileSystem

Main filesystem class for GitLab repositories.

#### Parameters

- `project_path` (str): GitLab project path (can be deeply nested, e.g., 'group/subgroup/project')
- `sha` (str, optional): SHA, branch, or tag to fetch from (defaults to default branch)
- `url` (str, optional): GitLab instance URL (default: https://gitlab.com)
- `private_token` (str, optional): GitLab private access token
- `oauth_token` (str, optional): GitLab OAuth token
- `job_token` (str, optional): GitLab CI job token
- `timeout` (float, optional): Request timeout in seconds
- `org` (str, optional): **Deprecated** - use `project_path` instead. For backward compatibility only.
- `repo` (str, optional): **Deprecated** - use `project_path` instead. For backward compatibility only.

#### Methods

- `ls(path, detail=False)`: List directory contents
- `info(path)`: Get file/directory information
- `exists(path)`: Check if path exists
- `isfile(path)`: Check if path is a file
- `isdir(path)`: Check if path is a directory  
- `open(path, mode='rb')`: Open file for reading


## Development

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Install dependencies
uv sync

# Run tests
uv run python test_gitlab_fs.py

# Run examples
uv run python example_usage.py
```

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