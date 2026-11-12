# Workmods SDK tests

This is a dependency-free smoke suite for `WorkmodsSDK.cs`. It compiles the SDK
against minimal Unity API stubs, so it runs on a normal .NET SDK without the
Unity Editor.

```bash
dotnet run --project unity-sdk/tests/WorkmodsSDK.Tests.csproj
```

The suite covers folder discovery, `game_id` filtering, manifest fallback,
bundle/DLL detection, rescan, missing-mod handling and unload/reload behavior.

`UnityStubs.cs` is deliberately small: it only implements the UnityEngine types
the SDK actually uses. It is not a substitute for testing inside Unity, and it
does not load real AssetBundles.
