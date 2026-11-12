"""Thin GitHub REST client.

Only HTTP concerns live here: authentication, error translation and the handful
of endpoints Workmods needs. Publish orchestration is in :mod:`workmods.publisher`.
"""

from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any

import requests

API_ROOT = "https://api.github.com"
USER_AGENT = "Workmods-Client"


class GitHubError(RuntimeError):
    """An API call failed. ``status`` is the HTTP status when one was received."""

    def __init__(self, message: str, status: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status = status
        self.payload = payload


class GitHubClient:
    def __init__(self, token: str = "", timeout: int = 30, session: requests.Session | None = None):
        self.token = (token or "").strip()
        self.timeout = timeout
        self.session = session or requests.Session()

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    # -- plumbing -----------------------------------------------------------
    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        if not url.startswith("http"):
            url = f"{API_ROOT}{url}"
        kwargs.setdefault("timeout", self.timeout)
        headers = dict(self.headers)
        headers.update(kwargs.pop("headers", {}) or {})
        try:
            response = self.session.request(method, url, headers=headers, **kwargs)
        except requests.RequestException as exc:
            raise GitHubError(f"Network error while calling GitHub: {exc}") from exc

        if response.status_code >= 400:
            message = ""
            try:
                message = response.json().get("message", "")
            except ValueError:
                message = (response.text or "").strip()[:300]
            raise GitHubError(
                f"GitHub API {response.status_code}: {message or response.reason}",
                status=response.status_code,
                payload=response.text,
            )
        return response

    # -- account ------------------------------------------------------------
    def get_user(self) -> dict[str, Any]:
        if not self.token:
            raise GitHubError("Not authenticated", status=401)
        return self._request("GET", "/user").json()

    def list_repos(self, per_page: int = 100) -> list[dict[str, Any]]:
        return self._request(
            "GET", f"/user/repos?per_page={per_page}&sort=updated"
        ).json()

    def get_repo(self, repo: str) -> dict[str, Any]:
        return self._request("GET", f"/repos/{repo}").json()

    def create_repo(self, name: str, private: bool = False, auto_init: bool = True) -> dict[str, Any]:
        return self._request(
            "POST",
            "/user/repos",
            json={"name": name, "private": private, "auto_init": auto_init},
        ).json()

    # -- repository contents ------------------------------------------------
    def get_file_sha(self, repo: str, path: str, ref: str | None = None) -> str | None:
        try:
            data = self._request("GET", f"/repos/{repo}/contents/{path}", params=_ref(ref)).json()
        except GitHubError as exc:
            if exc.status == 404:
                return None
            raise
        if isinstance(data, dict):
            return data.get("sha")
        return None

    def put_file(
        self,
        repo: str,
        path: str,
        content: bytes,
        message: str,
        branch: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content).decode("utf-8"),
        }
        if branch:
            payload["branch"] = branch
        existing = self.get_file_sha(repo, path, ref=branch)
        if existing:
            payload["sha"] = existing
        return self._request("PUT", f"/repos/{repo}/contents/{path}", json=payload).json()

    def delete_file(
        self,
        repo: str,
        path: str,
        message: str,
        branch: str | None = None,
    ) -> bool:
        """Delete ``path``; returns ``False`` when the file does not exist."""
        try:
            data = self._request("GET", f"/repos/{repo}/contents/{path}", params=_ref(branch)).json()
        except GitHubError as exc:
            if exc.status == 404:
                return False
            raise
        sha = data.get("sha") if isinstance(data, dict) else None
        if not sha:
            return False
        payload: dict[str, Any] = {"message": message, "sha": sha}
        if branch:
            payload["branch"] = branch
        self._request("DELETE", f"/repos/{repo}/contents/{path}", json=payload)
        return True

    # -- releases -----------------------------------------------------------
    def create_release(self, repo: str, tag: str, name: str, body: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/repos/{repo}/releases",
            json={"tag_name": tag, "name": name, "body": body, "draft": False},
        ).json()

    def get_release_by_tag(self, repo: str, tag: str) -> dict[str, Any] | None:
        try:
            return self._request("GET", f"/repos/{repo}/releases/tags/{tag}").json()
        except GitHubError as exc:
            if exc.status == 404:
                return None
            raise

    def ensure_release(self, repo: str, tag: str, body: str = "") -> dict[str, Any]:
        """Return the release for ``tag``, creating it when it does not exist."""
        existing = self.get_release_by_tag(repo, tag)
        if existing:
            return existing
        try:
            return self.create_release(repo, tag, tag, body)
        except GitHubError as exc:
            if exc.status == 422:  # tag already exists but release did not
                existing = self.get_release_by_tag(repo, tag)
                if existing:
                    return existing
            raise

    def _post_asset(self, url: str, filename: str, file_path: str | Path) -> dict[str, Any]:
        return self._request(
            "POST",
            f"{url}?name={filename}",
            data=Path(file_path).read_bytes(),
            headers={"Content-Type": "application/zip"},
        ).json()

    def upload_release_asset(self, upload_url: str, filename: str, file_path: str | Path) -> dict[str, Any]:
        """Upload an asset, replacing a same-named asset from an earlier attempt."""
        url = upload_url.split("{", 1)[0]
        try:
            return self._post_asset(url, filename, file_path)
        except GitHubError as exc:
            if exc.status != 422:
                raise

        # Asset already exists on this release (re-publishing the same version):
        # delete the old one, then upload again.
        release_api = upload_url.split("/assets", 1)[0].split("github.com", 1)[-1]
        assets = self._request("GET", f"{API_ROOT}{release_api}/assets?per_page=100").json()
        for asset in assets if isinstance(assets, list) else []:
            if asset.get("name") == filename:
                self._request("DELETE", f"{API_ROOT}{release_api}/assets/{asset['id']}")
        return self._post_asset(url, filename, file_path)

    # -- git refs / forks ---------------------------------------------------
    def get_git_ref(self, repo: str, branch: str) -> str | None:
        """Return the commit SHA a branch points at, or ``None`` when missing."""
        try:
            data = self._request("GET", f"/repos/{repo}/git/ref/heads/{branch}").json()
        except GitHubError as exc:
            if exc.status == 404:
                return None
            raise
        obj = data.get("object") if isinstance(data, dict) else None
        return str(obj.get("sha")) if obj and obj.get("sha") else None

    def ensure_branch(self, repo: str, branch: str, sha: str) -> None:
        """Create ``branch`` at ``sha`` or move it there when it already exists."""
        existing = self.get_git_ref(repo, branch)
        if existing == sha:
            return
        if existing:
            self._request(
                "PATCH",
                f"/repos/{repo}/git/refs/heads/{branch}",
                json={"sha": sha, "force": True},
            )
            return
        for attempt in range(6):
            try:
                self._request(
                    "POST",
                    f"/repos/{repo}/git/refs",
                    json={"ref": f"refs/heads/{branch}", "sha": sha},
                )
                return
            except GitHubError as exc:
                # A freshly created fork can lag behind its parent for a moment.
                if exc.status not in (404, 409, 422) or attempt == 5:
                    raise
                time.sleep(1.5 * (attempt + 1))

    def ensure_fork(self, repo: str, login: str = "") -> str:
        """Return ``login/<repo name>``, forking ``repo`` when it is missing."""
        owner, _, name = repo.partition("/")
        if not name:
            raise GitHubError(f"Invalid repository: {repo}", status=422)
        login = login or str(self.get_user().get("login") or "")
        candidate = f"{login}/{name}"
        try:
            self.get_repo(candidate)
            return candidate
        except GitHubError as exc:
            if exc.status != 404:
                raise
        self._request("POST", f"/repos/{owner}/{name}/forks")
        return candidate

    def wait_for_repo(self, repo: str, attempts: int = 20, delay: float = 1.5) -> dict[str, Any]:
        """Poll until a freshly forked repository is readable."""
        last: GitHubError | None = None
        for _ in range(attempts):
            try:
                return self.get_repo(repo)
            except GitHubError as exc:
                if exc.status != 404:
                    raise
                last = exc
                time.sleep(delay)
        raise GitHubError(f"Fork {repo} did not become available in time", status=404, payload=str(last))

    # -- pull requests ------------------------------------------------------
    def find_open_pull(self, repo: str, head: str) -> dict[str, Any] | None:
        pulls = self._request(
            "GET", f"/repos/{repo}/pulls", params={"state": "open", "head": head}
        ).json()
        if isinstance(pulls, list) and pulls:
            return pulls[0]
        return None

    def create_pull(
        self, repo: str, title: str, head: str, base: str, body: str = ""
    ) -> dict[str, Any]:
        """Open a pull request, returning the existing one when it is already open."""
        try:
            return self._request(
                "POST",
                f"/repos/{repo}/pulls",
                json={"title": title, "head": head, "base": base, "body": body},
            ).json()
        except GitHubError as exc:
            if exc.status != 422:
                raise
            existing = self.find_open_pull(repo, head)
            if existing:
                return existing
            raise


def _ref(branch: str | None) -> dict[str, str]:
    return {"ref": branch} if branch else {}


__all__ = ["API_ROOT", "GitHubClient", "GitHubError"]
