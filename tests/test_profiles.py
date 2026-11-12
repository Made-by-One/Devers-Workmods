import json

import pytest

from workmods.profiles import (
    ModProfile,
    ModProfileStore,
    ProfileError,
    import_profile,
)


def test_profile_tracks_enabled_disabled_and_presets():
    profile = ModProfile("rpg", game_id="Space Rangers", enabled=["a"], disabled=["b"])

    assert profile.game_id == "space-rangers"
    profile.toggle("b")
    assert profile.is_enabled("b")
    assert "b" not in profile.disabled

    profile.settings = {"volume": 5}
    profile.save_preset("quiet", {"volume": 1})
    assert profile.active_preset == "quiet"
    assert profile.apply_preset("quiet") == {"volume": 1}

    with pytest.raises(ProfileError):
        profile.apply_preset("missing")


def test_profile_store_roundtrip_export_and_import(tmp_path):
    path = tmp_path / "profiles.json"
    store = ModProfileStore(path)
    store.create("default", game_id="game-a", enabled=["one"], settings={"x": 1})
    store.save()

    restored = ModProfileStore(path)
    restored.load()
    assert restored.get("default").enabled == ["one"]

    exported = restored.export_profile("default", tmp_path / "default.json")
    payload = json.loads(exported.read_text(encoding="utf-8"))
    assert payload["name"] == "default"
    assert payload["settings"] == {"x": 1}

    imported = import_profile(exported)
    assert imported.name == "default"
    assert imported.game_id == "game-a"


def test_profile_store_refuses_duplicate_without_overwrite(tmp_path):
    store = ModProfileStore(tmp_path / "profiles.json")
    store.create("one")
    with pytest.raises(ProfileError):
        store.create("one")
    store.create("one", overwrite=True)
    assert store.get("one") is not None


def test_import_profile_can_overwrite(tmp_path):
    store = ModProfileStore(tmp_path / "profiles.json")
    store.create("one", game_id="game-a")
    source = tmp_path / "one.json"
    source.write_text(
        json.dumps({"name": "one", "game_id": "game-b", "enabled": ["x"]}),
        encoding="utf-8",
    )

    with pytest.raises(ProfileError):
        store.import_profile(source)
    profile = store.import_profile(source, overwrite=True)
    assert profile.game_id == "game-b"
    assert store.get("one").enabled == ["x"]
