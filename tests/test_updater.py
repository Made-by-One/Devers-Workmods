import hashlib
import io
import tarfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from workmods.updater import (
    ClientUpdater,
    ReleaseAsset,
    ReleaseInfo,
    UpdateError,
    is_newer,
    verify_sha256,
    verify_signature_data,
)


def _updater(tmp_path: Path, target: Path) -> ClientUpdater:
    return ClientUpdater(
        current_version="1.0b",
        executable_path=target,
        state_dir=tmp_path / "state",
        backup_dir=tmp_path / "backups",
    )


def test_is_newer_compares_numeric_parts():
    assert is_newer("1.1b", "1.0b")
    assert is_newer("v2.0.0", "1.9.9")
    assert not is_newer("1.0b", "1.0b")
    assert not is_newer("0.9", "1.0b")


def test_sha256_verification(tmp_path):
    path = tmp_path / "update.bin"
    path.write_bytes(b"update")
    expected = hashlib.sha256(b"update").hexdigest()
    assert verify_sha256(path, expected)
    assert not verify_sha256(path, "0" * 64)


def test_apply_and_rollback_restore_previous_executable(tmp_path):
    target = tmp_path / "Workmods"
    target.write_bytes(b"old")
    update = tmp_path / "new"
    update.write_bytes(b"new")
    updater = _updater(tmp_path, target)

    result = updater.apply_update(update, version="1.1b")
    assert result.applied
    assert target.read_bytes() == b"new"
    assert result.backup and result.backup.read_bytes() == b"old"

    assert updater.rollback()
    assert target.read_bytes() == b"old"
    assert updater.finalize_pending_update() is False


def test_apply_failure_rolls_back_previous_executable(tmp_path):
    target = tmp_path / "Workmods"
    target.write_bytes(b"old")
    updater = _updater(tmp_path, target)

    with pytest.raises(UpdateError):
        updater.apply_update(tmp_path / "missing")
    assert target.read_bytes() == b"old"


def test_check_for_updates_uses_release_client(tmp_path):
    target = tmp_path / "Workmods"
    target.write_bytes(b"old")
    updater = _updater(tmp_path, target)

    class FakeClient:
        def latest_release(self):
            return ReleaseInfo(
                tag_name="v1.1b",
                version="1.1b",
                assets=[ReleaseAsset("Workmods-linux.tar.gz", "https://example.invalid/a")],
            )

    updater.release_client = FakeClient()
    release = updater.check_for_updates()
    assert release is not None
    assert release.version == "1.1b"


def test_rsa_signature_verification(tmp_path):
    data = b"signed release checksums\n"
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    signature = key.sign(data, padding.PKCS1v15(), hashes.SHA256())

    assert verify_signature_data(data, signature, public_key=public_key)
    assert not verify_signature_data(data + b"x", signature, public_key=public_key)


def test_apply_update_extracts_archive_executable(tmp_path):
    target = tmp_path / "Workmods"
    target.write_bytes(b"old")
    update = tmp_path / "Workmods-linux-x86_64.tar.gz"
    payload = b"new"
    with tarfile.open(update, "w:gz") as archive:
        info = tarfile.TarInfo("Workmods")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))

    updater = _updater(tmp_path, target)
    result = updater.apply_update(update, version="1.1c")
    assert result.applied
    assert target.read_bytes() == b"new"


def test_download_rejects_release_without_asset(tmp_path):
    target = tmp_path / "Workmods"
    target.write_bytes(b"old")
    updater = _updater(tmp_path, target)
    release = ReleaseInfo(tag_name="v1.1b", version="1.1b")
    with pytest.raises(UpdateError):
        updater.download_release(release)
