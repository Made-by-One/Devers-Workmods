"""Command line tooling for mod authors: ``python -m workmods <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from workmods.config import APP_VERSION
from typing import Any, Sequence

from workmods.devtools import (
    DevToolsError,
    pack_mod,
    scaffold_mod,
    validate_mod,
    validate_package,
)
from workmods.profiles import ModProfileStore, ProfileError
from workmods.updater import ClientUpdater, UpdateError
from workmods.models import DEFAULT_GAME_ID


def _print_validation(folder: Path, result) -> None:
    print(f"Validating {folder}")
    for error in result.errors:
        print(f"  error: {error}")
    for warning in result.warnings:
        print(f"  warning: {warning}")
    if result.ok:
        print("OK" + (" with warnings" if result.warnings else ""))


def _cmd_init(args: argparse.Namespace) -> int:
    tags = [tag.strip() for tag in (args.tags or "").split(",") if tag.strip()]
    try:
        manifest = scaffold_mod(
            args.directory,
            name=args.name,
            game_id=args.game,
            author=args.author,
            version=args.version,
            entry_asset=args.entry,
            tags=tags,
            force=args.force,
        )
    except DevToolsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Created {manifest}")
    print("Next: put your bundles next to it, fill in the fields, then run:")
    print(f"  python -m workmods validate {Path(args.directory)}")
    return 0


def _compatibility_from_args(args: argparse.Namespace) -> dict[str, Any] | None:
    compat: dict[str, Any] = {}
    if getattr(args, "compatibility", None):
        try:
            import json

            parsed = json.loads(args.compatibility)
            if isinstance(parsed, dict):
                compat.update(parsed)
            elif isinstance(parsed, list):
                compat["platforms"] = parsed
            else:
                compat["target"] = parsed
        except (json.JSONDecodeError, ValueError):
            for chunk in str(args.compatibility).replace(";", ",").split(","):
                chunk = chunk.strip()
                if not chunk:
                    continue
                if ":" in chunk:
                    key, value = chunk.split(":", 1)
                    compat[key.strip()] = value.strip()
                else:
                    compat.setdefault("platforms", []).append(chunk)
    if getattr(args, "engine", None) or getattr(args, "sdk", None):
        compat["engine"] = args.engine or args.sdk
    if getattr(args, "unity_version", None) or getattr(args, "unity", None):
        compat["unity_version"] = args.unity_version or args.unity
    platforms = getattr(args, "platform", None) or getattr(args, "platforms", None) or []
    if platforms:
        compat["platforms"] = list(platforms)
    if getattr(args, "client_version", None):
        compat["client_version"] = args.client_version
    if getattr(args, "sdk_version", None):
        compat["sdk_version"] = args.sdk_version
    return compat or None


def _cmd_validate(args: argparse.Namespace) -> int:
    folder = Path(args.directory)
    result = validate_mod(folder, compatibility=_compatibility_from_args(args))
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
    else:
        _print_validation(folder, result)
    return 0 if result.ok else 1


def _cmd_validate_package(args: argparse.Namespace) -> int:
    package = Path(args.package)
    result = validate_package(
        package,
        expected_sha256=args.sha256,
        compatibility=_compatibility_from_args(args),
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"Validating package {package}")
        for error in result.errors:
            print(f"  error: {error}")
        for warning in result.warnings:
            print(f"  warning: {warning}")
        if result.ok:
            print("OK" + (" with warnings" if result.warnings else ""))
    return 0 if result.ok else 1


def _cmd_pack(args: argparse.Namespace) -> int:
    folder = Path(args.directory)
    try:
        result = pack_mod(folder, args.out)
    except DevToolsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"Packed {result.path}")
        print(f"  size:   {result.size} bytes")
        print(f"  sha256: {result.sha256}")
    return 0


def _default_profile_path() -> Path:
    from workmods.config import CONFIG_DIR

    return CONFIG_DIR / "profiles.json"


def _cmd_profile(args: argparse.Namespace) -> int:
    path = Path(args.file) if args.file else _default_profile_path()
    store = ModProfileStore(path)
    try:
        if path.exists():
            store.load(path)
    except ProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    action = args.profile_action
    if action == "list":
        for name in store.names():
            profile = store.get(name)
            print(f"{name}\t{profile.game_id}\tenabled={len(profile.enabled)}")
        return 0

    if action == "create":
        enabled = [item.strip() for item in (args.enable or "").split(",") if item.strip()]
        disabled = [item.strip() for item in (args.disable or "").split(",") if item.strip()]
        settings = {}
        if args.settings_file:
            try:
                settings = json.loads(Path(args.settings_file).read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                print(f"error: cannot read settings: {exc}", file=sys.stderr)
                return 1
        try:
            store.create(
                args.name,
                game_id=args.game,
                enabled=enabled,
                disabled=disabled,
                settings=settings,
                overwrite=args.force,
            )
            store.save(path)
        except ProfileError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"Created profile {args.name}")
        return 0

    if action == "delete":
        if not store.delete(args.name):
            print(f"error: unknown profile: {args.name}", file=sys.stderr)
            return 1
        store.save(path)
        print(f"Deleted profile {args.name}")
        return 0

    if action == "export":
        destination = Path(args.destination)
        try:
            store.export_profile(args.name, destination)
        except ProfileError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"Exported {args.name} to {destination}")
        return 0

    if action == "import":
        try:
            profile = store.import_profile(Path(args.source), overwrite=args.force)
            store.save(path)
        except ProfileError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"Imported profile {profile.name}")
        return 0

    print("error: unknown profile action", file=sys.stderr)
    return 1


def _cmd_update(args: argparse.Namespace) -> int:
    from workmods.config import CONFIG_DIR

    updater = ClientUpdater(
        current_version=args.current_version or APP_VERSION,
        repo=args.repo,
        executable_path=args.target,
        state_dir=CONFIG_DIR,
    )
    action = args.update_action
    if action == "check":
        try:
            release = updater.check_for_updates()
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if release is None:
            print(f"No update available (current {updater.current_version})")
            return 0
        print(f"Update available: {release.version} ({release.tag_name})")
        asset = release.asset(args.asset)
        if asset is not None:
            print(f"  asset: {asset.name}")
        return 0

    if action == "apply":
        try:
            result = updater.apply_update(
                Path(args.package),
                target=args.target,
                version=args.version or "",
            )
        except (UpdateError, OSError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"Applied update to {result.target}")
        if result.backup:
            print(f"  backup: {result.backup}")
        return 0

    if action == "rollback":
        if updater.rollback(target=args.target):
            print("Rolled back to the previous version")
            return 0
        print("error: no backup available", file=sys.stderr)
        return 1

    if action == "finalize":
        updater.finalize_pending_update()
        print("Finalized pending update")
        return 0

    print("error: unknown update action", file=sys.stderr)
    return 1


def _add_compatibility_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--compatibility", default=None,
        help="target compatibility as JSON or key:value pairs (engine, unity_version, platforms, client_version, sdk_version)",
    )
    parser.add_argument("--engine", "--sdk", dest="engine", default=None, help="target engine/sdk, for example unity")
    parser.add_argument("--unity-version", "--unity", "--target-unity-version", dest="unity_version", default=None, help="target Unity version")
    parser.add_argument(
        "--platform", "--platforms", "--target-platform", dest="platform", action="append",
        default=None, help="target platform (repeatable)",
    )
    parser.add_argument("--client-version", "--target-client-version", dest="client_version", default=None, help="target client version")
    parser.add_argument("--sdk-version", "--target-sdk-version", dest="sdk_version", default=None, help="target SDK version")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m workmods",
        description="Scaffold, validate and package Workmods mods without the desktop UI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create a mod folder and workmod.json")
    init_parser.add_argument("directory", help="folder to create (or update with --force)")
    init_parser.add_argument("--name", default="", help="display name (defaults to folder name)")
    init_parser.add_argument("--game", default=DEFAULT_GAME_ID, help="target game id")
    init_parser.add_argument("--author", default="", help="author / GitHub handle")
    init_parser.add_argument("--version", default="1.0.0", help="initial version")
    init_parser.add_argument("--entry", default="", help="optional default Unity asset name")
    init_parser.add_argument("--tags", default="", help="comma separated tags")
    init_parser.add_argument("--force", action="store_true", help="overwrite an existing manifest")
    init_parser.set_defaults(func=_cmd_init)

    validate_parser = subparsers.add_parser("validate", help="check a mod folder before publishing")
    validate_parser.add_argument("directory", help="mod folder to check")
    validate_parser.add_argument("--json", action="store_true", help="machine readable output")
    _add_compatibility_args(validate_parser)
    validate_parser.set_defaults(func=_cmd_validate)

    package_parser = subparsers.add_parser(
        "validate-package", help="check a packaged mod ZIP or folder before publishing"
    )
    package_parser.add_argument("package", help="mod folder or ZIP archive to check")
    package_parser.add_argument("--sha256", default=None, help="expected SHA-256 of the ZIP")
    package_parser.add_argument("--json", action="store_true", help="machine readable output")
    _add_compatibility_args(package_parser)
    package_parser.set_defaults(func=_cmd_validate_package)

    pack_parser = subparsers.add_parser("pack", help="build the release ZIP and print its SHA-256")
    pack_parser.add_argument("directory", help="mod folder to package")
    pack_parser.add_argument("--out", default=None, help="output ZIP path")
    pack_parser.add_argument("--json", action="store_true", help="machine readable output")
    pack_parser.set_defaults(func=_cmd_pack)

    profile_parser = subparsers.add_parser("profile", help="manage mod profiles (enabled sets and settings presets)")
    profile_sub = profile_parser.add_subparsers(dest="profile_action", required=True)
    profile_parser.add_argument("--file", default=None, help="profile store JSON path")

    profile_create = profile_sub.add_parser("create", help="create a profile")
    profile_create.add_argument("name", help="profile name")
    profile_create.add_argument("--game", default="default", help="target game id")
    profile_create.add_argument("--enable", default="", help="comma separated enabled mod ids")
    profile_create.add_argument("--disable", default="", help="comma separated disabled mod ids")
    profile_create.add_argument("--settings-file", default=None, help="JSON file with settings")
    profile_create.add_argument("--force", action="store_true", help="overwrite an existing profile")
    profile_create.set_defaults(func=_cmd_profile)

    profile_list = profile_sub.add_parser("list", help="list profiles")
    profile_list.set_defaults(func=_cmd_profile)

    profile_delete = profile_sub.add_parser("delete", help="delete a profile")
    profile_delete.add_argument("name", help="profile name")
    profile_delete.set_defaults(func=_cmd_profile)

    profile_export = profile_sub.add_parser("export", help="export a profile to JSON")
    profile_export.add_argument("name", help="profile name")
    profile_export.add_argument("destination", help="output JSON path")
    profile_export.set_defaults(func=_cmd_profile)

    profile_import = profile_sub.add_parser("import", help="import a profile from JSON")
    profile_import.add_argument("source", help="input JSON path")
    profile_import.add_argument("--force", action="store_true", help="overwrite an existing profile")
    profile_import.set_defaults(func=_cmd_profile)

    update_parser = subparsers.add_parser("update", help="check, apply and roll back client updates")
    update_sub = update_parser.add_subparsers(dest="update_action", required=True)
    update_parser.add_argument("--repo", default="Made-by-One/Devers-Workmods", help="GitHub repository")
    update_parser.add_argument("--current-version", default=APP_VERSION, help="currently installed version")
    update_parser.add_argument("--target", default=None, help="executable to update")
    update_parser.add_argument("--asset", default=None, help="release asset name")

    update_check = update_sub.add_parser("check", help="check for a newer release")
    update_check.set_defaults(func=_cmd_update)

    update_apply = update_sub.add_parser("apply", help="apply a downloaded update")
    update_apply.add_argument("package", help="downloaded update file")
    update_apply.add_argument("--target", default=None, help="executable to update")
    update_apply.add_argument("--version", default="", help="version being applied")
    update_apply.set_defaults(func=_cmd_update)

    update_rollback = update_sub.add_parser("rollback", help="restore the previous executable")
    update_rollback.add_argument("--target", default=None, help="executable to restore")
    update_rollback.set_defaults(func=_cmd_update)

    update_finalize = update_sub.add_parser("finalize", help="finalize a pending update")
    update_finalize.set_defaults(func=_cmd_update)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


__all__ = ["build_parser", "main"]
