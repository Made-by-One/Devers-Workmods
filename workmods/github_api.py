"""Thin GitHub REST client.

Only HTTP concerns live here: authentication, error translation and the handful
of endpoints Workmods needs. Publish orchestration is in :mod:`workmods.publisher`.
"""

from __future__ import annotations

import base64
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
    def get_file_sha(self, repo: str, path: str) -> str | None:
        try:
            data = self._request("GET", f"/repos/{repo}/contents/{path}").json()
        except GitHubError as exc:
            if exc.status == 404:
                return None
            raise
        if isinstance(data, dict):
            return data.get("sha")
        return None

    def put_file(self, repo: str, path: str, content: bytes, message: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content).decode("utf-8"),
        }
        existing = self.get_file_sha(repo, path)
        if existing:
            payload["sha"] = existing
        return self._request("PUT", f"/repos/{repo}/contents/{path}", json=payload).json()

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

    # -- registry -----------------------------------------------------------
    def dispatch(self, event_type: str, client_payload: dict[str, Any], repo: str) -> None:
        self._request(
            "POST",
            f"/repos/{repo}/dispatches",
            json={"event_type": event_type, "client_payload": client_payload},
        )


__all__ = ["API_ROOT", "GitHubClient", "GitHubError"]
