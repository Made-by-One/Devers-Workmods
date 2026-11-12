# Architecture

Workmods v1.1 is a small platform with three artifacts that share one contract:
the **registry entry**. Everything below follows from that contract.

## Layers

```
                    ┌───────────────────────────────┐
  PyQt6 only        │              ui/              │
  (no I/O rules)    │ tabs · dialogs · workers      │
                    └──────────────┬────────────────┘
                                   │ uses
                    ┌──────────────▼────────────────┐
  orchestration     │  publisher.py · oauth.py      │
                    └───────┬───────────────┬───────┘
                            │               │
             ┌──────────────▼───┐   ┌───────▼────────────┐
  adapters   │  github_api.py   │   │    storage.py      │
             │  requests only   │   │  pathlib + zipfile │
             └──────────────────┘   └────────────────────┘
                            │               │
                    ┌───────▼───────────────▼───────┐
  core       │ config.py · models.py · registry.py │
             │ i18n.py · utils.py                  │
             └─────────────────────────────────────┘
```

Rules that keep it maintainable:

- **Core has no dependencies** beyond the standard library. `Game`, `Mod` and
  `Registry` can be imported in a test, a CLI or a future server without Qt or
  `requests`.
- **`github_api.py` is the only place that knows GitHub URLs.** Error handling is
  translated to `GitHubError(status, payload)`.
- **`storage.py` is the only place that touches mod files.** Every archive goes
  through `safe_extract` (zip-slip rejection) and `install_package` (staging +
  rename).
- **The UI never builds URLs, zips files or parses JSON.** It calls a worker or a
  service and renders the result.
- **`publisher.py` owns the publish sequence**, so the same flow can later be
  driven by a CLI without a display.
- **`profiles.py` owns enabled/disabled sets and settings presets.** The UI only
  collects the current state and calls the store; the store has no Qt imports.
- **`updater.py` owns release checks, verification and replacement.** Downloads,
  checksum/signature verification, backup creation and rollback are testable
  without opening a window.

## Data flow: publishing a mod

```
AuthorStudioTab ──ModEditorDialog──► PublishRequest
                                         │
                              PublishWorker (QThread)
                                         │
                    ModPublisher.publish(request)
       ┌─────────────────────────────────┼──────────────────────────────┐
       ▼                                 ▼                              ▼
 storage.package_mod              storage.sha256_file          GitHubClient
 (ZIP without metadata)                                         ├ put_file ×N
                                                                ├ ensure_release
                                                                ├ upload_release_asset
                                                                ├ ensure_fork (if needed)
                                                                ├ ensure_branch
                                                                ├ put_file(submissions/…)
                                                                └ create_pull
                                                                        │
                                             validate_submission.yml (on PR)
                                                                        │
                                             maintainer review + merge
                                                                        │
                                             rebuild_registry.yml (on push)
                                                                        │
                                                              registry.json commit
```

`PublishResult` carries the submission payload, the SHA-256, the release URL and
the pull request URL. Nothing secret is exchanged: the submission file is plain
registry metadata, and the pull request itself is the access request.

## Data flow: installing a mod

```
CatalogTab ──InstallWorker──► storage.download_file  (any HTTP URL)
                                  │
                                  ├ sha256 check (registry value, optional)
                                  ├ storage.install_package  → staging dir
                                  │     ├ safe_extract
                                  │     ├ write .devers_meta.json
                                  │     └ rename over <install_dir>/<modId>
                                  ▼
                          install_finished → InstalledTab.scan()
```

Installs are atomic: an interrupted download or extraction never leaves a
half-written mod visible to the game. The old folder is only replaced after the
new one is complete.

## Enabled and disabled mods

A disabled mod is moved from `<install_dir>/<modId>` to
`<install_dir>/.workmods-disabled/<modId>`. The Unity SDK and the installed-mod
scanner skip hidden directories, so disabling is immediate and does not edit any
manifest. `scan_disabled_mods` reads the hidden folder for the client UI, and
`apply_mod_state` applies a profile’s enabled/disabled lists by moving folders.

Packaging explicitly skips `.workmods-disabled`, so disabled mods never leak into
a published ZIP.

## Mod profiles

`workmods/profiles.py` stores named `ModProfile` records:

- `enabled` and `disabled` mod ids for one game;
- the current `settings` object;
- named `presets` and the active preset;
- timestamps and a portable JSON representation.

Profiles live in `~/.devers_workmods/profiles.json`. Export writes one profile;
import validates the JSON and can replace an existing name. The Installed tab
saves the current disk state, applies a profile, edits a settings preset and
exports/imports the selected profile.

## Client updates

`ClientUpdater` uses the GitHub Releases API, picks the asset for the running
platform, downloads it, verifies `SHA256SUMS` and an optional `SHA256SUMS.sig`,
then extracts the executable from the archive. Before replacement it copies the
old executable to `~/.devers_workmods/updates/` and records the pending update in
`update_state.json`; any failure restores the backup. The same state file powers
the **Rollback Last Update** action in Settings.

## Game profiles

A `Game` is `{id, name, install_dir, sdk}`. `WorkmodsConfig` holds a list of
them plus `active_game_id`. Consequences:

- one client serves any number of games, each with its own mod directory;
- `registry.json` needs no paths — only `game_id` — so it stays portable;
- a mod draft can move between profiles; the editor relocates the folder instead
  of duplicating it.

Install directories are resolved at runtime (`install_dir_for`) with a default
`~/DeversMods/<game_id>` when a profile has none. Pre-1.0 configs (flat
`install_dir`) migrate into the `default` profile on read.

## Registry contract

`registry.py` accepts both schema v1 and v2, normalises mods into `Mod` objects,
and exposes a single filter function:

```python
registry.filter(game_id="space-rangers", query="neon")
```

`mod_matches` is the one source of truth used by the catalog, the installed tab
and (through `merge_games`) the game filter combo boxes. `include_unassigned=True`
keeps legacy `default` mods visible when a game is selected — used only where a
single-game registry predates `game_id`.

## Threading model

| Work | Where |
|---|---|
| HTTP downloads, GitHub calls, ZIP/IO | `QThread` workers (`ui/workers.py`) |
| Registry fetch | `QNetworkAccessManager` (`net.py`) |
| Preview images | `ImageDownloader` (`ui/widgets.py`) |
| UI | main thread only |

Workers are kept referenced until `QThread.finished` fires, then `deleteLater()`.
No UI code touches files or the network directly.

## Extension points

- **Another game:** no code change. Add a profile, set the same `game_id` when
  publishing, initialize the SDK with that id.
- **Another engine:** write an SDK that reads the same `<modsRoot>/<modId>/`
  layout and `workmod.json`. The registry contract is engine-independent; `sdk`
  is reserved for that (`"unity"`, `"godot"`, …).
- **Another hosting backend:** implement the small surface used by
  `ModPublisher` (`put_file`, `ensure_release`, `upload_release_asset`,
  `ensure_fork`, `ensure_branch`, `create_pull`) and swap it in.
- **Headless publishing:** reuse `ModPublisher` + `PublishRequest` from a script.

## Tests

`tests/` covers the contract rather than the widgets:

| File | What it protects |
|---|---|
| `test_registry.py` | v1 migration, game/search filtering, legacy visibility |
| `test_config.py` | legacy config migration, per-game dirs, profile lifecycle |
| `test_storage.py` | packaging filters, zip-slip, wrapper unwrap, atomic install, enable/disable, deletion guards |
| `test_publisher.py` | release + submission PR sequence, fork vs maintainer, default branch URLs, removal PRs |
| `test_registry_workflow.py` | submission validation (paths, ids, URLs, hashes) and `registry.json` rebuild |
| `test_profiles.py` | enabled/disabled sets, presets, export/import and overwrite rules |
| `test_updater.py` | version comparison, SHA-256, RSA signatures, archive extraction, apply/rollback |
| `test_compatibility.py` | engine, Unity, platform, client and SDK compatibility checks |

The UI was additionally smoke-tested offscreen (window construction, game
filtering, install from a local HTTP server, draft relocation, dialogs).
