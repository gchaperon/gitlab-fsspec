"""Basic functionality tests for GitLab filesystem."""

import pytest

from gitlab_fsspec import GitLabFileSystem


@pytest.fixture
def test_fs():
    """Create a GitLab filesystem instance for testing."""
    return GitLabFileSystem(project_path="gitlab-filesystem-test-repos/public")


def test_filesystem_creation(test_fs):
    """Test that GitLab filesystem can be created."""
    assert test_fs.project_path == "gitlab-filesystem-test-repos/public"
    assert test_fs.ref == "main"  # This repo uses 'main' as default branch
    assert test_fs.fsid == "gitlab://gitlab-filesystem-test-repos/public@main"


def test_ls_root_directory(test_fs):
    """Test listing root directory."""
    files = test_fs.ls("", detail=False)
    assert isinstance(files, list)

    # Check expected files/directories from your repo structure
    assert "README.md" in files
    assert "data" in files
    assert "docs" in files
    assert "empty" in files
    assert "media" in files
    assert "nested" in files
    assert "scripts" in files


def test_ls_with_detail(test_fs):
    """Test listing with detailed information."""
    detailed = test_fs.ls("", detail=True)
    assert isinstance(detailed, list)
    assert len(detailed) > 0

    # Check first item has expected structure
    first_item = detailed[0]
    assert "name" in first_item
    assert "size" in first_item
    assert "type" in first_item
    assert "id" in first_item
    assert "mode" in first_item
    assert first_item["type"] in ["file", "directory"]


def test_ls_subdirectory(test_fs):
    """Test listing a subdirectory."""
    data_files = test_fs.ls("data", detail=False)
    assert isinstance(data_files, list)
    assert "data/config.xml" in data_files
    assert "data/data.csv" in data_files
    assert "data/sample.json" in data_files


def test_ls_nested_directory(test_fs):
    """Test listing nested directory."""
    nested_files = test_fs.ls("nested/deep/very", detail=False)
    assert isinstance(nested_files, list)
    assert "nested/deep/very/far" in nested_files


def test_cat_file(test_fs):
    """Test reading file content."""
    content = test_fs.cat_file("README.md")
    assert isinstance(content, bytes)
    assert len(content) > 0
    assert b"GitLab Filesystem Test Repository" in content


def test_cat_file_in_subdirectory(test_fs):
    """Test reading file from subdirectory."""
    content = test_fs.cat_file("docs/sample.txt")
    assert isinstance(content, bytes)
    assert len(content) > 0


def test_cat_file_with_range(test_fs):
    """Test reading file with byte range."""
    # Read first 10 bytes
    content = test_fs.cat_file("README.md", start=0, end=10)
    assert isinstance(content, bytes)
    assert len(content) == 10

    # Read from middle
    content = test_fs.cat_file("README.md", start=10, end=20)
    assert isinstance(content, bytes)
    assert len(content) == 10


def test_info(test_fs):
    """Test getting file info."""
    info = test_fs.info("README.md")
    assert info["name"] == "README.md"
    assert info["type"] == "file"
    assert isinstance(info["size"], int)
    assert info["size"] > 0


def test_info_directory_fallback(test_fs):
    """Test getting directory info (should fallback to ls)."""
    info = test_fs.info("data")
    assert info["name"] == "data"
    assert info["type"] == "directory"


@pytest.mark.parametrize(
    "pattern,expected_files",
    [
        (
            "**/*.txt",
            {
                "docs/sample.txt",
                "nested/deep/very/far/deep_file.txt",
                "media/image_info.txt",
            },
        ),
        ("data/*", {"data/config.xml", "data/data.csv", "data/sample.json"}),
        ("scripts/*.py", {"scripts/example.py"}),
        ("*.md", {"README.md"}),  # Root level markdown files
        ("docs/*", {"docs/README_internal.md", "docs/sample.txt"}),
    ],
)
def test_glob_patterns(test_fs, pattern, expected_files):
    """Test various glob patterns."""
    found_files = test_fs.glob(pattern)
    assert isinstance(found_files, list)

    # Convert to set for easier comparison
    found_set = set(found_files)
    assert expected_files.issubset(found_set), (
        f"Pattern '{pattern}': Missing files: {expected_files - found_set}"
    )


@pytest.mark.parametrize(
    "pattern,detail",
    [
        ("scripts/*.py", True),
        ("data/*.csv", True),
        ("**/*.txt", False),
    ],
)
def test_glob_with_detail_option(test_fs, pattern, detail):
    """Test glob with detail parameter."""
    result = test_fs.glob(pattern, detail=detail)

    if detail:
        assert isinstance(result, dict)
        if result:  # If files found
            first_key = next(iter(result))
            file_info = result[first_key]
            assert "type" in file_info
            assert "size" in file_info
    else:
        assert isinstance(result, list)
        if result:  # If files found
            assert isinstance(result[0], str)


@pytest.mark.parametrize(
    "pattern",
    [
        "*/nonexistent.file",  # Pattern that should match nothing
        "**/*.missing",  # Non-existent extension (corrected ** usage)
        "data/*.exe",  # Wrong extension in existing directory
    ],
)
def test_glob_no_matches(test_fs, pattern):
    """Test glob patterns that should return no matches."""
    result = test_fs.glob(pattern)
    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.parametrize(
    "pattern,expected_files",
    [
        ("gitlab://gitlab-filesystem-test-repos/public:**/*.txt", {"docs/sample.txt", "nested/deep/very/far/deep_file.txt", "media/image_info.txt"}),
        ("gitlab://gitlab-filesystem-test-repos/public:data/*", {"data/config.xml", "data/data.csv", "data/sample.json"}),
        ("gitlab://gitlab-filesystem-test-repos/public:*.md", {"README.md"}),
    ],
)
def test_fsspec_open_files_glob(pattern, expected_files):
    """Test fsspec.open_files with glob patterns."""
    import fsspec

    files = fsspec.open_files(pattern)
    assert isinstance(files, list)
    assert len(files) > 0

    # Extract paths from OpenFile objects
    found_paths = {f.path for f in files}
    assert expected_files.issubset(found_paths), f"Pattern '{pattern}': Missing files: {expected_files - found_paths}"


def test_fsspec_expand_path_glob():
    """Test expanding glob patterns via fsspec filesystem creation."""
    import fsspec

    # Create filesystem and test expand_path with glob patterns
    fs = fsspec.filesystem("gitlab", project_path="gitlab-filesystem-test-repos/public")

    # Test expand_path with glob pattern
    result = fs.expand_path("**/*.txt")
    assert isinstance(result, list)
    assert len(result) >= 3

    expected_files = {"docs/sample.txt", "nested/deep/very/far/deep_file.txt", "media/image_info.txt"}
    found_set = set(result)
    assert expected_files.issubset(found_set)


def test_fsspec_open_files_context_manager():
    """Test using fsspec.open_files with context manager."""
    import fsspec

    pattern = "gitlab://gitlab-filesystem-test-repos/public:**/*.txt"
    files = fsspec.open_files(pattern)

    # Test context manager usage
    with files as opened_files:
        assert len(opened_files) > 0

        # Read content from first file
        first_file = opened_files[0]
        content = first_file.read()
        assert isinstance(content, bytes)
        assert len(content) > 0
