# ✦ Devers Workmods

**An independent, game-agnostic mod distribution platform — a Steam Workshop you own.**

**Status:** `v1.0a` — first public alpha. Read [Known limitations](#known-limitations-before-public-launch)
before relying on it for a real game.

Workmods is three things that share one format:

1. **A desktop client** (Python + PyQt6) for players to browse, install, update and remove mods per game.
2. **A public registry** (`registry.json`) updated by GitHub Actions — no central server, no vendor lock-in.
3. **A Unity SDK** (`unity-sdk/WorkmodsSDK.cs`) that any game developer drops into their project to discover and load those mods.

Mods live in the modder's own GitHub repository and are distributed through GitHub Releases. Workmods only stores metadata.

```
┌──────────────────┐    publish (ZIP + release)    ┌─────────────────────────┐
│  Workmods client │ ────────────────────────────► │ modder's GitHub repo    │
│  (PyQt6)         │                               │ + GitHub Release        │
│                  │ ── pull request ────────────► │  registry repo          │
└────────┬─────────┘                               │  submissions/ + Action  │
         │ reads registry.json                      └───────────┬─────────────┘
         │                                                       │ commits
         ▼                                                       ▼
   catalog / install                                  registry.json (raw.githubusercontent)
         │
         │ writes <install_dir>/<modId>/
         ▼
┌──────────────────┐
│  Unity game      │  WorkmodsSDK.Initialize(gameId: "my-game")
│  + WorkmodsSDK   │  WorkmodsSDK.LoadAssetBundle("a1b2c3d4", "MyPrefab")
└──────────────────┘
```

**Кратко по-русски:** Workmods — независимый аналог Steam Workshop для любых Unity-игр. Клиент на PyQt6 публикует моды в GitHub Releases и предлагает запись в общем реестре через pull request; `registry.json` пересобирает GitHub Action после merge. Игра подключает один C#-файл `WorkmodsSDK.cs`, сканирует папку модов и загружает AssetBundle'ы. У каждого мода есть `game_id`, поэтому один клиент обслуживает несколько игр. Подробности — в [docs/](docs/).

---

## Repository layout

```
.
├── main.py                     # entry point (python main.py)
├── devers_workmods.py          # legacy launcher kept for old shortcuts
├── workmods/                   # Python client, layered
│   ├── config.py               # settings, paths, game profiles, credentials
│   ├── models.py               # Game, Mod, InstalledMod (no Qt, no network)
│   ├── registry.py             # registry parsing, migration, filtering
│   ├── storage.py              # ZIP packaging, SHA-256, safe install, scanning
│   ├── github_api.py           # thin GitHub REST client
│   ├── publisher.py            # zip → repo → release → submission pull request
│   ├── oauth.py                # GitHub OAuth callback server
│   ├── net.py                  # Qt network adapter for the registry
│   ├── i18n.py                 # localization
│   ├── utils.py                # OS helpers
│   └── ui/                     # PyQt6 widgets only
│       ├── main_window.py      ├── catalog_tab.py
│       ├── installed_tab.py    ├── author_tab.py
│       ├── settings_tab.py     ├── editor_dialog.py
│       ├── workers.py          ├── widgets.py
│       └── theme.py
├── unity-sdk/
│   ├── WorkmodsSDK.cs          # drop-in SDK, single file
│   └── README.md
├── data/                       # icons + localization (en, ru)
├── docs/                       # architecture, schema, guides
├── submissions/                # one JSON file per mod (source of truth)
├── tests/                      # pytest suite (47 tests)
├── registry.json               # generated shared catalog
└── .github/
    ├── scripts/update_registry.py
    └── workflows/update_registry.yml
```

Why the split: only `workmods/ui/` imports Qt, and only `github_api`/`storage` touch the network and disk. That makes the interesting logic testable headlessly and lets a CLI or server job reuse it later. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## For players

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

1. Open **Settings → Game Profiles → Add Game** and set the game id, display name and install folder (for example `~/DeversMods/space-rangers`).
2. Pick a game in the **Catalog** filter — the list only shows mods whose `game_id` matches.
3. **Install**. The client downloads the release ZIP, verifies its SHA-256 against the registry and extracts it to `<install folder>/<modId>/`.
4. Point the game at that folder (the Unity SDK does this by default: `Application.persistentDataPath/Workmods`).

Installed mods are listed per game; **Delete** removes the folder, nothing else. To update, install again — the old folder is replaced atomically.

---

## For modders

You need a GitHub account. Workmods creates and fills a repository for you — you never touch git.

1. **Prepare the mod folder.** Whatever the game's SDK expects: `.bundle` files (recommended), Addressables output, or DLLs. Keep `workmod.json` next to them (optional but recommended):

   ```json
   {
     "id": "a1b2c3d4",
     "game_id": "space-rangers",
     "name": "Neon UI",
     "version": "1.2.0",
     "author": "your-handle",
     "description": "Neon HUD replacement.",
     "entry_asset": "NeonHud",
     "bundles": ["neon-ui.bundle"],
     "tags": ["ui", "hud"]
   }
   ```

2. **Log in** in the **Author Studio** tab (GitHub OAuth, `repo` scope).
3. **New Repo** creates a public repository; pick it in the editor.
4. **Create**, fill in name, version, description, target game, optional icon/banner, select the files folder.
5. **Publish & Request Addition.** The client:
   - packages the folder into a ZIP and computes SHA-256,
   - uploads files + release asset to your repo (`v<version>` tag),
   - opens a pull request adding `submissions/<game_id>/<mod_id>.json` to the registry repository.

No write access to the registry is needed — the pull request comes from your fork.
CI validates the submission file, a maintainer reviews it, and the merge triggers
the **Rebuild Mod Registry** Action. Players see the mod after the next catalog
refresh.

**Updating:** bump the version, publish again — the new pull request replaces the same `modId` submission file, so players see one entry. **Unpublishing** opens a pull request that deletes the submission file; your repository and releases stay online.

Full walkthrough, troubleshooting and versioning rules: [docs/PUBLISHING.md](docs/PUBLISHING.md).

---

## For game developers

Nothing about Workmods is specific to one game: a mod declares a `game_id`, and your game initializes the SDK with that same id.

**1. Copy** [`unity-sdk/WorkmodsSDK.cs`](unity-sdk/WorkmodsSDK.cs) into `Assets/Workmods/`. No packages, no dependencies.

**2. Choose the content format** (details in [docs/UNITY_INTEGRATION.md](docs/UNITY_INTEGRATION.md)):

| Format | Works on | Best for |
|---|---|---|
| **AssetBundles** (recommended) | Mono + IL2CPP, all platforms | prefabs, textures, audio, ScriptableObjects |
| **Addressables** | Mono + IL2CPP | projects already using Addressables; ship the built bundles and load them through the SDK |
| **DLL assembly** | Mono only (IL2CPP cannot load code at runtime) | deep gameplay mods |

**3. Initialize and load:**

```csharp
using Workmods;
using UnityEngine;

public class ModBootstrap : MonoBehaviour
{
    void Start()
    {
        // Defaults to Application.persistentDataPath/Workmods.
        // Mods published for another game_id are ignored.
        WorkmodsSDK.Initialize(gameId: "space-rangers", writeLogToFile: true);

        foreach (var mod in WorkmodsSDK.GetInstalledMods())
            Debug.Log($"{mod.Name} {mod.Version} installed at {mod.DirectoryPath}");

        var prefab = WorkmodsSDK.LoadAssetBundle("a1b2c3d4", "NeonHud") as GameObject;
        if (prefab != null)
            Instantiate(prefab);
    }
}
```

Or add the **Workmods Mod Loader** component to a bootstrap object and set the folder/game id in the Inspector.

API: `GetInstalledMods()`, `GetInstalledMod(id)`, `IsInstalled(id)`, `LoadAssetBundle(modId, assetName)`, `LoadAsset<T>(...)`, `GetAssetBundle(id)`, `TryLoadAssembly(id, out assembly)`, `UnloadAssetBundle(id)`, `UnloadAll()`, `Rescan()`.

The SDK logs every discovered mod, loaded bundle, asset and failure (`WorkmodsLog.OnLog`, Unity console, optional `workmods.log`). It never throws into your game loop.

---

## Registry

`registry.json` is generated only by the Action — never edit it manually. Schema v2:

```json
{
  "schema_version": 2,
  "updated_at": "2026-11-09T12:00:00+00:00",
  "games": [{ "id": "space-rangers", "name": "Space Rangers", "sdk": "unity" }],
  "mods": [
    {
      "id": "a1b2c3d4",
      "game_id": "space-rangers",
      "name": "Neon UI",
      "version": "1.2.0",
      "author": "your-handle",
      "description": "Neon HUD replacement.",
      "repo": "you/workmods-neon-ui",
      "download_url": "https://github.com/you/workmods-neon-ui/releases/download/v1.2.0/a1b2c3d4.zip",
      "sha256": "…",
      "entry_asset": "NeonHud",
      "tags": ["ui"],
      "updated_at": "2026-11-09T12:00:00+00:00"
    }
  ]
}
```

Version 1 documents (`{"mods": [...]}` without `game_id`) are migrated on read: those mods belong to the `default` profile and remain visible under **All games**. Full field reference, submission format and review flow: [docs/REGISTRY_SCHEMA.md](docs/REGISTRY_SCHEMA.md).

---

## Development

```bash
pip install -r requirements-dev.txt
pytest              # 47 tests, no display required
ruff check workmods tests
```

The test suite covers registry migration/filtering, config migration and game profiles, ZIP packaging, path-traversal rejection, atomic installs, publish orchestration against a fake GitHub client, and the submission validator/registry rebuild bot.

Build the Unity SDK check (optional): compile `unity-sdk/WorkmodsSDK.cs` together with Unity API stubs; it has no Unity-only syntax beyond the documented APIs. It was verified with C# 7.3 in both Mono and `ENABLE_IL2CPP` configurations.

## Known limitations (before public launch)

These are deliberate v1.0 boundaries, not bugs to discover later:

1. **Publishing is PR-based and manual.** Anybody can open a submission pull
   request without registry access, but a maintainer still has to review and
   merge it; there is no automated malware scanning or trust score yet.
2. **No automatic update notifications.** Installing again replaces the folder;
   there is no "update available" diff, dependency graph or load order between
   mods.
3. **Large files:** mod files are uploaded through the GitHub Contents API and
   are unsuitable above ~50–100 MB; use the release asset / manual PR path for
   huge content.
4. **WebGL is not supported** by the Unity SDK (no synchronous file access);
   AssetBundles plus an async loader are required there.
5. **No mod signing.** SHA-256 gives integrity, not trust.

## License

MIT — see [LICENSE](LICENSE).
