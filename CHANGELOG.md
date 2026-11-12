# Changelog

All notable changes to Workmods. The format follows Keep a Changelog and the
project uses semantic versioning.

## [1.1c] — 2026-11-12

Third public beta. Connects the new profile and update features to the desktop
GUI, verifies release checksums/signatures and ships signed release metadata.

### Added

- **Settings → Application Updates**: check GitHub Releases, open the download
  page, download and install on packaged builds, and roll back the last update.
- **Installed → Mod Profile**: save/apply enabled/disabled sets, edit settings
  presets, and export/import profiles as JSON.
- On-disk enable/disable via the hidden `.workmods-disabled` folder; the SDK and
  scanner ignore it automatically.
- `SHA256SUMS` on every release and optional `SHA256SUMS.sig` from the
  `RELEASE_SIGNING_KEY` secret; the updater verifies both when configured.
- `docs/RELEASE_SIGNING.md` with key generation, secret setup and manual checks.
- Compatibility fields in the publishing guide and localized README updates.

### Changed

- Version bumped to `1.1c`; download links and release notes updated.
- `requirements.txt` now includes `cryptography` for RSA/ECDSA verification.
- Updater extracts `Workmods`/`Workmods.exe` from ZIP/TAR release archives before
  replacing the executable.
- 84 Python tests total.

## [1.1b] — 2026-11-12

Second public beta. Adds mod profiles, client update infrastructure and package
compatibility checks on top of the 1.0b authoring tools.

### Added

- **Mod profiles** (`workmods/profiles.py`): named enabled/disabled mod sets,
  reusable settings presets, JSON export and import, plus `profile` CLI commands.
- **Client updater** (`workmods/updater.py`): GitHub release checks, SHA-256 and
  optional detached-signature verification, atomic executable replacement,
  backup creation and rollback when an update cannot be applied.
- **Package compatibility validation**: `validate` and `validate-package` accept
  target engine, Unity version, platform, client and SDK versions and compare
  them with the manifest's compatibility fields.
- `update` CLI commands for checking, applying, finalizing and rolling back an
  update.
- 15 new tests for profiles, updater verification/rollback and compatibility
  checks; 81 Python tests total.

### Changed

- Version bumped to `1.1b`; README download links point at the new release.
- The sample mod declares its Unity engine, version and supported platforms so
  compatibility checks have concrete metadata to verify.

## [1.0b] — 2026-11-12

Public beta. The client keeps the 1.0 format and workflow but gets a full design
pass plus the authoring tools that were missing from the alpha.

### Added

- **Six-language interface** (`en`, `ru`, `de`, `es`, `fr`, `zh`) with native
  language names, system-language detection on first launch and instant switching
  without restarting the client.
- **Mod author CLI**: `python -m workmods init`, `validate`, `validate-package`
  and `pack`; the editor auto-fills metadata from the generated `workmod.json`.
- **Package validation** for folders and final ZIPs: SHA-256 verification,
  unsafe-entry rejection, archive size limits and the same manifest checks as
  the editor.
- **Unity SDK example** (`unity-sdk/examples/BasicModLoader/`) and a sample mod
  package for local loader tests.
- **Unity SDK smoke suite** with minimal Unity stubs and a separate CI job; it
  covers discovery, filtering, manifest fallback, bundle/DLL detection, rescan
  and unloading.
- **Redesigned beta interface**: richer catalog detail with a metadata strip,
  master-detail installed mods with local actions, author account and draft/published
  stats, a two-column settings layout and a sectioned two-column mod editor.
- Submission validator: path/id/game consistency, SHA-256 format, GitHub release
  URLs, tags, unknown-field rejection and duplicate-id detection.
- Removal through a pull request that deletes the submission file.
- `submissions/README.md`; updated schema, publishing and architecture docs;
  13 new tests.
- 12 tests for localization and the author CLI; 7 package-validation tests;
  66 Python tests total, plus the C# SDK suite.
- **Localized README** in English, Russian, German, Spanish, French and Chinese.
- **Standalone builds** for Windows x64, Linux x86_64 and macOS through
  `.github/workflows/release.yml`, published as the first `v1.0b` release.
- **Optional code signing** for Windows and macOS release binaries, including
  macOS notarization and stapling when the required secrets are configured.

### Changed

- Version bumped to `1.0b`; the header now shows the beta channel.
- Refined dark palette, typography, tabs, cards, inputs and list selection states.
- **Publishing is now a pull request**, not a `repository_dispatch`. The registry
  is generated from `submissions/<game_id>/<mod_id>.json`; the client forks the
  registry when needed, opens a pull request and shows its URL, so no write access
  to the registry and no shared secret are required to publish a mod.
- Registry CI is split into **Validate Submission** (pull requests, read-only) and
  **Rebuild Mod Registry** (push to `main`, rebuilds `registry.json`).
- `BOT_SECRET` / `WORKMODS_BOT_SECRET` were removed from the client and the bot.
- Removed the legacy `devers_workmods.py` launcher, unused icon assets and the
  personal design-preview site from version control.
- Fixed a stale reference to the removed `docs/SECURITY.md` in the OAuth module.

### Fixed

- `ruff` is now listed in `requirements-dev.txt`, so the CI lint step can run.

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
  Unity integration guide.

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

- Publishing required write access to the registry repository; open publishing
  needed a proxy or PR flow.
- No automatic update checks, dependency resolution or mod signing.
- The Unity SDK does not support WebGL.
