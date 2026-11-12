// Minimal UnityEngine surface used by WorkmodsSDK. These stubs are only for
// compiling and testing the SDK outside Unity; they are not a Unity emulator.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;

namespace UnityEngine
{
    public class Object
    {
    }

    public class GameObject : Object
    {
    }

    public class MonoBehaviour
    {
    }

    [AttributeUsage(AttributeTargets.Class)]
    public class AddComponentMenu : Attribute
    {
        public AddComponentMenu(string menuName)
        {
        }
    }

    [AttributeUsage(AttributeTargets.Field)]
    public class TooltipAttribute : Attribute
    {
        public TooltipAttribute(string text)
        {
        }
    }

    public static class Application
    {
        public static string persistentDataPath
        {
            get { return Path.Combine(Path.GetTempPath(), "workmods-unity-test-data"); }
        }
    }

    public static class Debug
    {
        public static void Log(object message)
        {
        }

        public static void LogWarning(object message)
        {
        }

        public static void LogError(object message)
        {
        }
    }

    public static class JsonUtility
    {
        private static readonly JsonSerializerOptions Options = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
            IncludeFields = true
        };

        public static T FromJson<T>(string json)
        {
            return JsonSerializer.Deserialize<T>(json, Options);
        }
    }

    public class AssetBundle
    {
        public string name;
        private readonly HashSet<string> assets = new HashSet<string>(StringComparer.Ordinal);

        public static AssetBundle LoadFromFile(string path)
        {
            if (!File.Exists(path))
                return null;
            return new AssetBundle { name = Path.GetFileName(path) };
        }

        public static AssetBundle LoadFromMemory(byte[] bytes)
        {
            return new AssetBundle { name = "memory" };
        }

        public bool Contains(string assetName)
        {
            return assets.Contains(assetName);
        }

        public T LoadAsset<T>(string assetName) where T : Object
        {
            return null;
        }

        public void Unload(bool unloadAllLoadedObjects)
        {
        }
    }
}
