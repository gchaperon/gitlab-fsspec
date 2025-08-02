"""Minimal GitLab filesystem implementation for fsspec."""

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

    def ls(self, path, detail=True, **kwargs):
        """List objects at path.

        Parameters
        ----------
        path : str
            Directory path to list
        detail : bool
            If True, returns list of dicts with file info; if False, returns list of names
        """
        path = self._strip_protocol(path)

        # Get repository tree and validate with Pydantic
        items = GitLabTree(self.project.repository_tree(path=path, ref=self.ref, get_all=True)).root

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
