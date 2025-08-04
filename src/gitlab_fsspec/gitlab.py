"""Minimal GitLab filesystem implementation for fsspec."""

import re
import typing as tp

import gitlab
import pydantic
from fsspec.spec import AbstractFileSystem


class GitLabTreeItem(pydantic.BaseModel):
    """Model for a GitLab repository tree item."""

    id: str
    name: str
    type: tp.Literal["blob", "tree"]
    path: str
    mode: str


class GitLabTree(pydantic.RootModel[list[GitLabTreeItem]]):
    """Model for validating a list of GitLab tree items."""

    pass


class GitLabFileSystem(AbstractFileSystem):
    """Minimal read-only interface to files in GitLab repositories.

    Parameters
    ----------
    project_path : str
        GitLab project path (e.g., 'group/project')
    sha : str, optional
        Branch, tag, or commit SHA (defaults to repository's default branch)
    url : str, optional
        GitLab instance URL (defaults to https://gitlab.com)
    private_token : str, optional
        GitLab private access token
    """

    protocol = "gitlab"

    # Regex pattern for gitlab://<repo/path>[@<ref>][:<path/to/file>]
    _gitlab_url_pattern = re.compile(
        r"""
        ^gitlab://                    # Match literal "gitlab://" at start
        (?P<project_path>[^@:]+)      # Named group: repo/path (any chars except @ and :)
        (?:@(?P<ref>[^:]+))?          # Named group: optional @ref (any chars except :)
        (?::(?P<file_path>.*))?       # Named group: optional :path/to/file (any remaining chars)
        $                            # End of string
    """,
        re.VERBOSE,
    )

    def __init__(
        self,
        project_path: str,
        sha: str | None = None,
        url: str = "https://gitlab.com",
        private_token: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.project_path = project_path
        self.url = url

        # Initialize GitLab client
        auth_kwargs = {}
        if private_token:
            auth_kwargs["private_token"] = private_token

        self.gl = gitlab.Gitlab(url, **auth_kwargs)

        # Get the project
        try:
            self.project = self.gl.projects.get(project_path)
        except gitlab.GitlabGetError as e:
            raise FileNotFoundError(f"Project {project_path} not found") from e

        # Determine the reference to use
        self.ref = sha if sha is not None else self.project.default_branch

    @property
    def fsid(self):
        """Unique filesystem identifier."""
        return f"gitlab://{self.project_path}@{self.ref}"

    @classmethod
    def _strip_protocol(cls, path):
        """Remove the gitlab:// protocol from path and extract file path."""
        match = cls._gitlab_url_pattern.match(path)
        if match:
            # Return the file_path part, or empty string if None
            return match.group("file_path") or ""

        # If it doesn't match our pattern, return as-is (let base class handle it)
        return path

    @staticmethod
    def _get_kwargs_from_urls(path):
        """Extract connection parameters from gitlab:// URL."""
        match = GitLabFileSystem._gitlab_url_pattern.match(path)
        if not match:
            # If it doesn't match our pattern, return empty dict
            return {}

        kwargs = {"project_path": match.group("project_path")}

        # Add ref if specified
        ref = match.group("ref")
        if ref:
            kwargs["sha"] = ref

        return kwargs

    def ls(self, path, detail=False, **kwargs):
        """List objects at path.

        Parameters
        ----------
        path : str
            Directory path to list
        detail : bool
            If True, returns list of dicts with file info; if False, returns list of names
        """
        path = self._strip_protocol(path)
        path = tp.cast(str, path)

        # Get repository tree and validate with Pydantic
        items = GitLabTree(
            self.project.repository_tree(path=path, ref=self.ref, get_all=True)
        ).root

        # Convert to fsspec format
        entries = [
            {
                "name": item.path,
                "size": None,  # GitLab tree API doesn't provide file sizes
                "type": "directory" if item.type == "tree" else "file",
                # FS-specific keys from GitLab
                "id": item.id,
                "mode": item.mode,
            }
            for item in items
        ]

        return entries if detail else [entry["name"] for entry in entries]

    def cat_file(self, path, start=None, end=None, **kwargs):
        """Get the content of a file.

        Parameters
        ----------
        path : str
            Path to the file
        start : int, optional
            Start byte position
        end : int, optional
            End byte position
        """
        path = self._strip_protocol(path)

        # Get file content from GitLab - let errors bubble up
        file_content = self.project.files.raw(file_path=path, ref=self.ref)

        # Handle byte range - note: end=0 edge case not handled
        return file_content[start or 0 : end or len(file_content)]

    def info(self, path, **kwargs):
        """Get file/directory info with actual size.

        Overrides the default implementation because GitLab's repository tree API
        (used by ls()) doesn't provide file sizes, but the files API does.
        This is necessary for fsspec.open() to work properly with buffered files.
        """
        path = self._strip_protocol(path)

        try:
            # Try to get file info first
            file_info = self.project.files.get(file_path=path, ref=self.ref)
            return {
                "name": path,
                "size": file_info.size,
                "type": "file",
                "id": file_info.blob_id,
            }
        except gitlab.GitlabGetError:
            # Fall back to ls() for directories or if file not found
            return super().info(path, **kwargs)
