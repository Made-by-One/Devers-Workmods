using System;
using System.Collections.Generic;
using System.IO;
using Workmods;
using UnityEngine;

internal static class WorkmodsSDKTests
{
    private static int failures;

    private static void Check(bool condition, string message)
    {
        if (condition)
            return;
        failures++;
        Console.Error.WriteLine("FAIL: " + message);
    }

    private static string CreateMod(string root, string folder, string manifestJson, params string[] files)
    {
        string directory = Path.Combine(root, folder);
        Directory.CreateDirectory(directory);
        if (manifestJson != null)
            File.WriteAllText(Path.Combine(directory, "workmod.json"), manifestJson);
        foreach (string file in files)
        {
            string path = Path.Combine(directory, file);
            string parent = Path.GetDirectoryName(path);
            if (!string.IsNullOrEmpty(parent))
                Directory.CreateDirectory(parent);
            File.WriteAllText(path, "test");
        }
        return directory;
    }

    public static int Main()
    {
        string root = Path.Combine(Path.GetTempPath(), "workmods-sdk-tests-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            CreateMod(root, "game-a-mod",
                "{\"id\":\"game-a-mod\",\"game_id\":\"game-a\",\"name\":\"Game A Mod\",\"version\":\"1.0.0\",\"entry_asset\":\"A\",\"bundles\":[\"a.bundle\"]}",
                "a.bundle");
            CreateMod(root, "game-b-mod",
                "{\"id\":\"game-b-mod\",\"game_id\":\"game-b\",\"name\":\"Game B Mod\",\"version\":\"1.0.0\"}",
                "b.bundle");
            CreateMod(root, "plain", null, "plain.bundle", "lib.dll");
            CreateMod(root, "broken", "{ not json", "content.bundle");

            WorkmodsSDK.Initialize(root, "game-a", true, false);

            Check(WorkmodsSDK.IsInitialized, "SDK initializes");
            Check(WorkmodsSDK.ModsRoot == root, "mods root is stored");
            Check(WorkmodsSDK.GameId == "game-a", "game id is stored");
            Check(WorkmodsSDK.GetInstalledMods().Count == 3,
                "game-b mod is filtered, other three are discovered");
            Check(WorkmodsSDK.GetInstalledMods("game-a").Count == 1,
                "explicit game id returns one mod");

            WorkmodsInstalledMod modA = WorkmodsSDK.GetInstalledMod("game-a-mod");
            Check(modA != null, "manifest mod is found by id");
            Check(modA != null && modA.Name == "Game A Mod", "manifest name is loaded");
            Check(modA != null && modA.EntryAsset == "A", "entry asset is loaded");
            Check(modA != null && modA.GetBundlePaths().Count == 1,
                "explicit bundle is resolved");

            WorkmodsInstalledMod plain = WorkmodsSDK.GetInstalledMod("plain");
            Check(plain != null, "manifest-less folder is discovered");
            Check(plain != null && !plain.HasManifest, "manifest-less folder has no manifest");
            Check(plain != null && plain.GetBundlePaths().Count == 1,
                "bundle extension is discovered");
            Check(plain != null && plain.GetAssemblyPaths().Count == 1,
                "DLL is discovered");

            WorkmodsInstalledMod broken = WorkmodsSDK.GetInstalledMod("broken");
            Check(broken != null && !broken.HasManifest,
                "invalid manifest falls back to the folder");

            Check(WorkmodsSDK.LoadAsset<GameObject>("missing-mod", "A") == null,
                "missing mod returns null");
            Check(WorkmodsSDK.GetAssetBundle("missing-mod") == null,
                "missing mod has no bundle");
            Check(WorkmodsSDK.GetAssetBundle("game-a-mod") != null,
                "existing bundle loads through the stub");

            CreateMod(root, "late",
                "{\"id\":\"late\",\"game_id\":\"game-a\",\"name\":\"Late Mod\",\"version\":\"1.0.0\"}",
                "late.bundle");
            WorkmodsSDK.Rescan();
            Check(WorkmodsSDK.GetInstalledMods().Count == 4,
                "rescan discovers a mod added at runtime");

            WorkmodsSDK.Initialize(root, "other-game", true, false);
            Check(WorkmodsSDK.GetInstalledMods().Count == 2,
                "only mods without a foreign game id remain");

            WorkmodsSDK.Initialize(root, null, true, false);
            Check(WorkmodsSDK.GetInstalledMods().Count == 5,
                "no game filter discovers every mod");

            Check(WorkmodsSDK.DefaultModsRoot ==
                Path.Combine(Application.persistentDataPath, "Workmods"),
                "default root is persistentDataPath/Workmods");

            var lines = new List<string>();
            WorkmodsLog.OnLog += line => lines.Add(line);
            WorkmodsLog.Info("captured line");
            Check(lines.Count > 0 && lines[lines.Count - 1].Contains("captured line"),
                "log events are delivered to subscribers");
            Check(WorkmodsLog.GetRecentLines().Length > 0,
                "recent log lines are retained");

            WorkmodsSDK.UnloadAll();
            Check(WorkmodsSDK.GetAssetBundle("game-a-mod") != null,
                "bundles can be loaded again after unload");
            WorkmodsSDK.UnloadAll();
        }
        finally
        {
            WorkmodsSDK.UnloadAll();
            try { Directory.Delete(root, true); } catch (IOException) { }
        }

        if (failures == 0)
        {
            Console.WriteLine("WorkmodsSDK tests passed.");
            return 0;
        }
        Console.Error.WriteLine(failures + " WorkmodsSDK test(s) failed.");
        return 1;
    }
}
