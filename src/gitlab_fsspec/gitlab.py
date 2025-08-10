"""Minimal GitLab filesystem implementation for fsspec."""

import re
import typing as tp

import gitlab
import pydantic
import pydantic_settings
from fsspec.spec import AbstractFileSystem


class GitLabAuthKwargs(tp.TypedDict, total=False):
    """Type definition for GitLab authentication kwargs."""

    private_token: str
    oauth_token: str
    job_token: str


class GitLabAuth(pydantic_settings.BaseSettings):
    """GitLab authentication configuration with environment variable support.

    Follows python-gitlab authentication precedence:
    1. private_token (recommended)
    2. oauth_token
    3. job_token (limited permissions)
    """

    private_token: str | None = None
    oauth_token: str | None = None
    job_token: tp.Annotated[
        str | None,
        pydantic.Field(
            validation_alias=pydantic.AliasChoices("gitlab_job_token", "ci_job_token")
        ),
    ] = None

    model_config = pydantic_settings.SettingsConfigDict(
        env_prefix="GITLAB_",
        extra="ignore",
    )

    def get_auth_kwargs(self) -> GitLabAuthKwargs:
        """Return auth kwargs dict for GitLab client with proper precedence.

        Returns
        -------
        GitLabAuthKwargs
            Authentication kwargs ready for gitlab.Gitlab constructor
        """
        if self.private_token:
            return {"private_token": self.private_token}
        elif self.oauth_token:
            return {"oauth_token": self.oauth_token}
        elif self.job_token:
            return {"job_token": self.job_token}
        else:
            return {}


def create_gitlab_client(
    url: str,
    auth_kwargs: GitLabAuthKwargs | None = None,
) -> gitlab.Gitlab:
    """Create and return a GitLab client instance with authentication.

    Parameters
    ----------
    url : str
        GitLab instance URL
    auth_kwargs : GitLabAuthKwargs, optional
        Authentication kwargs dict

    Returns
    -------
    gitlab.Gitlab
        Configured GitLab client instance
    """
    # Create GitLabAuth object using the provided auth_kwargs
    # This allows environment variables to be used as fallback
    auth = GitLabAuth(**(auth_kwargs or {}))
    
    return gitlab.Gitlab(url, **auth.get_auth_kwargs())


class GitLabTreeItem(pydantic.BaseModel):
    """Model for a GitLab repository tree item."""

    id: str
    name: str
    type: tp.Literal["blob", "tree"]
    path: str
    mode: str


class GitLabFileSystem(AbstractFileSystem):
    """Minimal read-only interface to files in GitLab repositories.

    Parameters
    ----------
    project_path : str
        GitLab project path (e.g., 'group/project')
    ref : str, optional
        Branch, tag, or commit SHA (defaults to repository's default branch)
    url : str, optional
        GitLab instance URL (defaults to https://gitlab.com)
    auth_kwargs : GitLabAuthKwargs, optional
        Authentication kwargs dict with one of the keys: private_token, oauth_token, job_token

    Notes
    -----
    Authentication precedence: private_token > oauth_token > job_token
    If auth_kwargs is None, will attempt to load credentials from environment variables:
    GITLAB_PRIVATE_TOKEN, GITLAB_OAUTH_TOKEN, GITLAB_JOB_TOKEN, or CI_JOB_TOKEN.
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
        ref: str | None = None,
        url: str = "https://gitlab.com",
        auth_kwargs: GitLabAuthKwargs | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.project_path = project_path
        self.url = url

        # Initialize GitLab client
        self.gl = create_gitlab_client(url, auth_kwargs)

        # Get the project
        self.project = self.gl.projects.get(project_path)

        # Determine the reference to use
        self.ref = ref or self.project.default_branch

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

        # Extract only the constructor parameters we need
        return {
            k: v for k, v in match.groupdict().items() if k in ["project_path", "ref"]
        }

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

        # Get repository tree and validate each item with Pydantic
        items = [
            GitLabTreeItem(**item)
            for item in self.project.repository_tree(
                path=path, ref=self.ref, get_all=True
            )
        ]

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
