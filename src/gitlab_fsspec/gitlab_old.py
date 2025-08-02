"""GitLab filesystem implementation for fsspec."""

import base64
import io
from typing import Any

import gitlab
from fsspec.spec import AbstractFileSystem


class GitLabFileSystem(AbstractFileSystem):
    """Interface to files in GitLab repositories

    An instance of this class provides access to files residing within a remote GitLab
    repository. You may specify a point in the repo's history by SHA, branch, or tag
    (default is the default branch of the repository).

    When using fsspec.open, allows URIs of the form:

    - "gitlab://project/path@ref/path/to/file.txt", where project/path can be deeply nested
      (e.g., gitlab://gitlab-org/monetization/monetization-platform@main/README.md)
    - "gitlab://project/path@/path/to/file.txt", uses default branch when ref is empty
    - "gitlab://project/path/file.txt", uses default branch when @ is omitted

    For authentication, you can provide:
    - private_token: GitLab private access token
    - oauth_token: GitLab OAuth token
    - job_token: GitLab CI job token
    - Or configure via environment variables or GitLab configuration files

    Parameters
    ----------
    project_path : str
        GitLab project path (can be deeply nested, e.g., 'group/subgroup/project')
    sha : str, optional
        SHA, branch, or tag to fetch from (defaults to repository's default branch)
    url : str, optional
        GitLab instance URL (defaults to https://gitlab.com)
    private_token : str, optional
        GitLab private access token
    oauth_token : str, optional
        GitLab OAuth token
    job_token : str, optional
        GitLab CI job token
    timeout : float, optional
        Request timeout in seconds
    org : str, optional
        Deprecated: use project_path instead. For backward compatibility only.
    repo : str, optional
        Deprecated: use project_path instead. For backward compatibility only.
    **kwargs
        Additional arguments passed to AbstractFileSystem
    """

    protocol = "gitlab"

    def __init__(
        self,
        project_path: str | None = None,
        sha: str | None = None,
        url: str = "https://gitlab.com",
        private_token: str | None = None,
        oauth_token: str | None = None,
        job_token: str | None = None,
        timeout: float | None = None,
        # Backward compatibility parameters
        org: str | None = None,
        repo: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)

        # Handle backward compatibility and parameter validation
        if project_path is None:
            if org is not None and repo is not None:
                project_path = f"{org}/{repo}"
            else:
                raise ValueError(
                    "Either 'project_path' or both 'org' and 'repo' must be provided"
                )

        self.project_path = project_path
        self.url = url
        self.timeout = timeout or 60.0

        # Initialize GitLab client
        auth_kwargs = {}
        if private_token:
            auth_kwargs["private_token"] = private_token
        elif oauth_token:
            auth_kwargs["oauth_token"] = oauth_token
        elif job_token:
            auth_kwargs["job_token"] = job_token

        self.gl = gitlab.Gitlab(url, **auth_kwargs)

        # Get the project
        try:
            self.project = self.gl.projects.get(project_path)
        except gitlab.GitlabGetError as e:
            raise FileNotFoundError(f"Project {project_path} not found") from e

        # Determine the reference to use
        if sha is None:
            # Use the default branch
            self.ref = self.project.default_branch
        else:
            self.ref = sha

    def _get_directory_contents(self, path: str = "") -> list[dict[str, Any]]:
        """Get directory contents for a given path."""
        try:
            # Get repository tree at the specified path and ref
            tree_kwargs = {"ref": self.ref, "all": True}
            if path:
                tree_kwargs["path"] = path
            items = self.project.repository_tree(**tree_kwargs)

            entries = []
            for item in items:
                item_path = item["path"]
                if path and not item_path.startswith(path + "/"):
                    continue

                entry = {
                    "name": item_path,
                    "type": "directory" if item["type"] == "tree" else "file",
                    "size": 0,  # GitLab API doesn't provide size in tree listing
                    "mode": item.get("mode", "100644"),
                    "id": item["id"],
                }
                entries.append(entry)

            return entries

        except gitlab.GitlabGetError as e:
            if e.response_code == 404:
                raise FileNotFoundError(f"Path {path} not found") from e
            raise

    def ls(
        self, path: str, detail: bool = False, **kwargs
    ) -> list[str] | list[dict[str, Any]]:
        """List files at given path

        Parameters
        ----------
        path : str
            Location to list, relative to repo root
        detail : bool
            If True, returns list of dicts with file info; if False, returns list of names
        """
        path = self._strip_protocol(path).rstrip("/")

        # Check if this is a file
        try:
            file_info = self.info(path)
            if file_info["type"] == "file":
                if detail:
                    return [file_info]
                else:
                    return [path]
        except FileNotFoundError:
            pass

        # Get directory contents
        entries = self._get_directory_contents(path)

        # Filter entries that are direct children of the path
        if path:
            prefix = path + "/"
            direct_children = []
            for entry in entries:
                rel_path = entry["name"]
                if rel_path.startswith(prefix):
                    child_path = rel_path[len(prefix) :]
                    if "/" not in child_path:  # Direct child, not nested
                        direct_children.append(entry)
                elif rel_path == path:
                    continue  # Skip the directory itself
            entries = direct_children
        else:
            # Root directory - only include top-level items
            entries = [e for e in entries if "/" not in e["name"]]

        if detail:
            return entries
        else:
            return sorted([entry["name"] for entry in entries])

    def info(self, path: str, **kwargs) -> dict[str, Any]:
        """Get file/directory information

        Parameters
        ----------
        path : str
            Path to get info for

        Returns
        -------
        dict
            File/directory information
        """
        path = self._strip_protocol(path).rstrip("/")

        try:
            # Try to get file content to determine if it's a file
            file_info = self.project.files.get(file_path=path, ref=self.ref)

            return {
                "name": path,
                "type": "file",
                "size": file_info.size,
                "encoding": file_info.encoding,
                "content_sha256": file_info.content_sha256,
                "ref": self.ref,
                "last_commit_id": file_info.last_commit_id,
            }

        except gitlab.GitlabGetError as e:
            if e.response_code == 404:
                # Not a file, check if it's a directory
                try:
                    self._get_directory_contents(path)
                    return {
                        "name": path,
                        "type": "directory",
                        "size": 0,
                    }
                except gitlab.GitlabGetError:
                    pass
                raise FileNotFoundError(f"Path {path} not found") from e
            raise

    def _open(
        self,
        path: str,
        mode: str = "rb",
        block_size: int | None = None,
        autocommit: bool = True,
        cache_options: dict | None = None,
        **kwargs,
    ) -> io.IOBase:
        """Open a file for reading

        Parameters
        ----------
        path : str
            Path to the file
        mode : str
            File open mode (only 'rb' supported)
        block_size : int, optional
            Block size for reading (unused)
        autocommit : bool, optional
            Auto-commit mode (unused)
        cache_options : dict, optional
            Cache options (unused)
        **kwargs
            Additional arguments

        Returns
        -------
        io.IOBase
            File-like object
        """
        if mode != "rb":
            raise NotImplementedError("Only binary read mode 'rb' is supported")

        path = self._strip_protocol(path)

        try:
            # Get file content from GitLab
            file_info = self.project.files.get(file_path=path, ref=self.ref)

            # Decode content based on encoding
            if file_info.encoding == "base64":
                content = base64.b64decode(file_info.content)
            else:
                # Assume text content
                content = file_info.content.encode("utf-8")

            return io.BytesIO(content)

        except gitlab.GitlabGetError as e:
            if e.response_code == 404:
                raise FileNotFoundError(f"File {path} not found") from e
            raise

    def exists(self, path: str, **kwargs) -> bool:
        """Check if path exists

        Parameters
        ----------
        path : str
            Path to check

        Returns
        -------
        bool
            True if path exists, False otherwise
        """
        try:
            self.info(path)
            return True
        except FileNotFoundError:
            return False

    def isfile(self, path: str) -> bool:
        """Check if path is a file

        Parameters
        ----------
        path : str
            Path to check

        Returns
        -------
        bool
            True if path is a file, False otherwise
        """
        try:
            info = self.info(path)
            return info["type"] == "file"
        except FileNotFoundError:
            return False

    def isdir(self, path: str) -> bool:
        """Check if path is a directory

        Parameters
        ----------
        path : str
            Path to check

        Returns
        -------
        bool
            True if path is a directory, False otherwise
        """
        try:
            info = self.info(path)
            return info["type"] == "directory"
        except FileNotFoundError:
            return False

    @classmethod
    def _strip_protocol(cls, path: str) -> str:
        """Remove protocol from path and extract file path

        Parameters
        ----------
        path : str
            Path that may include protocol

        Returns
        -------
        str
            File path without protocol
        """
        if not path.startswith("gitlab://"):
            result = super()._strip_protocol(path)
            # Handle case where parent returns list
            if isinstance(result, list):
                return result[0] if result else ""
            return result

        # Handle new GitLab URI format: gitlab://project/path@ref/file/path
        path_without_protocol = path[9:]  # Remove "gitlab://"

        # Split on '@' to separate project path from ref/file path
        if "@" in path_without_protocol:
            project_path, ref_and_file = path_without_protocol.split("@", 1)

            # Split the ref/file path to get just the file path
            if "/" in ref_and_file:
                ref, file_path = ref_and_file.split("/", 1)
                return file_path
            else:
                # No file path after ref, return empty
                return ""
        else:
            # No '@' symbol - need to extract file path from project/file structure
            # This is tricky without knowing the exact project structure
            # For now, assume the project is the first two parts (group/project)
            parts = path_without_protocol.split("/")
            if len(parts) > 2:
                # Return everything after the assumed project path
                return "/".join(parts[2:])
            else:
                return ""

    @staticmethod
    def _get_kwargs_from_urls(path: str) -> dict[str, str]:
        """Extract filesystem kwargs from URL

        Parses URIs in the format:
        - gitlab://project/path@ref/file.txt
        - gitlab://project/path/file.txt (uses default branch)

        Parameters
        ----------
        path : str
            URL path in GitLab URI format

        Returns
        -------
        dict
            Extracted parameters including project_path and optionally sha
        """
        if not path.startswith("gitlab://"):
            return {}

        # Remove the protocol
        path_without_protocol = path[9:]  # Remove "gitlab://"

        # Split on '@' to separate project path from ref/file path
        if "@" in path_without_protocol:
            project_and_ref, file_path = path_without_protocol.split("@", 1)

            # Split the ref/file path to get the ref and file
            if "/" in file_path:
                ref, _ = file_path.split("/", 1)
                result = {"project_path": project_and_ref}
                if ref:  # Only add sha if ref is not empty
                    result["sha"] = ref
                return result
            else:
                # No file path, just ref
                return (
                    {"project_path": project_and_ref, "sha": file_path}
                    if file_path
                    else {"project_path": project_and_ref}
                )
        else:
            # No '@' symbol, extract project path from the full path
            if "/" in path_without_protocol:
                # Find where the project path ends and file path begins
                # This is tricky - we'll assume the project path has at least one '/'
                # and try to be smart about it
                parts = path_without_protocol.split("/")
                if len(parts) >= 2:
                    # Take first two parts as minimum project path (group/project)
                    project_path = "/".join(parts[:2])
                    return {"project_path": project_path}
                else:
                    return {"project_path": parts[0]}
            else:
                return {"project_path": path_without_protocol}
