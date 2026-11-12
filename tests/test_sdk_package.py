import json
import zipfile
from pathlib import Path

from workmods.cli import main
from workmods.devtools import validate_mod, validate_package
from workmods.storage import package_mod, sha256_file


def _mod(tmp_path: Path, name: str = "mod") -> Path:
    folder = tmp_path / name
    folder.mkdir()
    (folder / "workmod.json").write_text(
        json.dumps(
            {
                "id": "abc12345",
                "game_id": "game-a",
                "name": "Sample",
                "version": "1.0.0",
                "bundles": ["content.bundle"],
            }
        ),
        encoding="utf-8",
    )
    (folder / "content.bundle").write_bytes(b"BUNDLE")
    return folder


def test_validate_package_accepts_packed_mod(tmp_path):
    folder = _mod(tmp_path)
    archive = tmp_path / "sample.zip"
    package_mod(folder, archive)

    result = validate_package(archive)
    assert result.ok
    assert result.errors == []


def test_validate_package_checks_sha256(tmp_path):
    folder = _mod(tmp_path)
    archive = tmp_path / "sample.zip"
    package_mod(folder, archive)

    result = validate_package(archive, expected_sha256=sha256_file(archive))
    assert result.ok

    result = validate_package(archive, expected_sha256="0" * 64)
    assert not result.ok
    assert any("SHA-256" in error for error in result.errors)


def test_validate_package_rejects_traversal(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../evil.txt", "x")
        handle.writestr("workmod.json", "{}")

    result = validate_package(archive)
    assert not result.ok
    assert any("unsafe archive entry" in error for error in result.errors)


def test_validate_package_rejects_missing_and_non_zip(tmp_path):
    assert not validate_package(tmp_path / "missing.zip").ok

    text = tmp_path / "mod.txt"
    text.write_text("not a zip", encoding="utf-8")
    result = validate_package(text)
    assert not result.ok
    assert any("not a mod folder or ZIP" in error for error in result.errors)


def test_validate_package_accepts_directory(tmp_path):
    folder = _mod(tmp_path)
    result = validate_package(folder)
    assert result.ok
    assert result.warnings


def test_cli_validate_package_json(tmp_path, capsys):
    folder = _mod(tmp_path)
    archive = tmp_path / "sample.zip"
    package_mod(folder, archive)

    assert main(["validate-package", str(archive), "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True

    assert main(["validate-package", str(tmp_path / "missing.zip")]) == 1


def test_sample_mod_is_valid():
    sample = Path("unity-sdk/examples/sample-mod")
    assert validate_mod(sample).ok
    assert validate_package(sample).ok
