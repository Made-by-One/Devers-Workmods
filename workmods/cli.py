"""Command line tooling for mod authors: ``python -m workmods <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from workmods.devtools import (
    DevToolsError,
    pack_mod,
    scaffold_mod,
    validate_mod,
    validate_package,
)
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


def _cmd_validate(args: argparse.Namespace) -> int:
    folder = Path(args.directory)
    result = validate_mod(folder)
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
    else:
        _print_validation(folder, result)
    return 0 if result.ok else 1


def _cmd_validate_package(args: argparse.Namespace) -> int:
    package = Path(args.package)
    result = validate_package(package, expected_sha256=args.sha256)
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
    validate_parser.set_defaults(func=_cmd_validate)

    package_parser = subparsers.add_parser(
        "validate-package", help="check a packaged mod ZIP or folder before publishing"
    )
    package_parser.add_argument("package", help="mod folder or ZIP archive to check")
    package_parser.add_argument("--sha256", default=None, help="expected SHA-256 of the ZIP")
    package_parser.add_argument("--json", action="store_true", help="machine readable output")
    package_parser.set_defaults(func=_cmd_validate_package)

    pack_parser = subparsers.add_parser("pack", help="build the release ZIP and print its SHA-256")
    pack_parser.add_argument("directory", help="mod folder to package")
    pack_parser.add_argument("--out", default=None, help="output ZIP path")
    pack_parser.add_argument("--json", action="store_true", help="machine readable output")
    pack_parser.set_defaults(func=_cmd_pack)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


__all__ = ["build_parser", "main"]
