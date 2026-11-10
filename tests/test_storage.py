import zipfile
from pathlib import Path

import pytest

from workmods.storage import (
    StorageError,
    install_package,
    package_mod,
    read_mod_meta,
    safe_extract,
    scan_installed_mods,
    sha256_file,
    uninstall_mod,
)


def make_mod_files(root: Path) -> Path:
    mod_dir = root / "source"
    (mod_dir / "bundles").mkdir(parents=True)
    (mod_dir / "readme.txt").write_text("hello", encoding="utf-8")
    (mod_dir / "bundles" / "ui.bundle").write_bytes(b"BUNDLE")
    (mod_dir / "__pycache__").mkdir()
    (mod_dir / "__pycache__" / "junk.pyc").write_bytes(b"junk")
    (mod_dir / ".devers_meta.json").write_text("{}", encoding="utf-8")
    return mod_dir


def test_package_and_install_roundtrip(tmp_path):
    source = make_mod_files(tmp_path)
    archive = tmp_path / "mod.zip"

    package_mod(source, archive)
    install_root = tmp_path / "installed"
    target = install_package(
        archive,
        install_root,
        "a1b2c3d4",
        {"game_id": "game-a", "name": "Neon UI", "version": "1.2.0"},
    )

    assert (target / "readme.txt").read_text(encoding="utf-8") == "hello"
    assert (target / "bundles" / "ui.bundle").read_bytes() == b"BUNDLE"
    # Internal metadata and caches are never published.
    with zipfile.ZipFile(archive) as zip_file:
        names = zip_file.namelist()
    assert ".devers_meta.json" not in names
    assert not any("__pycache__" in name for name in names)

    meta = read_mod_meta(target)
    assert meta["id"] == "a1b2c3d4"
    assert meta["game_id"] == "game-a"
    assert meta["installed_at"]


def test_sha256_matches_hashlib(tmp_path):
    import hashlib

    path = tmp_path / "file.bin"
    path.write_bytes(b"workmods")
    assert sha256_file(path) == hashlib.sha256(b"workmods").hexdigest()


def test_install_unwraps_single_wrapper_directory(tmp_path):
    source = tmp_path / "wrapped" / "MyMod"
    source.mkdir(parents=True)
    (source / "file.txt").write_text("data", encoding="utf-8")
    archive = tmp_path / "wrapped.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.write(source / "file.txt", "MyMod/file.txt")

    target = install_package(archive, tmp_path / "root", "wrapped")
    assert (target / "file.txt").is_file()
    assert not (target / "MyMod").exists()


def test_zip_slip_is_rejected(tmp_path):
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr("../escaped.txt", "nope")

    with pytest.raises(StorageError):
        safe_extract(archive, tmp_path / "out")
    assert not (tmp_path / "escaped.txt").exists()


def test_invalid_mod_id_is_rejected(tmp_path):
    archive = tmp_path / "mod.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr("file.txt", "x")
    with pytest.raises(StorageError):
        install_package(archive, tmp_path / "root", "../escape")


def test_scan_and_uninstall(tmp_path):
    root = tmp_path / "mods"
    (root / "one").mkdir(parents=True)
    (root / "one" / ".devers_meta.json").write_text(
        '{"id": "one", "name": "First", "game_id": "game-a"}', encoding="utf-8"
    )
    (root / "two").mkdir()
    (root / ".hidden").mkdir()

    mods = scan_installed_mods(root, "game-a")
    assert [mod.mod_id for mod in mods] == ["one", "two"]
    assert mods[1].game_id == "game-a"

    assert uninstall_mod(root, "one") is True
    assert not (root / "one").exists()
    assert uninstall_mod(root, "one") is False


def test_uninstall_refuses_outside_paths(tmp_path):
    root = tmp_path / "mods"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    with pytest.raises(StorageError):
        uninstall_mod(root, "../outside")
    assert outside.exists()
