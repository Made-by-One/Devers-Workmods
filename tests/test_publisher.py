import json
from pathlib import Path

import pytest

from workmods.publisher import ModPublisher, PublishRequest, submission_path
from workmods.storage import StorageError


class FakeGitHub:
    def __init__(self, token="token", default_branch="main", push=False, existing_submission=False):
        self.token = token
        self.default_branch = default_branch
        self.push = push
        self.existing_submission = existing_submission
        self.uploaded = {}
        self.branches = {}
        self.pulls = []
        self.deleted = []
        self.forked = []
        self.validated = []
        self.files = {"sha256": "base"}

    # -- account ------------------------------------------------------------
    def get_user(self):
        return {"login": "someone"}

    def get_repo(self, repo):
        self.validated.append(repo)
        return {
            "default_branch": self.default_branch,
            "permissions": {"push": self.push},
        }

    # -- contents -----------------------------------------------------------
    def get_file_sha(self, repo, path, ref=None):
        return "sha" if self.existing_submission else None

    def put_file(self, repo, path, content, message, branch=None):
        self.uploaded[path] = {"repo": repo, "content": content, "branch": branch}
        return {}

    def delete_file(self, repo, path, message, branch=None):
        self.deleted.append((repo, path, branch))
        return True

    def ensure_release(self, repo, tag, body=""):
        return {
            "upload_url": f"https://uploads.github.com/repos/{repo}/releases/1/assets{{?name,label}}",
            "html_url": f"https://github.com/{repo}/releases/tag/{tag}",
        }

    def upload_release_asset(self, upload_url, filename, file_path):
        return {}

    # -- registry pull requests ---------------------------------------------
    def get_git_ref(self, repo, branch):
        return "base-sha"

    def ensure_branch(self, repo, branch, sha):
        self.branches[branch] = sha

    def ensure_fork(self, repo, login=""):
        fork = f"{login or 'someone'}/{repo.split('/', 1)[1]}"
        self.forked.append(fork)
        return fork

    def wait_for_repo(self, repo, attempts=20, delay=1.5):
        return {"full_name": repo}

    def create_pull(self, repo, title, head, base, body=""):
        pull = {
            "html_url": f"https://github.com/{repo}/pull/{len(self.pulls) + 1}",
            "title": title,
            "head": head,
            "base": base,
            "body": body,
        }
        self.pulls.append(pull)
        return pull


def make_request(tmp_path: Path, **overrides) -> PublishRequest:
    files = tmp_path / "files"
    files.mkdir(exist_ok=True)
    (files / "mod.bundle").write_bytes(b"BUNDLE")
    (files / "readme.txt").write_text("hi", encoding="utf-8")
    params = dict(
        repo="someone/neon-ui",
        files_dir=str(files),
        mod_id="a1b2c3d4",
        name="Neon UI",
        version="1.2.0",
        game_id="Space Rangers",
        description="Neon HUD",
        author="someone",
        entry_asset="NeonHud",
        tags=["ui"],
        registry_repo="Made-by-One/Devers-Workmods",
    )
    params.update(overrides)
    return PublishRequest(**params)


def test_submission_path_normalizes_game():
    assert submission_path("Space Rangers!", "abc") == "submissions/space-rangers/abc.json"


def test_publish_uploads_release_and_opens_submission_pr(tmp_path):
    client = FakeGitHub()
    publisher = ModPublisher(client)

    result = publisher.publish(make_request(tmp_path))

    assert client.uploaded["mod.bundle"]["content"] == b"BUNDLE"
    assert client.uploaded["readme.txt"]["content"] == b"hi"
    assert result.download_url == (
        "https://github.com/someone/neon-ui/releases/download/v1.2.0/a1b2c3d4.zip"
    )
    assert result.release_url.endswith("/v1.2.0")
    assert result.pr_url == "https://github.com/Made-by-One/Devers-Workmods/pull/1"
    assert result.submission_path == "submissions/space-rangers/a1b2c3d4.json"

    submission = json.loads(client.uploaded[result.submission_path]["content"])
    assert submission["id"] == "a1b2c3d4"
    assert submission["game_id"] == "space-rangers"
    assert submission["entry_asset"] == "NeonHud"
    assert submission["tags"] == ["ui"]
    assert submission["submitted_by"] == "someone"
    assert submission["sha256"] == result.sha256
    assert "secret" not in submission
    # The submission lives on its own branch, not on the default branch.
    assert client.uploaded[result.submission_path]["branch"].startswith("workmods/")
    assert client.uploaded["mod.bundle"]["branch"] is None
    assert client.forked == ["someone/Devers-Workmods"]
    assert client.pulls[0]["head"] == f"someone:{client.uploaded[result.submission_path]['branch']}"
    assert client.pulls[0]["base"] == "main"

    # The payload handed back to the UI mirrors what reviewers see.
    assert result.payload["submitted_by"] == "someone"
    assert "secret" not in result.payload


def test_maintainer_with_push_does_not_fork(tmp_path):
    client = FakeGitHub(push=True)
    publisher = ModPublisher(client)

    result = publisher.publish(make_request(tmp_path))

    assert client.forked == []
    assert client.uploaded[result.submission_path]["repo"] == "Made-by-One/Devers-Workmods"
    assert client.pulls[0]["head"].startswith("someone:")


def test_publish_uses_repository_default_branch_for_raw_urls(tmp_path):
    client = FakeGitHub(default_branch="master")
    request = make_request(tmp_path)
    icon = tmp_path / "icon.png"
    icon.write_bytes(b"PNG")
    request.icon_path = str(icon)

    publisher = ModPublisher(client)
    result = publisher.publish(request)

    submission = json.loads(client.uploaded[result.submission_path]["content"])
    assert submission["icon_url"] == "https://raw.githubusercontent.com/someone/neon-ui/master/icon.png"
    assert client.uploaded["icon.png"]["content"] == b"PNG"


def test_publish_validates_before_touching_network(tmp_path):
    publisher = ModPublisher(FakeGitHub())

    with pytest.raises(StorageError):
        publisher.publish(make_request(tmp_path, files_dir=str(tmp_path / "missing")))
    with pytest.raises(StorageError):
        publisher.publish(make_request(tmp_path, version="1.0 / beta"))
    with pytest.raises(StorageError):
        publisher.publish(make_request(tmp_path, repo=""))
    with pytest.raises(StorageError):
        publisher.publish(make_request(tmp_path, registry_repo=""))
    assert publisher.client.pulls == []
    assert publisher.client.uploaded == {}


def test_unpublish_opens_removal_pr():
    client = FakeGitHub(existing_submission=True)
    pr_url = ModPublisher(client).unpublish(
        "a1b2c3d4", game_id="Space Rangers", registry_repo="owner/registry"
    )

    assert pr_url == "https://github.com/owner/registry/pull/1"
    repo, path, branch = client.deleted[0]
    assert path == "submissions/space-rangers/a1b2c3d4.json"
    assert branch.startswith("workmods/remove-")
    assert client.pulls[0]["title"].startswith("Remove a1b2c3d4")


def test_unpublish_without_submission_file_fails():
    client = FakeGitHub(existing_submission=False)
    with pytest.raises(StorageError):
        ModPublisher(client).unpublish("missing", registry_repo="owner/registry")
    assert client.pulls == []


def test_publish_requires_token(tmp_path):
    publisher = ModPublisher(FakeGitHub(token=""))
    with pytest.raises(StorageError):
        publisher.publish(make_request(tmp_path))
