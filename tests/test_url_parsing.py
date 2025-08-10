"""URL parsing tests for GitLab filesystem."""

import fsspec
import pytest

from gitlab_fsspec import GitLabFileSystem


@pytest.mark.parametrize(
    "url,expected",
    [
        ("gitlab://my/repo@master:file.txt", "file.txt"),
        ("gitlab://my/repo:file.txt", "file.txt"),
        ("gitlab://my/repo@master:docs/readme.md", "docs/readme.md"),
        ("gitlab://my/repo", ""),
        ("file.txt", "file.txt"),  # No protocol - returned as-is
    ],
)
def test_strip_protocol(url, expected):
    """Test _strip_protocol method."""
    result = GitLabFileSystem._strip_protocol(url)
    assert result == expected


@pytest.mark.parametrize(
    "url,expected",
    [
        ("gitlab://my/repo@master:file.txt", {"project_path": "my/repo", "sha": "master"}),
        ("gitlab://my/repo:file.txt", {"project_path": "my/repo"}),
        ("gitlab://group/subgroup/project@v1.0:src/main.py", {"project_path": "group/subgroup/project", "sha": "v1.0"}),
        ("file.txt", {}),  # No gitlab protocol
    ],
)
def test_get_kwargs_from_urls(url, expected):
    """Test _get_kwargs_from_urls method."""
    result = GitLabFileSystem._get_kwargs_from_urls(url)
    assert result == expected


@pytest.mark.parametrize(
    "url,expected_groups",
    [
        ("gitlab://my/repo", {"project_path": "my/repo", "ref": None, "file_path": None}),
        ("gitlab://my/repo@master", {"project_path": "my/repo", "ref": "master", "file_path": None}),
        ("gitlab://my/repo:file.txt", {"project_path": "my/repo", "ref": None, "file_path": "file.txt"}),
        ("gitlab://my/repo@master:file.txt", {"project_path": "my/repo", "ref": "master", "file_path": "file.txt"}),
        ("gitlab://group/subgroup/project@v1.0:src/main.py", {"project_path": "group/subgroup/project", "ref": "v1.0", "file_path": "src/main.py"}),
    ],
)
def test_regex_pattern_valid_urls(url, expected_groups):
    """Test the regex pattern with valid URLs."""
    pattern = GitLabFileSystem._gitlab_url_pattern
    match = pattern.match(url)
    assert match is not None
    assert match.group("project_path") == expected_groups["project_path"]
    assert match.group("ref") == expected_groups["ref"]
    assert match.group("file_path") == expected_groups["file_path"]


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "gitlab:/",
        "gitlab://",
        "not-a-url",
        "",
    ],
)
def test_regex_pattern_invalid_urls(url):
    """Test the regex pattern with invalid URLs."""
    pattern = GitLabFileSystem._gitlab_url_pattern
    match = pattern.match(url)
    assert match is None


def test_fsspec_open_integration():
    """Test fsspec.open integration with GitLab URLs."""
    with fsspec.open("gitlab://gitlab-filesystem-test-repos/public:README.md") as f:
        content = f.read()
        assert isinstance(content, bytes)
        assert len(content) > 0
        assert b"GitLab Filesystem Test Repository" in content


def test_fsspec_open_with_ref():
    """Test fsspec.open with specific reference."""
    with fsspec.open("gitlab://gitlab-filesystem-test-repos/public@main:README.md") as f:
        content = f.read()
        assert isinstance(content, bytes)
        assert len(content) > 0


def test_fsspec_open_nested_file():
    """Test opening nested file via fsspec.open."""
    with fsspec.open("gitlab://gitlab-filesystem-test-repos/public:nested/deep/very/far/deep_file.txt") as f:
        content = f.read()
        assert isinstance(content, bytes)
        assert len(content) > 0


def test_fsspec_open_text_mode():
    """Test fsspec.open in text mode with automatic decoding."""
    with fsspec.open("gitlab://gitlab-filesystem-test-repos/public:README.md", mode="r") as f:
        content = f.read()
        assert isinstance(content, str)
        assert len(content) > 0
        assert "GitLab Filesystem Test Repository" in content
