# Workmods Unity SDK

`WorkmodsSDK.cs` is a single-file, dependency-free mod loader for Unity games.
Copy it into `Assets/Workmods/` and you are done — no package, no asmdef needed.

```csharp
using Workmods;
using UnityEngine;

public class Mods : MonoBehaviour
{
    void Start()
    {
        WorkmodsSDK.Initialize(gameId: "my-game");     // persistentDataPath/Workmods
        foreach (var mod in WorkmodsSDK.GetInstalledMods())
            Debug.Log($"{mod.Name} v{mod.Version}");

        var prefab = WorkmodsSDK.LoadAssetBundle("a1b2c3d4", "MyPrefab") as GameObject;
        if (prefab != null) Instantiate(prefab);
    }
}
```

- Scans `<modsRoot>/<modId>/`, reads `workmod.json` or `.devers_meta.json`, discovers bundles.
- `GetInstalledMods()`, `GetInstalledMod(id)`, `LoadAssetBundle(modId, assetName)`,
  `LoadAsset<T>(...)`, `TryLoadAssembly(...)`, `UnloadAll()`, `Rescan()`.
- Filters mods by `game_id` when you pass your game's id.
- Logs every mod/bundle/asset and every failure (`WorkmodsLog`, optional `workmods.log`), never throws into gameplay code.
- Supports AssetBundles, Addressables-built bundles (Mono + IL2CPP) and DLL assemblies (Mono only).

Requirements: Unity 2019.4+, C# 7.3. WebGL is not supported by this synchronous
SDK (use an async `UnityWebRequestAssetBundle` loader there).

The full integration guide — folder paths, manifest fields, bundle building,
platform caveats and troubleshooting — is in
[docs/UNITY_INTEGRATION.md](../docs/UNITY_INTEGRATION.md).

## Example project

`examples/BasicModLoader/` contains a bootstrap component you can copy into a
Unity scene. `examples/sample-mod/` is a valid package for local loader tests;
its `.bundle` is a placeholder and must be replaced with a real AssetBundle.

## Tests

The SDK has a dependency-free smoke suite that compiles against minimal Unity
stubs, so it runs without the Unity Editor:

```bash
dotnet run --project tests/WorkmodsSDK.Tests.csproj
```

## Package validation

Before publishing, check both the source folder and the final ZIP:

```bash
python -m workmods validate path/to/my-mod
python -m workmods validate-package path/to/my-mod.zip --sha256 <expected-digest>
```

The package validator rejects unsafe archive entries, oversized archives and
SHA-256 mismatches, and applies the same manifest checks as the desktop editor.
