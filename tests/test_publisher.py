from pathlib import Path

import pytest

from workmods.publisher import ModPublisher, PublishRequest
from workmods.storage import StorageError


class FakeGitHub:
    def __init__(self, token="token", default_branch="main"):
        self.token = token
        self.default_branch = default_branch
        self.uploaded = {}
        self.dispatches = []
        self.release_asset = None
        self.validated = []

    def get_repo(self, repo):
        self.validated.append(repo)
        return {"default_branch": self.default_branch}

    def put_file(self, repo, path, content, message):
        self.uploaded[path] = content
        return {}

    def ensure_release(self, repo, tag, body=""):
        return {
            "upload_url": f"https://uploads.github.com/repos/{repo}/releases/1/assets{{?name,label}}",
            "html_url": f"https://github.com/{repo}/releases/tag/{tag}",
        }

    def upload_release_asset(self, upload_url, filename, file_path):
        self.release_asset = (filename, Path(file_path).read_bytes())
        return {}

    def dispatch(self, event_type, client_payload, repo):
        self.dispatches.append((event_type, client_payload, repo))


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
        bot_secret="top-secret",
        registry_repo="Made-by-One/Devers-Workmods",
    )
    params.update(overrides)
    return PublishRequest(**params)


def test_publish_uploads_release_and_registry_payload(tmp_path):
    client = FakeGitHub()
    publisher = ModPublisher(client)

    result = publisher.publish(make_request(tmp_path))

    assert client.uploaded["mod.bundle"] == b"BUNDLE"
    assert client.uploaded["readme.txt"] == b"hi"
    assert result.download_url == (
        "https://github.com/someone/neon-ui/releases/download/v1.2.0/a1b2c3d4.zip"
    )
    assert result.release_url.endswith("/v1.2.0")

    event_type, payload, repo = client.dispatches[0]
    assert event_type == "add_mod"
    assert repo == "Made-by-One/Devers-Workmods"
    assert payload["game_id"] == "space-rangers"
    assert payload["entry_asset"] == "NeonHud"
    assert payload["tags"] == ["ui"]
    # The secret authenticates the dispatch but must never land in registry.json.
    assert payload["secret"] == "top-secret"
    assert "secret" not in result.payload
    assert result.sha256 == payload["sha256"]


def test_publish_uses_repository_default_branch_for_raw_urls(tmp_path):
    client = FakeGitHub(default_branch="master")
    request = make_request(tmp_path)
    icon = tmp_path / "icon.png"
    icon.write_bytes(b"PNG")
    request.icon_path = str(icon)

    publisher = ModPublisher(client)
    publisher.publish(request)

    _, payload, _ = client.dispatches[0]
    assert payload["icon_url"] == "https://raw.githubusercontent.com/someone/neon-ui/master/icon.png"
    assert client.uploaded["icon.png"] == b"PNG"


def test_publish_validates_before_touching_network(tmp_path):
    publisher = ModPublisher(FakeGitHub())

    with pytest.raises(StorageError):
        publisher.publish(make_request(tmp_path, files_dir=str(tmp_path / "missing")))
    with pytest.raises(StorageError):
        publisher.publish(make_request(tmp_path, version="1.0 / beta"))
    with pytest.raises(StorageError):
        publisher.publish(make_request(tmp_path, repo=""))
    assert publisher.client.dispatches == []


def test_unpublish_dispatches_remove_event():
    client = FakeGitHub()
    ModPublisher(client).unpublish("a1b2c3d4", registry_repo="owner/registry", bot_secret="s")

    event_type, payload, repo = client.dispatches[0]
    assert event_type == "remove_mod"
    assert payload == {"secret": "s", "id": "a1b2c3d4"}
    assert repo == "owner/registry"


def test_publish_requires_token(tmp_path):
    publisher = ModPublisher(FakeGitHub(token=""))
    with pytest.raises(StorageError):
        publisher.publish(make_request(tmp_path))
