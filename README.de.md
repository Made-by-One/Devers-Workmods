# ✦ Devers Workmods

**Eine unabhängige Mod-Plattform für alle Unity-Spiele — ein Steam Workshop, der der Community gehört.**

**Sprachen:** [English](README.md) · [Русский](README.ru.md) · Deutsch · [Español](README.es.md) · [Français](README.fr.md) · [中文](README.zh.md)

**Status:** `v1.0b` — öffentliche Beta mit überarbeitetem Client. [Erste Beta herunterladen](https://github.com/Made-by-One/Devers-Workmods/releases/tag/v1.0b) oder zuerst die [bekannten Einschränkungen](#einschränkungen) lesen.

Workmods besteht aus drei Teilen mit einem gemeinsamen Format:

1. **Desktop-Client** (Python + PyQt6): Spieler durchsuchen, installieren, aktualisieren und entfernen Mods pro Spiel.
2. **Öffentliches Register** (`registry.json`), das von GitHub Actions neu aufgebaut wird — ohne zentralen Server und ohne Bindung an einen Anbieter.
3. **Unity-SDK** (`unity-sdk/WorkmodsSDK.cs`): eine einzelne C#-Datei, die Spieleentwickler einbinden, um Mods zu finden und zu laden.

Mods liegen im GitHub-Repository des Autors und werden über GitHub Releases verteilt. Workmods speichert nur Metadaten.

```
Workmods-Client ── ZIP + Release ──► Repository des Mods
       │
       └── Pull Request ───────────► submissions/ + GitHub Action
                                             │
                                             ▼
                                      registry.json
                                             │
                                             ▼
                                    Katalog im Client
                                             │
                                             ▼
                              Mod-Ordner + Unity-SDK
```

---

## Download

Fertige Builds werden in den [GitHub Releases](https://github.com/Made-by-One/Devers-Workmods/releases/tag/v1.0b) veröffentlicht:

| System | Archiv |
|---|---|
| Windows x64 | `Workmods-windows-x86_64.zip` |
| Linux x86_64 | `Workmods-linux-x86_64.tar.gz` |
| macOS | `Workmods-macos.zip` |

Archiv entpacken und `Workmods.exe`, `Workmods` oder `Workmods.app` starten. Python und PyQt6 sind enthalten. Der macOS-Build ist nicht signiert: beim ersten Start **Rechtsklick → Öffnen** verwenden. Windows SmartScreen kann ebenfalls warnen.

---

## Für Spieler

### Aus dem Quellcode starten

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

1. **Settings → Game Profiles → Add Game** öffnen und `game_id`, Anzeigename und Installationsordner festlegen (zum Beispiel `~/DeversMods/space-rangers`).
2. Im **Catalog**-Filter ein Spiel wählen — angezeigt werden nur Mods mit passender `game_id`.
3. **Install** drücken. Der Client lädt das Release-ZIP, prüft die SHA-256-Summe gegen das Register und entpackt den Mod nach `<Installationsordner>/<modId>/`.
4. Diesen Ordner im Spiel verwenden. Das Unity-SDK nutzt standardmäßig `Application.persistentDataPath/Workmods`.

Installierte Mods werden pro Spiel angezeigt. **Delete** entfernt nur den Mod-Ordner. Zum Aktualisieren erneut installieren — der alte Ordner wird atomar ersetzt.

---

## Für Mod-Ersteller

Du brauchst ein GitHub-Konto. Workmods erstellt und befüllt das Repository selbst — du musst nie manuell mit git arbeiten.

1. **Mod-Ordner vorbereiten:** `.bundle`-Dateien (empfohlen), Addressables-Ausgabe oder DLLs. Optional `workmod.json` daneben legen:

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

2. Im **Author Studio** über GitHub OAuth anmelden.
3. **New Repo** drücken, ein öffentliches Repository erstellen und im Editor auswählen.
4. Name, Version, Beschreibung, Zielspiel und optional Icon/Banner ausfüllen und den Dateiordner wählen.
5. **Publish & Request Addition** drücken. Der Client packt die Dateien als ZIP, berechnet SHA-256, lädt das Release ins eigene Repository und öffnet einen Pull Request mit `submissions/<game_id>/<mod_id>.json`.

Schreibrechte am Register sind nicht nötig: Der Pull Request kommt aus deinem Fork. CI prüft die Datei, ein Maintainer reviewed sie, und nach dem Merge baut die GitHub Action `registry.json` neu.

**Aktualisieren:** Version erhöhen und erneut veröffentlichen — der neue Pull Request ersetzt dieselbe Einreichung. **Unpublish** öffnet einen Pull Request zum Löschen; Repository und Releases bleiben online.

Ordner oder fertiges ZIP vor dem Veröffentlichen prüfen:

```bash
python -m workmods validate my-mod
python -m workmods validate-package dist/my-mod.zip --sha256 <erwarteter-hash>
```

Die Paketprüfung lehnt unsichere Archiveinträge, zu große Archive und eine falsche SHA-256 ab.

Ausführliche Anleitung: [docs/PUBLISHING.md](docs/PUBLISHING.md).

---

## Für Unity-Entwickler

Workmods ist nicht an ein bestimmtes Spiel gebunden: Ein Mod deklariert eine `game_id`, und das Spiel initialisiert das SDK mit derselben ID.

1. [`unity-sdk/WorkmodsSDK.cs`](unity-sdk/WorkmodsSDK.cs) nach `Assets/Workmods/` kopieren. Keine Pakete, keine Abhängigkeiten.
2. Inhaltsformat wählen:

| Format | Läuft auf | Geeignet für |
|---|---|---|
| **AssetBundles** (empfohlen) | Mono + IL2CPP, alle Plattformen | Prefabs, Texturen, Audio, ScriptableObjects |
| **Addressables** | Mono + IL2CPP | Projekte, die bereits Addressables nutzen |
| **DLL** | nur Mono | tiefe Gameplay-Mods |

3. Initialisieren und laden:

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

API: `GetInstalledMods()`, `GetInstalledMod(id)`, `IsInstalled(id)`, `LoadAssetBundle(...)`, `LoadAsset<T>(...)`, `TryLoadAssembly(...)`, `UnloadAssetBundle(id)`, `UnloadAll()`, `Rescan()`.

Das SDK protokolliert gefundene Mods, geladene Bundles und Fehler, wirft aber keine Ausnahmen in die Gameplay-Schleife. Mehr: [docs/UNITY_INTEGRATION.md](docs/UNITY_INTEGRATION.md).

---

## Register

`registry.json` wird ausschließlich von der GitHub Action erzeugt — nicht manuell bearbeiten. Schema v2 enthält `schema_version`, `games` und `mods`; jeder Mod hat `game_id`, `download_url`, `sha256` und Metadaten. Dokumente der Version 1 werden beim Lesen in das Profil `default` migriert.

Vollständige Feldreferenz und Einreichungsformat: [docs/REGISTRY_SCHEMA.md](docs/REGISTRY_SCHEMA.md).

---

## Entwicklung und Build

```bash
pip install -r requirements-dev.txt
pytest              # 66 Tests, kein Display nötig
ruff check workmods tests
```

Lokalen Standalone-Client bauen:

```bash
# Linux / macOS
pyinstaller --noconfirm --clean --onefile --windowed --name Workmods --add-data "data:data" main.py

# Windows (Semikolon bei --add-data beachten)
pyinstaller --noconfirm --clean --onefile --windowed --name Workmods --icon data/icon/app.ico --add-data "data;data" main.py
```

Die Ausgabe liegt in `dist/`. GitHub Actions baut Windows, Linux und macOS und veröffentlicht den Release über den Tag `v*`; Konfiguration: [.github/workflows/release.yml](.github/workflows/release.yml).

---

## Einschränkungen

Bewusste Grenzen von Version 1.0:

1. Veröffentlichung läuft über Pull Requests und manuelles Review; automatische Malware-Analyse gibt es noch nicht.
2. Keine automatischen Update-Hinweise, keine Abhängigkeitsauflösung und keine Ladereihenfolge zwischen Mods.
3. Große Dateien über die GitHub Contents API sind ungeeignet (etwa über 50–100 MB); dafür Release-Assets verwenden.
4. Das Unity-SDK unterstützt WebGL nicht.
5. SHA-256 sichert die Integrität, nicht das Vertrauen; Mod-Signaturen fehlen.

---

## Lizenz

MIT — siehe [LICENSE](LICENSE).
