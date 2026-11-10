# Changelog

All notable changes to Workmods. The format follows Keep a Changelog and the
project uses semantic versioning.

## [1.0a] — 2026-11-10

First public alpha. Feature-freeze release for the v1.0 line: the client, the
registry workflow and the Unity SDK share one mod format, and the documented
limitations in the README are the accepted boundaries for this alpha.

### Added

- **Game profiles.** One client manages mods for any number of Unity games; each
  profile has an id, display name and install directory, and mods carry a
  `game_id`.
- **Per-game filtering** in the catalog and installed tabs, plus a game selector
  in the mod editor and the settings tab.
- **Unity SDK** (`unity-sdk/WorkmodsSDK.cs`): folder scanning, per-game filtering,
  AssetBundle loading with dependency bundles, Mono-only DLL loading, logging to
  the console and to `workmods.log`, and a drop-in `WorkmodsModLoader` component.
- **Working installs.** The catalog now actually downloads a release, verifies its
  SHA-256, extracts it safely and writes a manifest (previously the install button
  emitted an unconnected signal).
- **Publish pipeline** as a testable service: ZIP → hash → repository files →
  release asset → registry dispatch, with progress reporting.
- **Registry schema v2** (`schema_version`, `games`, `game_id`, `entry_asset`,
  `tags`, timestamps) with transparent migration of v1 documents.
- **Modular package layout**: `config`, `models`, `storage`, `github_api`,
  `publisher`, `registry`, `oauth`, `net`, `ui/`.
- **Localization** files for English and Russian.
- **Tests**: 34 pytest cases covering registry, config migration, storage safety,
  publishing and the registry bot; CI workflow.
- **Documentation**: README, architecture, registry schema, publishing guide,
  Unity integration guide, security notes.

### Changed

- `devers_workmods.py` is now a thin compatibility launcher; `main.py` is the
  entry point.
- Registry updates are applied by `.github/scripts/update_registry.py` instead of
  an inline Python string in the workflow; the shared secret is stripped before
  `registry.json` is written.
- Icons and banners are referenced from the repository's actual default branch.
- Releases are created idempotently and re-publishing a version replaces its
  asset.

### Fixed

- Install button did nothing (no handler for the download signal).
- Registry payloads leaked `BOT_SECRET` into the public `registry.json`.
- A folder could be deleted outside the install directory; ZIP extraction allowed
  path traversal.
- Game filter defaulted to the active game and hid every mod on first launch.

### Known limitations

- Publishing requires write access to the registry repository (see
  `docs/SECURITY.md`); open publishing needs a proxy or PR flow.
- No automatic update checks, dependency resolution or mod signing.
- The Unity SDK does not support WebGL.
