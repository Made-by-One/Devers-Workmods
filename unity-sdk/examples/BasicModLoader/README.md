# Basic mod loader example

This folder is a minimal integration example for `WorkmodsSDK.cs`. It is not a
full Unity project: copy the files into your own Unity project and adjust the
scene references.

## Files

- `ModLoaderExample.cs` - bootstrap component that initializes the SDK and loads
  one mod's entry asset.
- `../sample-mod/` - a tiny valid mod package that can be installed into the
  scanned mods folder for local testing.

## Setup

1. Copy `unity-sdk/WorkmodsSDK.cs` to `Assets/Workmods/WorkmodsSDK.cs`.
2. Copy `ModLoaderExample.cs` to `Assets/Workmods/ModLoaderExample.cs`.
3. Create an empty GameObject in your first scene and add `ModLoaderExample`.
4. Set `Game Id` to the id used by your Workmods game profile.
5. Install `sample-mod` into the folder returned by `WorkmodsSDK.DefaultModsRoot`,
   or point `Mods Folder Override` at a folder containing it.
6. Run the scene. The example logs discovered mods and instantiates the entry
   asset when it is a `GameObject`.

## Notes

- DLL loading is Mono-only. AssetBundles work on both Mono and IL2CPP.
- Keep bundles loaded while instantiated objects are alive.
- Treat mods as untrusted content even though Workmods verifies SHA-256 at install time.
