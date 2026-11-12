import json
from pathlib import Path

import pytest

from workmods.cli import main
from workmods.devtools import (
    DevToolsError,
    new_mod_id,
    pack_mod,
    read_manifest,
    scaffold_mod,
    validate_mod,
    version_problem,
)
from workmods.storage import sha256_file


def test_new_mod_id_is_short_and_unique():
    first, second = new_mod_id(), new_mod_id()
    assert len(first) == 8
    assert first != second


def test_version_problem():
    assert version_problem("1.2.0") is None
    assert version_problem("") == "version is required"
    assert version_problem("1.0 beta")
    assert version_problem("1/2")


def test_scaffold_writes_manifest_and_refuses_overwrite(tmp_path):
    folder = tmp_path / "neon-ui"
    manifest_path = scaffold_mod(
        folder, name="Neon UI", game_id="Space Rangers", author="me", tags=["ui", "hud"]
    )

    assert manifest_path == folder / "workmod.json"
    manifest = read_manifest(folder)
    assert manifest["name"] == "Neon UI"
    assert manifest["game_id"] == "space-rangers"
    assert manifest["tags"] == ["ui", "hud"]

    with pytest.raises(DevToolsError):
        scaffold_mod(folder)
    scaffold_mod(folder, force=True)


def test_validate_accepts_a_complete_mod(tmp_path):
    folder = tmp_path / "mod"
    folder.mkdir()
    (folder / "workmod.json").write_text(
        json.dumps(
            {
                "id": "abc12345",
                "game_id": "game-a",
                "name": "Mod",
                "version": "1.0.0",
                "entry_asset": "Main",
                "bundles": ["mod.bundle"],
            }
        ),
        encoding="utf-8",
    )
    (folder / "mod.bundle").write_bytes(b"BUNDLE")
    (folder / "icon.png").write_bytes(b"PNG")
    (folder / "banner.png").write_bytes(b"PNG")

    result = validate_mod(folder)
    assert result.ok
    assert result.errors == []


def test_validate_reports_missing_manifest_and_bundles(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert not validate_mod(empty).ok

    folder = tmp_path / "mod"
    folder.mkdir()
    (folder / "workmod.json").write_text(
        json.dumps({"name": "Mod", "version": "1.0.0", "bundles": ["missing.bundle"]}),
        encoding="utf-8",
    )
    (folder / "content.bin").write_bytes(b"x")
    result = validate_mod(folder)
    assert not result.ok
    assert any("missing.bundle" in error for error in result.errors)
    assert any("game_id" in warning for warning in result.warnings)


def test_pack_mod_creates_zip_with_hash(tmp_path):
    folder = tmp_path / "mod"
    folder.mkdir()
    (folder / "workmod.json").write_text('{"name": "Mod", "version": "1.0.0"}', encoding="utf-8")
    (folder / "file.txt").write_text("hello", encoding="utf-8")

    result = pack_mod(folder)
    assert result.path == tmp_path / "mod.zip"
    assert result.path.is_file()
    assert result.sha256 == sha256_file(result.path)
    assert result.size == result.path.stat().st_size


def test_cli_init_validate_pack(tmp_path, capsys):
    folder = tmp_path / "cool-mod"
    assert main(["init", str(folder), "--name", "Cool"]) == 0
    capsys.readouterr()
    assert (folder / "workmod.json").is_file()

    (folder / "mod.bundle").write_bytes(b"BUNDLE")
    assert main(["validate", str(folder), "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True

    assert main(["pack", str(folder), "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert Path(output["path"]).is_file()
    assert output["sha256"]


def test_cli_validate_fails_for_missing_mod(tmp_path):
    assert main(["validate", str(tmp_path / "nope")]) == 1
