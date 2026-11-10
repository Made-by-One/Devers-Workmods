# Unity integration guide

`unity-sdk/WorkmodsSDK.cs` is a single, dependency-free C# file. It scans a mods
folder, exposes installed mods and loads their assets.

## 1. Install the SDK

Copy `WorkmodsSDK.cs` into your project, e.g. `Assets/Workmods/WorkmodsSDK.cs`.
No package manager, no asmdef required (if you use assembly definitions, add the
file to a runtime assembly that references `UnityEngine`).

The SDK targets C# 7.3 and Unity 2019.4+. It compiles for Mono and IL2CPP; only
DLL loading is Mono-only.

## 2. Where mods live

Workmods installs each mod into its own folder:

```
<modsRoot>/
├── a1b2c3d4/
│   ├── workmod.json            (optional manifest, may be .devers_meta.json)
│   ├── neon-ui.bundle
│   └── bundles/shared.bundle
└── e5f6a7b8/
    ├── workmod.json
    └── weapons.bundle
```

The SDK defaults to `Application.persistentDataPath/Workmods`. **The client's
default install folder is `~/DeversMods/<game_id>`**, so pick one of these:

- in Workmods: **Settings → Game Profiles** → set this game's install directory to
  the folder your game scans (recommended if the game already expects
  `persistentDataPath/Workmods`), or
- in your game: `WorkmodsSDK.Initialize(modsRoot: "/path/to/DeversMods/my-game")`,
  or
- expose a folder picker in your game's settings and pass the result.

`WorkmodsSDK.DefaultModsRoot` returns the default; `WorkmodsSDK.ModsRoot` what is
actually scanned.

## 3. Mod manifest

`workmod.json` is optional. Missing fields fall back to the folder name and to
file-extension discovery.

| Field | Purpose |
|---|---|
| `id` | Mod id (defaults to folder name). |
| `game_id` | Target game; if set, `Initialize(gameId: …)` filters mismatches. |
| `name`, `version`, `author`, `description` | Display metadata. |
| `entry_asset` | Convenience default asset name for your UI. |
| `bundles` | Explicit bundle filenames (relative paths). Recommended when names are ambiguous. |
| `tags` | Free-form strings, ignored by the SDK. |

The Workmods client writes `.devers_meta.json` at install time with the same keys
plus `repo`, `sha256`, `download_url`; `JsonUtility` ignores unknown fields, so
both files work.

## 4. Choose a content format

### AssetBundles (recommended)

Works with both scripting backends and every Unity platform (except WebGL, see
below). The modder builds a bundle; the SDK loads it with
`AssetBundle.LoadFromFile` (falling back to `LoadFromMemory`).

Modder-side editor script:

```csharp
// Assets/Editor/WorkmodsBundleBuilder.cs
using UnityEditor;
using UnityEngine;

public static class WorkmodsBundleBuilder
{
    [MenuItem("Workmods/Build Mod Bundle")]
    public static void Build()
    {
        var builds = new[]
        {
            new AssetBundleBuild
            {
                assetBundleName = "neon-ui.bundle",
                assetNames = new[] { "Assets/ModContent/NeonHud.prefab" }
            }
        };
        BuildPipeline.BuildAssetBundles(
            "Build/Mod", builds,
            BuildAssetBundleOptions.ChunkBasedCompression, // LZ4: streamable, Android-friendly
            BuildTarget.StandaloneWindows64);
    }
}
```

Put the produced bundles (plus `workmod.json`) into the mod folder and publish.
Use `ChunkBasedCompression` — LZMA bundles must be fully decompressed and are a
common source of Android failures.

### Addressables

Also supported, because Addressables builds AssetBundles. Ship the **built bundle
files** from `Library/com.unity.addressables/aa/<platform>/` in the mod folder and
load assets with `LoadAssetBundle`. If the mod relies on an Addressables catalog
(`catalog.json`, `settings.json`), your game must add its own
`IResourceLocator` for that catalog — the SDK deliberately does not parse
catalogs, since their format is Addressables-version specific.

If your project is Addressables-only and you do not want two code paths, expose a
loader interface in your game and implement it twice (Addressables for built-in
content, `WorkmodsSDK` for mods).

### DLL assemblies

Only on the **Mono** scripting backend; IL2CPP cannot JIT new code. Prefer DLL
mods for logic-only content, and treat them as fully trusted code.

```csharp
if (WorkmodsSDK.TryLoadAssembly("a1b2c3d4", out var assembly))
{
    var type = assembly.GetType("NeonUi.ModEntryPoint");
    type?.GetMethod("Initialize")?.Invoke(null, null);
}
```

Ship the DLL in the mod folder together with its dependencies. If the DLL
references assemblies your game already ships, version mismatches throw
`FileLoadException` — log and disable the mod instead of crashing.

## 5. Initialization

```csharp
using Workmods;
using UnityEngine;

public class Mods : MonoBehaviour
{
    private void Awake()
    {
        WorkmodsSDK.Initialize(
            modsRoot: null,            // null → Application.persistentDataPath/Workmods
            gameId: "space-rangers",   // reject mods published for other games
            verboseLogging: true,
            writeLogToFile: true);     // <modsRoot>/workmods.log
    }
}
```

Or use the **Workmods Mod Loader** component (Add Component → Workmods → Workmods
Mod Loader): set folder override, game id, logging, and it initializes on `Awake`.

Calling `GetInstalledMods()` before `Initialize()` lazily initializes with
defaults, so ordering bugs degrade to sane behaviour.

## 6. API reference

| Member | Description |
|---|---|
| `Initialize(modsRoot, gameId, verboseLogging, writeLogToFile)` | Scan the folder. Safe to call repeatedly. |
| `Rescan()` | Re-read the folder after an in-game install. |
| `GetInstalledMods()` | `IReadOnlyList<WorkmodsInstalledMod>` filtered by `gameId`. |
| `GetInstalledMods(gameId)` | Only mods declaring that game id (multi-game launchers). |
| `GetInstalledMod(id)` / `IsInstalled(id)` | Lookup helpers (case-insensitive). |
| `LoadAssetBundle(modId, assetName)` | `UnityEngine.Object` or `null`; logs the reason. |
| `LoadAsset<T>(modId, assetName)` | Typed variant, e.g. `<GameObject>`. |
| `GetAssetBundle(modId)` | First cached `AssetBundle` of the mod. |
| `LoadBundles(mod)` | Load/cache every bundle of a mod (handles dependencies). |
| `TryLoadAssembly(id, out Assembly)` | Mono only; returns `false` on IL2CPP with an error log. |
| `GetAssembly(id)` | Assembly cached by the previous call. |
| `UnloadAssetBundle(id)` / `UnloadAll()` | Unload bundles; destroy instances first. |
| `WorkmodsLog.OnLog`, `GetRecentLines()` | Hook into your own logger / show an in-game log. |

`WorkmodsInstalledMod`: `ModId`, `GameId`, `Name`, `Version`, `Author`,
`Description`, `EntryAsset`, `DirectoryPath`, `Files`, `GetFile(path)`,
`GetBundlePaths()`, `GetAssemblyPaths()`.

Everything is main-thread; do not call `LoadAssetBundle` from worker threads.

### Example: mod list UI

```csharp
foreach (var mod in WorkmodsSDK.GetInstalledMods())
{
    var row = Instantiate(rowPrefab, listRoot);
    row.GetComponentInChildren<Text>().text = $"{mod.Name} v{mod.Version}";
    row.GetComponent<Button>().onClick.AddListener(() =>
    {
        var assetName = string.IsNullOrEmpty(mod.EntryAsset) ? mod.Name : mod.EntryAsset;
        var prefab = WorkmodsSDK.LoadAssetBundle(mod.ModId, assetName) as GameObject;
        if (prefab != null) Instantiate(prefab);
    });
}
```

### Example: apply a mod's settings

Mods usually ship a `ScriptableObject` with configuration. Load it by type:

```csharp
var config = WorkmodsSDK.LoadAsset<MyModConfig>("a1b2c3d4", "NeonConfig");
if (config != null) Apply(config);
```

`LoadAsset<T>` searches every bundle of the mod until it finds the name, then
casts. Keep the bundle loaded while objects from it are alive.

### Example: unload cleanly

```csharp
Destroy(modRootInstance);                 // destroy instantiated objects first
WorkmodsSDK.UnloadAssetBundle("a1b2c3d4"); // then release the bundles
```

## 7. Logging

All SDK messages go through `WorkmodsLog`:

- `Debug.Log` / `LogWarning` / `LogError` with the `[Workmods]` prefix;
- `WorkmodsLog.OnLog += line => myLogger.Write(line);`
- `WorkmodsLog.GetRecentLines()` — last 200 lines, for an in-game diagnostics tab;
- `writeLogToFile: true` appends to `<modsRoot>/workmods.log`.

Each discovered mod, loaded bundle, loaded asset and every failure is logged with
its reason (missing bundle, wrong asset type, broken manifest, etc.). Loading
never throws into gameplay code.

## 8. Platform notes

| Platform | Notes |
|---|---|
| Windows / macOS / Linux standalone | Full support. |
| Android | Use LZ4 (`ChunkBasedCompression`) bundles. `LoadFromFile` streams them; LZMA falls back to a full memory load. Scoped storage: mods live in `persistentDataPath`, no extra permission needed. |
| iOS | Full support; mods must be installed into `persistentDataPath` by your own UI (App Store rules may restrict downloaded executable content — AssetBundles only). |
| Consoles | Possible but platform-specific packaging/signing applies; test early. |
| IL2CPP | AssetBundles work; DLL loading does not (logged as an error). |
| **WebGL** | **Not supported by this SDK.** WebGL has no synchronous file access and requires `UnityWebRequestAssetBundle`. Use AssetBundles and write an async loader if you target WebGL. |

## 9. Security

Mods are executable content. Workmods verifies SHA-256 on install, but that only
proves the file matches the registry, not that it is safe. Recommendations:

- Prefer AssetBundles (data) over DLLs (code).
- Show players what they install and where it came from (`repo`, `author`).
- Never grant mods network or file access beyond what your game already has.
- Validate loaded objects (expected types, value ranges) as you would with any
  user content.

## 10. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `No mods folder at …` | Nothing installed yet, or the game's folder differs from Workmods' install dir. Set the game profile path or pass `modsRoot`. |
| Mod discovered but skipped | `game_id` mismatch with `Initialize(gameId: …)`. |
| `no AssetBundle found` | Folder has no `.bundle`/`.unity3d`/`.bytes`, and `workmod.json` does not list `bundles`. |
| `Asset 'X' not found` | Bundle was built for another platform, or the asset name is wrong. Rebuild for the target platform. |
| Asset loads but prefab is pink | Shaders/textures are in a different bundle; include dependencies in the same mod and load all bundles (`LoadBundles`). |
| Bundle loads, dependencies missing | Ship dependency bundles inside the mod; the SDK loads all bundles of a mod before resolving assets. |
| Android `The archive is corrupted` | Rebuild with LZ4 compression. |
| IL2CPP `TryLoadAssembly` returns false | Expected: IL2CPP cannot load assemblies at runtime. |
| Duplicate asset names | `LoadAssetBundle` searches bundles in order; use explicit `bundles` in the manifest and unique asset names. |
