// ============================================================================
//  WorkmodsSDK.cs — drop-in mod loader for Unity games
// ============================================================================
//
//  WHAT THIS IS
//  ------------
//  Workmods stores every installed mod in its own folder:
//
//      <modsRoot>/<modId>/<mod files...>
//
//  This file scans that folder, exposes the list to your game, and loads
//  AssetBundles (or DLLs) from it. It is a single, dependency-free MonoBehaviour
//  helper: copy it anywhere under Assets/ (for example Assets/Workmods/) and it
//  compiles on Unity 2019.4+ (Mono and IL2CPP).
//
//  QUICK START
//  -----------
//      using Workmods;
//
//      void Start()
//      {
//          // Defaults to Application.persistentDataPath/Workmods.
//          // Pass your registry game id to ignore mods built for other games.
//          WorkmodsSDK.Initialize(gameId: "space-rangers");
//
//          foreach (var mod in WorkmodsSDK.GetInstalledMods())
//              Debug.Log(mod.Name + " " + mod.Version);
//
//          var prefab = WorkmodsSDK.LoadAssetBundle("a1b2c3d4", "MyPrefab");
//          if (prefab != null)
//              Instantiate(prefab);
//      }
//
//  Or add the "Workmods Mod Loader" component to a bootstrap object and it
//  initializes itself on Awake.
//
//  HOW MODS ARE SHIPPED (pick one)
//  -------------------------------
//  1. AssetBundles (recommended) — the modder builds a bundle from prefabs,
//     scenes, ScriptableObjects, audio, textures, etc. and puts the .bundle file
//     (plus optional dependency bundles) in the mod folder. This works on every
//     scripting backend and on consoles; this SDK loads it with
//     AssetBundle.LoadFromFile.
//  2. Addressables (also supported) — the modder's Addressables build produces
//     .bundle files too. Merge the bundle files into the mod folder and call
//     LoadAssetBundle; for content catalogues you need your own
//     IResourceLocator pointed at the mod's catalog JSON.
//  3. Plain DLL — a compiled assembly (Mono scripting backend only; IL2CPP
//     cannot JIT arbitrary code). Call TryLoadAssembly and reflect over the
//     types. This is the most powerful and the least safe option.
//
//  A mod may include a workmod.json (or the .devers_meta.json written by the
//  Workmods client) to describe itself:
//
//      {
//        "id": "a1b2c3d4",
//        "game_id": "space-rangers",
//        "name": "Neon UI",
//        "version": "1.2.0",
//        "author": "someone",
//        "description": "Neon HUD replacement",
//        "entry_asset": "NeonHud",
//        "bundles": ["neon-ui.bundle", "shared.bundle"]
//      }
//
//  All optional. Without a manifest the folder name is used as the id and the
//  SDK discovers bundle files by extension.
//
//  SECURITY NOTE
//  -------------
//  Mods are executable content. Workmods verifies SHA-256 at install time, but
//  your game should still treat mods as untrusted: prefer AssetBundles, warn
//  players before enabling DLL mods, and never run mod code with elevated
//  permissions.
// ============================================================================

using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using UnityEngine;

namespace Workmods
{
    /// <summary>Deserialized mod manifest. Unknown JSON fields are ignored.</summary>
    [Serializable]
    public class WorkmodsModManifest
    {
        public string id;
        public string game_id;
        public string name;
        public string version;
        public string author;
        public string description;
        public string entry_asset;
        public string[] tags;
        public string[] bundles; // optional explicit bundle list
        public string repo;
    }

    /// <summary>One installed mod and the files found in its folder.</summary>
    public class WorkmodsInstalledMod
    {
        public string ModId { get; internal set; }
        public string GameId { get; internal set; }
        public string Name { get; internal set; }
        public string Version { get; internal set; }
        public string Author { get; internal set; }
        public string Description { get; internal set; }
        public string EntryAsset { get; internal set; }
        public string DirectoryPath { get; internal set; }
        public WorkmodsModManifest Manifest { get; internal set; }
        public List<string> Files { get; internal set; }

        internal WorkmodsInstalledMod()
        {
            Files = new List<string>();
        }

        public bool HasManifest
        {
            get { return Manifest != null; }
        }

        /// <summary>Absolute path of a file inside the mod, or null when missing.</summary>
        public string GetFile(string relativePath)
        {
            if (string.IsNullOrEmpty(relativePath) || string.IsNullOrEmpty(DirectoryPath))
                return null;
            string candidate = Path.Combine(DirectoryPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
            return File.Exists(candidate) ? candidate : null;
        }

        /// <summary>
        /// Files that should be loadable as AssetBundles. Uses the manifest list
        /// when present, otherwise known bundle extensions, otherwise every file
        /// that is clearly not metadata or a DLL.
        /// </summary>
        public List<string> GetBundlePaths()
        {
            var result = new List<string>();

            if (Manifest != null && Manifest.bundles != null && Manifest.bundles.Length > 0)
            {
                foreach (string entry in Manifest.bundles)
                {
                    string path = GetFile(entry);
                    if (!string.IsNullOrEmpty(path))
                        result.Add(path);
                    else
                        WorkmodsLog.Warn("Mod '" + ModId + "' declares missing bundle: " + entry);
                }
                if (result.Count > 0)
                    return result;
            }

            var candidates = new List<string>();
            foreach (string file in Files)
            {
                string extension = Path.GetExtension(file).ToLowerInvariant();
                if (extension == ".bundle" || extension == ".unity3d" ||
                    extension == ".assetbundle" || extension == ".ab" || extension == ".bytes")
                {
                    candidates.Add(file);
                }
            }

            if (candidates.Count == 0)
            {
                foreach (string file in Files)
                {
                    string extension = Path.GetExtension(file).ToLowerInvariant();
                    if (extension == ".json" || extension == ".txt" || extension == ".md" ||
                        extension == ".dll" || extension == ".pdb" || extension == ".mdb" ||
                        extension == ".png" || extension == ".jpg" || extension == ".jpeg" ||
                        extension == ".meta" || extension == ".manifest")
                        continue;
                    candidates.Add(file);
                }
            }

            // Dependencies are often stored in a bundles/ subfolder; load them first.
            candidates.Sort(delegate (string a, string b)
            {
                bool aNested = a.IndexOf("bundles", StringComparison.OrdinalIgnoreCase) >= 0;
                bool bNested = b.IndexOf("bundles", StringComparison.OrdinalIgnoreCase) >= 0;
                if (aNested == bNested)
                    return string.Compare(a, b, StringComparison.OrdinalIgnoreCase);
                return aNested ? -1 : 1;
            });
            result.AddRange(candidates);
            return result;
        }

        /// <summary>Every managed assembly shipped by the mod.</summary>
        public List<string> GetAssemblyPaths()
        {
            var result = new List<string>();
            foreach (string file in Files)
            {
                string extension = Path.GetExtension(file).ToLowerInvariant();
                if (extension == ".dll")
                    result.Add(file);
            }
            return result;
        }

        public override string ToString()
        {
            return Name + " v" + (string.IsNullOrEmpty(Version) ? "?" : Version) +
                   " [" + ModId + "]";
        }
    }

    /// <summary>Static logging with an optional file sink.</summary>
    public static class WorkmodsLog
    {
        public const string Prefix = "[Workmods] ";

        /// <summary>Raised for every SDK log line; hook this into your own console.</summary>
        public static event Action<string> OnLog;

        public static bool Verbose = true;
        public static bool WriteToFile;
        public static string LogFilePath;

        private static readonly Queue<string> Recent = new Queue<string>();
        private const int RecentLimit = 200;

        public static void Info(string message)
        {
            if (!Verbose)
                return;
            Emit(message, false);
        }

        public static void Warn(string message)
        {
            Emit(message, false);
            Debug.LogWarning(Prefix + message);
        }

        public static void Error(string message)
        {
            Emit(message, true);
            Debug.LogError(Prefix + message);
        }

        /// <summary>Most recent SDK messages, oldest first (useful for an in-game log screen).</summary>
        public static string[] GetRecentLines()
        {
            return Recent.ToArray();
        }

        private static void Emit(string message, bool isError)
        {
            string line = DateTime.Now.ToString("HH:mm:ss") + " " + message;
            Recent.Enqueue(line);
            while (Recent.Count > RecentLimit)
                Recent.Dequeue();

            Action<string> handler = OnLog;
            if (handler != null)
            {
                try { handler(line); }
                catch (Exception) { /* a consumer's logger must never break loading */ }
            }

            if (!WriteToFile || string.IsNullOrEmpty(LogFilePath))
                return;
            try
            {
                string directory = Path.GetDirectoryName(LogFilePath);
                if (!string.IsNullOrEmpty(directory) && !Directory.Exists(directory))
                    Directory.CreateDirectory(directory);
                File.AppendAllText(LogFilePath, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") +
                    (isError ? " ERROR " : " ") + message + Environment.NewLine, Encoding.UTF8);
            }
            catch (Exception)
            {
                // Logging must never be the reason a game fails to start.
            }
        }
    }

    /// <summary>
    /// Entry point. All methods are safe to call before/while mods are absent —
    /// an empty list is returned and the reason is logged.
    /// </summary>
    public static class WorkmodsSDK
    {
        public const string DefaultFolderName = "Workmods";
        public const string ManifestFileName = "workmod.json";
        public const string ClientManifestFileName = ".devers_meta.json";

        private static readonly List<WorkmodsInstalledMod> Mods = new List<WorkmodsInstalledMod>();
        private static readonly Dictionary<string, AssetBundle> Bundles =
            new Dictionary<string, AssetBundle>(StringComparer.OrdinalIgnoreCase);
        private static readonly Dictionary<string, string> BundleOwners =
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        private static readonly Dictionary<string, Assembly> Assemblies =
            new Dictionary<string, Assembly>(StringComparer.OrdinalIgnoreCase);

        public static string ModsRoot { get; private set; }
        public static string GameId { get; private set; }
        public static bool IsInitialized { get; private set; }

        /// <summary>Application.persistentDataPath/Workmods — where the client installs.</summary>
        public static string DefaultModsRoot
        {
            get { return Path.Combine(Application.persistentDataPath, DefaultFolderName); }
        }

        /// <summary>
        /// Scan the mod folder. Safe to call more than once; call Rescan() to
        /// pick up mods installed while the game is running.
        /// </summary>
        /// <param name="modsRoot">Folder to scan. Defaults to DefaultModsRoot.</param>
        /// <param name="gameId">
        /// When set, mods whose manifest declares a different game_id are ignored.
        /// Mods without a game_id are always accepted.
        /// </param>
        /// <param name="verboseLogging">Log every discovered mod and load step.</param>
        /// <param name="writeLogToFile">Also append to &lt;modsRoot&gt;/workmods.log.</param>
        public static void Initialize(string modsRoot = null, string gameId = null,
            bool verboseLogging = true, bool writeLogToFile = false)
        {
            ModsRoot = string.IsNullOrEmpty(modsRoot) ? DefaultModsRoot : modsRoot;
            GameId = gameId;
            WorkmodsLog.Verbose = verboseLogging;
            WorkmodsLog.WriteToFile = writeLogToFile;
            WorkmodsLog.LogFilePath = Path.Combine(ModsRoot, "workmods.log");

            IsInitialized = true;
            Scan();
        }

        /// <summary>Re-scan the folder; already loaded bundles stay loaded.</summary>
        public static void Rescan()
        {
            if (!IsInitialized)
            {
                Initialize();
                return;
            }
            Scan();
        }

        private static void Scan()
        {
            Mods.Clear();
            if (string.IsNullOrEmpty(ModsRoot) || !Directory.Exists(ModsRoot))
            {
                WorkmodsLog.Info("No mods folder at " + ModsRoot + " (nothing to load).");
                return;
            }

            string[] directories;
            try
            {
                directories = Directory.GetDirectories(ModsRoot);
            }
            catch (Exception exception)
            {
                WorkmodsLog.Error("Cannot list " + ModsRoot + ": " + exception.Message);
                return;
            }

            foreach (string directory in directories)
            {
                string folderName = Path.GetFileName(directory);
                if (string.IsNullOrEmpty(folderName) || folderName.StartsWith(".", StringComparison.Ordinal))
                    continue;

                try
                {
                    WorkmodsInstalledMod mod = ReadMod(directory);
                    if (mod == null)
                        continue;
                    if (!string.IsNullOrEmpty(GameId) && !string.IsNullOrEmpty(mod.GameId) &&
                        !string.Equals(GameId, mod.GameId, StringComparison.OrdinalIgnoreCase))
                    {
                        WorkmodsLog.Info("Skipping " + mod.Name + ": built for game '" + mod.GameId + "'.");
                        continue;
                    }
                    Mods.Add(mod);
                    WorkmodsLog.Info("Discovered mod " + mod + " (" + mod.Files.Count + " files).");
                }
                catch (Exception exception)
                {
                    WorkmodsLog.Error("Failed to read mod folder " + directory + ": " + exception.Message);
                }
            }
        }

        private static WorkmodsInstalledMod ReadMod(string directory)
        {
            WorkmodsModManifest manifest = ReadManifest(directory);
            string folderName = Path.GetFileName(directory);
            var files = new List<string>();
            try
            {
                foreach (string file in Directory.GetFiles(directory, "*", SearchOption.AllDirectories))
                    files.Add(file);
            }
            catch (Exception exception)
            {
                WorkmodsLog.Error("Cannot list files of " + folderName + ": " + exception.Message);
                return null;
            }

            var mod = new WorkmodsInstalledMod
            {
                ModId = manifest != null && !string.IsNullOrEmpty(manifest.id) ? manifest.id : folderName,
                GameId = manifest != null ? manifest.game_id : null,
                Name = manifest != null && !string.IsNullOrEmpty(manifest.name) ? manifest.name : folderName,
                Version = manifest != null ? manifest.version : null,
                Author = manifest != null ? manifest.author : null,
                Description = manifest != null ? manifest.description : null,
                EntryAsset = manifest != null ? manifest.entry_asset : null,
                DirectoryPath = directory,
                Manifest = manifest,
                Files = files
            };
            return mod;
        }

        private static WorkmodsModManifest ReadManifest(string directory)
        {
            string[] names = { ManifestFileName, ClientManifestFileName };
            foreach (string name in names)
            {
                string path = Path.Combine(directory, name);
                if (!File.Exists(path))
                    continue;
                try
                {
                    string json = File.ReadAllText(path, Encoding.UTF8);
                    WorkmodsModManifest manifest = JsonUtility.FromJson<WorkmodsModManifest>(json);
                    if (manifest != null)
                        return manifest;
                }
                catch (Exception exception)
                {
                    WorkmodsLog.Warn("Invalid manifest " + path + ": " + exception.Message);
                }
            }
            return null;
        }

        /// <summary>All mods matching the configured game id, in folder order.</summary>
        public static IReadOnlyList<WorkmodsInstalledMod> GetInstalledMods()
        {
            if (!IsInitialized)
                Initialize();
            return Mods;
        }

        /// <summary>Mods that declare a specific game id (for multi-game launchers).</summary>
        public static List<WorkmodsInstalledMod> GetInstalledMods(string gameId)
        {
            var result = new List<WorkmodsInstalledMod>();
            foreach (WorkmodsInstalledMod mod in GetInstalledMods())
            {
                if (string.Equals(mod.GameId, gameId, StringComparison.OrdinalIgnoreCase))
                    result.Add(mod);
            }
            return result;
        }

        public static WorkmodsInstalledMod GetInstalledMod(string modId)
        {
            if (string.IsNullOrEmpty(modId))
                return null;
            foreach (WorkmodsInstalledMod mod in GetInstalledMods())
            {
                if (string.Equals(mod.ModId, modId, StringComparison.OrdinalIgnoreCase))
                    return mod;
            }
            return null;
        }

        public static bool IsInstalled(string modId)
        {
            return GetInstalledMod(modId) != null;
        }

        // ---------------------------------------------------------------- loads

        /// <summary>
        /// Load one asset from a mod's AssetBundle. Returns null (and logs why)
        /// when the mod, bundle or asset cannot be found. Assets that reference
        /// prefabs keep their dependencies as long as the bundle is not unloaded.
        /// </summary>
        public static UnityEngine.Object LoadAssetBundle(string modId, string assetName)
        {
            return LoadAsset<UnityEngine.Object>(modId, assetName);
        }

        /// <summary>Typed variant, e.g. LoadAsset&lt;GameObject&gt;(...).</summary>
        public static T LoadAsset<T>(string modId, string assetName) where T : UnityEngine.Object
        {
            WorkmodsInstalledMod mod = GetInstalledMod(modId);
            if (mod == null)
            {
                WorkmodsLog.Error("Load failed: mod '" + modId + "' is not installed.");
                return null;
            }
            if (string.IsNullOrEmpty(assetName))
            {
                WorkmodsLog.Error("Load failed for mod '" + modId + "': assetName is empty.");
                return null;
            }

            List<AssetBundle> bundles = LoadBundles(mod);
            if (bundles.Count == 0)
            {
                WorkmodsLog.Error("Load failed for mod '" + modId + "': no AssetBundle found. " +
                                  "Ship a .bundle file or list one in workmod.json.");
                return null;
            }

            foreach (AssetBundle bundle in bundles)
            {
                if (!bundle.Contains(assetName))
                    continue;
                T asset = bundle.LoadAsset<T>(assetName);
                if (asset != null)
                {
                    WorkmodsLog.Info("Loaded asset '" + assetName + "' from " + mod + ".");
                    return asset;
                }
                WorkmodsLog.Warn("Asset '" + assetName + "' could not be loaded as " +
                                 typeof(T).Name + " from " + bundle.name + ".");
            }

            WorkmodsLog.Error("Asset '" + assetName + "' not found in any bundle of " + mod + ".");
            return null;
        }

        /// <summary>Load and cache every bundle belonging to a mod.</summary>
        public static List<AssetBundle> LoadBundles(WorkmodsInstalledMod mod)
        {
            var result = new List<AssetBundle>();
            if (mod == null)
                return result;

            foreach (string path in mod.GetBundlePaths())
            {
                AssetBundle bundle;
                if (Bundles.TryGetValue(path, out bundle) && bundle != null)
                {
                    result.Add(bundle);
                    continue;
                }

                bundle = LoadBundleFile(path, mod.ModId);
                if (bundle == null)
                    continue;
                Bundles[path] = bundle;
                BundleOwners[path] = mod.ModId;
                result.Add(bundle);
            }
            return result;
        }

        private static AssetBundle LoadBundleFile(string path, string modId)
        {
            try
            {
                AssetBundle bundle = AssetBundle.LoadFromFile(path);
                if (bundle == null)
                {
                    // Some platforms/packers reject LoadFromFile; memory load is a
                    // safe fallback for small bundles.
                    bundle = AssetBundle.LoadFromMemory(File.ReadAllBytes(path));
                }
                if (bundle == null)
                {
                    WorkmodsLog.Error("AssetBundle.LoadFromFile returned null for " + path);
                    return null;
                }
                WorkmodsLog.Info("Loaded bundle " + Path.GetFileName(path) + " from mod '" + modId + "'.");
                return bundle;
            }
            catch (Exception exception)
            {
                WorkmodsLog.Error("Failed to load bundle " + path + ": " + exception.Message);
                return null;
            }
        }

        /// <summary>Primary cached bundle of a mod (first loadable one), or null.</summary>
        public static AssetBundle GetAssetBundle(string modId)
        {
            WorkmodsInstalledMod mod = GetInstalledMod(modId);
            if (mod == null)
                return null;
            List<AssetBundle> bundles = LoadBundles(mod);
            return bundles.Count > 0 ? bundles[0] : null;
        }

        /// <summary>
        /// Load the first managed assembly shipped by the mod. Mono backend only:
        /// IL2CPP cannot load assemblies at runtime, in which case this logs an
        /// error and returns false.
        /// </summary>
        public static bool TryLoadAssembly(string modId, out Assembly assembly)
        {
            assembly = null;
            WorkmodsInstalledMod mod = GetInstalledMod(modId);
            if (mod == null)
            {
                WorkmodsLog.Error("Cannot load assembly: mod '" + modId + "' is not installed.");
                return false;
            }

            List<string> paths = mod.GetAssemblyPaths();
            if (paths.Count == 0)
            {
                WorkmodsLog.Warn("Mod '" + modId + "' does not contain a .dll.");
                return false;
            }

#if ENABLE_IL2CPP
            WorkmodsLog.Error("DLL mods are not supported with the IL2CPP scripting backend. " +
                              "Use AssetBundles or let the modder ship IL2CPP-compatible content.");
            return false;
#else
            foreach (string path in paths)
            {
                try
                {
                    assembly = Assembly.LoadFrom(path);
                    Assemblies[modId] = assembly;
                    WorkmodsLog.Info("Loaded assembly " + Path.GetFileName(path) + " from mod '" + modId + "'.");
                    return true;
                }
                catch (Exception exception)
                {
                    WorkmodsLog.Error("Failed to load assembly " + path + ": " + exception.Message);
                }
            }
            return false;
#endif
        }

        /// <summary>Cached assembly of a mod, if TryLoadAssembly succeeded.</summary>
        public static Assembly GetAssembly(string modId)
        {
            Assembly assembly;
            return Assemblies.TryGetValue(modId, out assembly) ? assembly : null;
        }

        // -------------------------------------------------------------- unloads

        /// <summary>
        /// Unload a mod's bundles. Destroy every instantiated object that came
        /// from them first, otherwise Unity leaks the assets.
        /// </summary>
        public static void UnloadAssetBundle(string modId)
        {
            if (string.IsNullOrEmpty(modId))
                return;
            var toRemove = new List<string>();
            foreach (KeyValuePair<string, AssetBundle> pair in Bundles)
            {
                if (pair.Value == null)
                {
                    toRemove.Add(pair.Key);
                    continue;
                }
                if (!BundleOwners.TryGetValue(pair.Key, out string owner) ||
                    !string.Equals(owner, modId, StringComparison.OrdinalIgnoreCase))
                    continue;
                try { pair.Value.Unload(false); }
                catch (Exception exception) { WorkmodsLog.Warn("Unload failed: " + exception.Message); }
                toRemove.Add(pair.Key);
            }
            foreach (string key in toRemove)
            {
                Bundles.Remove(key);
                BundleOwners.Remove(key);
            }
        }

        /// <summary>Unload all mod bundles and forget loaded assemblies.</summary>
        public static void UnloadAll()
        {
            foreach (KeyValuePair<string, AssetBundle> pair in Bundles)
            {
                if (pair.Value == null)
                    continue;
                try { pair.Value.Unload(false); }
                catch (Exception) { /* already unloaded */ }
            }
            Bundles.Clear();
            BundleOwners.Clear();
            Assemblies.Clear();
            WorkmodsLog.Info("All mod bundles unloaded.");
        }
    }

    /// <summary>
    /// Optional convenience component. Put it on a bootstrap object in your first
    /// scene; it initializes the SDK on Awake and can scan a custom folder.
    /// </summary>
    [AddComponentMenu("Workmods/Workmods Mod Loader")]
    public class WorkmodsModLoader : MonoBehaviour
    {
        [Tooltip("Leave empty to use Application.persistentDataPath/Workmods.")]
        public string modsFolderOverride = "";

        [Tooltip("Your registry game id. Mods for other games are ignored.")]
        public string gameId = "";

        [Tooltip("Call WorkmodsSDK.Initialize automatically on Awake.")]
        public bool initializeOnAwake = true;

        [Tooltip("Log discovered mods and load steps to the Unity console.")]
        public bool verboseLogging = true;

        [Tooltip("Also append SDK logs to <mods folder>/workmods.log.")]
        public bool writeLogToFile = false;

        private void Awake()
        {
            if (initializeOnAwake)
                Initialize();
        }

        public void Initialize()
        {
            WorkmodsSDK.Initialize(
                string.IsNullOrEmpty(modsFolderOverride) ? null : modsFolderOverride,
                string.IsNullOrEmpty(gameId) ? null : gameId,
                verboseLogging,
                writeLogToFile);
        }

        /// <summary>Re-scan after the player installed a mod in-game.</summary>
        public void Reload()
        {
            WorkmodsSDK.Rescan();
        }
    }
}
