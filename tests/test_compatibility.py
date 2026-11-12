import json

from workmods.cli import main
from workmods.devtools import validate_mod, validate_package


def _mod(tmp_path, **overrides):
    folder = tmp_path / "mod"
    folder.mkdir()
    manifest = {
        "id": "abc12345",
        "game_id": "game-a",
        "name": "Sample",
        "version": "1.0.0",
        "engine": "unity",
        "unity_version": "2021.3",
        "platforms": ["windows", "linux"],
        "min_client_version": "1.0b",
        "min_sdk_version": "1.0",
        "bundles": ["content.bundle"],
    }
    manifest.update(overrides)
    (folder / "workmod.json").write_text(json.dumps(manifest), encoding="utf-8")
    (folder / "content.bundle").write_bytes(b"BUNDLE")
    return folder


def test_compatibility_accepts_matching_target(tmp_path):
    result = validate_mod(
        _mod(tmp_path),
        compatibility={"engine": "unity", "unity_version": "2022.3", "platforms": ["windows"]},
    )
    assert result.ok


def test_compatibility_rejects_wrong_engine_unity_and_platform(tmp_path):
    folder = _mod(tmp_path)
    result = validate_mod(
        folder,
        compatibility={"engine": "unreal", "unity_version": "2020.3", "platforms": ["android"]},
    )
    assert not result.ok
    assert any("engine" in error for error in result.errors)
    assert any("Unity version" in error for error in result.errors)
    assert any("platform" in error for error in result.errors)


def test_compatibility_rejects_old_client_and_sdk(tmp_path):
    result = validate_mod(
        _mod(tmp_path),
        compatibility={"client_version": "0.9", "sdk_version": "0.5"},
    )
    assert not result.ok
    assert any("client version" in error for error in result.errors)
    assert any("SDK version" in error for error in result.errors)


def test_compatibility_cli_flags(tmp_path, capsys):
    folder = _mod(tmp_path)
    assert main([
        "validate", str(folder), "--json",
        "--engine", "unity", "--unity-version", "2022.3", "--platform", "windows",
    ]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True

    assert main([
        "validate", str(folder), "--json",
        "--engine", "unreal",
    ]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is False


def test_package_compatibility_is_checked_after_extraction(tmp_path):
    from workmods.storage import package_mod

    folder = _mod(tmp_path)
    archive = tmp_path / "mod.zip"
    package_mod(folder, archive)
    result = validate_package(archive, compatibility={"engine": "unreal"})
    assert not result.ok
    assert any("engine" in error for error in result.errors)
