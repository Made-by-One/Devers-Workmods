using UnityEngine;
using Workmods;

/// <summary>
/// Minimal bootstrap for a game that supports Workmods mods.
/// Add this component to one GameObject in your first scene.
/// </summary>
public class ModLoaderExample : MonoBehaviour
{
    [Tooltip("Leave empty to use Application.persistentDataPath/Workmods.")]
    public string modsFolderOverride = "";

    [Tooltip("Your registry game id. Mods for other games are ignored.")]
    public string gameId = "sample-game";

    [Tooltip("Asset name to instantiate from the first installed mod.")]
    public string entryAssetOverride = "";

    [Tooltip("Log discovered mods and load steps to the Unity console.")]
    public bool verboseLogging = true;

    private void Awake()
    {
        WorkmodsSDK.Initialize(
            modsRoot: string.IsNullOrEmpty(modsFolderOverride) ? null : modsFolderOverride,
            gameId: string.IsNullOrEmpty(gameId) ? null : gameId,
            verboseLogging: verboseLogging,
            writeLogToFile: true);

        foreach (var mod in WorkmodsSDK.GetInstalledMods())
        {
            Debug.Log($"[Workmods Example] {mod.Name} v{mod.Version} ({mod.ModId})");
        }

        LoadFirstMod();
    }

    private void LoadFirstMod()
    {
        var mods = WorkmodsSDK.GetInstalledMods();
        if (mods.Count == 0)
        {
            Debug.Log("[Workmods Example] No mods installed.");
            return;
        }

        var mod = mods[0];
        string assetName = string.IsNullOrEmpty(entryAssetOverride)
            ? (string.IsNullOrEmpty(mod.EntryAsset) ? mod.Name : mod.EntryAsset)
            : entryAssetOverride;

        var asset = WorkmodsSDK.LoadAssetBundle(mod.ModId, assetName);
        if (asset is GameObject prefab)
        {
            Instantiate(prefab);
            Debug.Log($"[Workmods Example] Instantiated '{assetName}' from {mod.Name}.");
        }
        else if (asset != null)
        {
            Debug.Log($"[Workmods Example] Loaded '{assetName}' ({asset.GetType().Name}) from {mod.Name}.");
        }
        else
        {
            Debug.LogWarning($"[Workmods Example] Could not load '{assetName}' from {mod.Name}.");
        }
    }

    private void OnDestroy()
    {
        WorkmodsSDK.UnloadAll();
    }
}
