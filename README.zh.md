# ✦ Devers Workmods

**面向所有 Unity 游戏的独立 Steam 创意工坊替代品——由社区拥有的模组平台。**

**语言：** [English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md) · 中文

**状态：** `v1.0b` —— 重新设计客户端的公开测试版。[下载首个测试版](https://github.com/Made-by-One/Devers-Workmods/releases/tag/v1.0b)，或先阅读[已知限制](#限制)。

Workmods 由三个共享同一格式的部分组成：

1. **桌面客户端**（Python + PyQt6）：玩家按游戏浏览、安装、更新和删除模组。
2. **公共注册表**（`registry.json`）：由 GitHub Actions 重建，无中心服务器，也不锁定供应商。
3. **Unity SDK**（`unity-sdk/WorkmodsSDK.cs`）：游戏开发者只需加入一个 C# 文件，即可发现并加载模组。

模组存放在作者自己的 GitHub 仓库中，通过 GitHub Releases 分发。Workmods 只保存元数据。

```
Workmods 客户端 ── ZIP + Release ──► 模组仓库
       │
       └── pull request ────────────► submissions/ + GitHub Action
                                             │
                                             ▼
                                      registry.json
                                             │
                                             ▼
                                    客户端中的目录
                                             │
                                             ▼
                              模组文件夹 + Unity SDK
```

---

## 下载

预编译版本发布在 [GitHub Releases](https://github.com/Made-by-One/Devers-Workmods/releases/tag/v1.0b)：

| 系统 | 压缩包 |
|---|---|
| Windows x64 | `Workmods-windows-x86_64.zip` |
| Linux x86_64 | `Workmods-linux-x86_64.tar.gz` |
| macOS | `Workmods-macos.zip` |

解压后运行 `Workmods.exe`、`Workmods` 或 `Workmods.app`。Python 和 PyQt6 已包含在内。macOS 版本未签名：首次启动请使用**右键 → 打开**。Windows SmartScreen 也可能显示类似提示。

---

## 玩家

### 从源码运行

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

1. 打开 **Settings → Game Profiles → Add Game**，设置 `game_id`、显示名称和安装目录（例如 `~/DeversMods/space-rangers`）。
2. 在 **Catalog** 过滤器中选择游戏，列表只显示具有相同 `game_id` 的模组。
3. 点击 **Install**。客户端会下载 Release 中的 ZIP，用注册表中的 SHA-256 校验，并解压到 `<安装目录>/<modId>/`。
4. 让游戏读取该目录。Unity SDK 默认使用 `Application.persistentDataPath/Workmods`。

已安装模组按游戏分组显示。**Delete** 只删除模组文件夹。要更新时重新安装，旧文件夹会被原子替换。

---

## 模组作者

需要 GitHub 账号。Workmods 会自动创建并填充仓库，无需手动操作 git。

1. **准备模组文件夹：** `.bundle` 文件（推荐）、Addressables 输出或 DLL。可以在旁边放置 `workmod.json`：

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

2. 在 **Author Studio** 中通过 GitHub OAuth 登录。
3. 点击 **New Repo**，创建公开仓库并在编辑器中选择它。
4. 填写名称、版本、描述、目标游戏，可选图标和横幅，然后选择文件文件夹。
5. 点击 **Publish & Request Addition**。客户端会打包 ZIP、计算 SHA-256、把 Release 上传到你的仓库，并提交包含 `submissions/<game_id>/<mod_id>.json` 的 pull request。

不需要注册表写权限：pull request 来自你的 fork。CI 会校验文件，维护者审核后合并，随后 GitHub Action 重建 `registry.json`。

**更新：** 提升版本并重新发布，新的 pull request 会替换同一份提交。**Unpublish** 会创建删除提交的 pull request；你的仓库和 Release 仍然保留。

完整指南：[docs/PUBLISHING.md](docs/PUBLISHING.md)。

---

## Unity 开发者

Workmods 不绑定某个具体游戏：模组声明 `game_id`，游戏用相同的 id 初始化 SDK。

1. 将 [`unity-sdk/WorkmodsSDK.cs`](unity-sdk/WorkmodsSDK.cs) 复制到 `Assets/Workmods/`，不需要额外包或依赖。
2. 选择内容格式：

| 格式 | 支持平台 | 适用场景 |
|---|---|---|
| **AssetBundles**（推荐） | Mono + IL2CPP，所有平台 | 预制体、纹理、音频、ScriptableObject |
| **Addressables** | Mono + IL2CPP | 已使用 Addressables 的项目 |
| **DLL** | 仅 Mono | 深入修改玩法的模组 |

3. 初始化并加载：

```csharp
using Workmods;
using UnityEngine;

public class ModBootstrap : MonoBehaviour
{
    void Start()
    {
        WorkmodsSDK.Initialize(gameId: "space-rangers", writeLogToFile: true);

        foreach (var mod in WorkmodsSDK.GetInstalledMods())
            Debug.Log($"{mod.Name} {mod.Version}: {mod.DirectoryPath}");

        var prefab = WorkmodsSDK.LoadAssetBundle("a1b2c3d4", "NeonHud") as GameObject;
        if (prefab != null)
            Instantiate(prefab);
    }
}
```

API：`GetInstalledMods()`、`GetInstalledMod(id)`、`IsInstalled(id)`、`LoadAssetBundle(...)`、`LoadAsset<T>(...)`、`TryLoadAssembly(...)`、`UnloadAssetBundle(id)`、`UnloadAll()`、`Rescan()`。

SDK 会记录发现的模组、加载的 bundle 和错误，但不会向游戏循环抛出异常。更多：[docs/UNITY_INTEGRATION.md](docs/UNITY_INTEGRATION.md)。

---

## 注册表

`registry.json` 只由 GitHub Action 生成，请勿手动编辑。Schema v2 包含 `schema_version`、`games` 和 `mods`；每个模组都有 `game_id`、`download_url`、`sha256` 和元数据。读取版本 1 的文档时会自动迁移到 `default` 配置。

完整字段说明和提交格式：[docs/REGISTRY_SCHEMA.md](docs/REGISTRY_SCHEMA.md)。

---

## 开发与构建

```bash
pip install -r requirements-dev.txt
pytest              # 59 个测试，无需显示器
ruff check workmods tests
```

本地构建独立客户端：

```bash
# Linux / macOS
pyinstaller --noconfirm --clean --onefile --windowed --name Workmods --add-data "data:data" main.py

# Windows（注意 --add-data 中的分号）
pyinstaller --noconfirm --clean --onefile --windowed --name Workmods --icon data/icon/app.ico --add-data "data;data" main.py
```

输出位于 `dist/`。GitHub Actions 会构建 Windows、Linux 和 macOS，并在 `v*` 标签上发布 Release；配置见 [.github/workflows/release.yml](.github/workflows/release.yml)。

---

## 限制

版本 1.0 有意保留的边界：

1. 发布通过 pull request 和人工审核，尚无自动恶意软件扫描。
2. 没有自动更新提示、依赖解析或模组加载顺序。
3. 通过 GitHub Contents API 上传大文件不合适（大约超过 50–100 MB）；请使用 Release 资产。
4. Unity SDK 不支持 WebGL。
5. SHA-256 只保证完整性，不保证可信度；模组没有签名。

---

## 许可证

MIT —— 见 [LICENSE](LICENSE)。
