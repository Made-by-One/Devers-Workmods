# ✦ Devers Workmods

**Un équivalent indépendant de Steam Workshop pour tous les jeux Unity — un atelier de mods qui appartient à la communauté.**

**Langues :** [English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Español](README.es.md) · Français · [中文](README.zh.md)

**Statut :** `v1.0b` — bêta publique avec un client redessiné. [Télécharger la première bêta](https://github.com/Made-by-One/Devers-Workmods/releases/tag/v1.0b) ou lire les [limites connues](#limites) avant de l’utiliser dans un vrai jeu.

Workmods repose sur trois éléments qui partagent un même format :

1. **Client de bureau** (Python + PyQt6) : les joueurs parcourent, installent, mettent à jour et suppriment les mods de chaque jeu.
2. **Registre public** (`registry.json`) reconstruit par GitHub Actions — sans serveur central ni dépendance à un fournisseur.
3. **SDK Unity** (`unity-sdk/WorkmodsSDK.cs`) : un seul fichier C# que le développeur du jeu ajoute pour découvrir et charger les mods.

Les mods restent dans le dépôt GitHub de l’auteur et sont distribués via GitHub Releases. Workmods ne stocke que les métadonnées.

```
Client Workmods ── ZIP + Release ──► dépôt du mod
       │
       └── pull request ────────────► submissions/ + GitHub Action
                                             │
                                             ▼
                                      registry.json
                                             │
                                             ▼
                                    catalogue du client
                                             │
                                             ▼
                              dossier des mods + SDK Unity
```

---

## Téléchargement

Les versions compilées sont publiées dans les [GitHub Releases](https://github.com/Made-by-One/Devers-Workmods/releases/tag/v1.0b) :

| Système | Archive |
|---|---|
| Windows x64 | `Workmods-windows-x86_64.zip` |
| Linux x86_64 | `Workmods-linux-x86_64.tar.gz` |
| macOS | `Workmods-macos.zip` |

Décompressez l’archive et lancez `Workmods.exe`, `Workmods` ou `Workmods.app`. Python et PyQt6 sont inclus. La version macOS n’est pas signée : au premier lancement, utilisez **Clic droit → Ouvrir**. Windows SmartScreen peut également afficher un avertissement.

---

## Pour les joueurs

### Lancer depuis les sources

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

1. Ouvrez **Settings → Game Profiles → Add Game** et renseignez le `game_id`, le nom affiché et le dossier d’installation (par exemple `~/DeversMods/space-rangers`).
2. Choisissez un jeu dans le filtre **Catalog** — seuls les mods portant ce `game_id` apparaissent.
3. Cliquez sur **Install**. Le client télécharge le ZIP de la release, vérifie son SHA-256 par rapport au registre et extrait le mod dans `<dossier d’installation>/<modId>/`.
4. Indiquez ce dossier au jeu. Le SDK Unity utilise par défaut `Application.persistentDataPath/Workmods`.

Les mods installés sont regroupés par jeu. **Delete** supprime uniquement le dossier du mod. Pour mettre à jour, réinstallez : l’ancien dossier est remplacé de façon atomique.

---

## Pour les créateurs de mods

Un compte GitHub est nécessaire. Workmods crée et remplit le dépôt à votre place — aucune manipulation manuelle de git.

1. **Préparez le dossier du mod :** fichiers `.bundle` (recommandé), sortie Addressables ou DLL. Ajoutez si vous le souhaitez un `workmod.json` :

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

2. Connectez-vous dans **Author Studio** via GitHub OAuth.
3. Cliquez sur **New Repo**, créez un dépôt public et sélectionnez-le dans l’éditeur.
4. Renseignez le nom, la version, la description, le jeu cible, éventuellement l’icône et la bannière, puis choisissez le dossier des fichiers.
5. Cliquez sur **Publish & Request Addition**. Le client crée un ZIP, calcule le SHA-256, publie la release dans votre dépôt et ouvre une pull request avec `submissions/<game_id>/<mod_id>.json`.

Aucun droit d’écriture sur le registre n’est nécessaire : la pull request vient de votre fork. La CI valide le fichier, un mainteneur le relit et, après le merge, la GitHub Action reconstruit `registry.json`.

**Mise à jour :** augmentez la version et republiez — la nouvelle pull request remplace la même soumission. **Unpublish** ouvre une pull request de suppression ; votre dépôt et vos releases restent en ligne.

Guide complet : [docs/PUBLISHING.md](docs/PUBLISHING.md).

---

## Pour les développeurs Unity

Workmods n’est lié à aucun jeu en particulier : un mod déclare un `game_id` et le jeu initialise le SDK avec le même identifiant.

1. Copiez [`unity-sdk/WorkmodsSDK.cs`](unity-sdk/WorkmodsSDK.cs) dans `Assets/Workmods/`. Aucun paquet, aucune dépendance.
2. Choisissez le format du contenu :

| Format | Fonctionne sur | Idéal pour |
|---|---|---|
| **AssetBundles** (recommandé) | Mono + IL2CPP, toutes plateformes | prefabs, textures, audio, ScriptableObjects |
| **Addressables** | Mono + IL2CPP | projets utilisant déjà Addressables |
| **DLL** | Mono uniquement | mods de gameplay avancés |

3. Initialisez et chargez :

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

API : `GetInstalledMods()`, `GetInstalledMod(id)`, `IsInstalled(id)`, `LoadAssetBundle(...)`, `LoadAsset<T>(...)`, `TryLoadAssembly(...)`, `UnloadAssetBundle(id)`, `UnloadAll()`, `Rescan()`.

Le SDK journalise les mods trouvés, les bundles chargés et les erreurs, mais ne lance jamais d’exception dans la boucle du jeu. Détails : [docs/UNITY_INTEGRATION.md](docs/UNITY_INTEGRATION.md).

---

## Registre

`registry.json` est généré uniquement par la GitHub Action — ne le modifiez pas à la main. Le schéma v2 contient `schema_version`, `games` et `mods` ; chaque mod possède `game_id`, `download_url`, `sha256` et ses métadonnées. Les documents de version 1 sont migrés vers le profil `default` à la lecture.

Référence complète des champs et format des soumissions : [docs/REGISTRY_SCHEMA.md](docs/REGISTRY_SCHEMA.md).

---

## Développement et compilation

```bash
pip install -r requirements-dev.txt
pytest              # 59 tests, aucun écran requis
ruff check workmods tests
```

Compiler le client autonome en local :

```bash
# Linux / macOS
pyinstaller --noconfirm --clean --onefile --windowed --name Workmods --add-data "data:data" main.py

# Windows (attention au point-virgule dans --add-data)
pyinstaller --noconfirm --clean --onefile --windowed --name Workmods --icon data/icon/app.ico --add-data "data;data" main.py
```

Le résultat se trouve dans `dist/`. GitHub Actions compile Windows, Linux et macOS et publie la release avec le tag `v*` ; configuration : [.github/workflows/release.yml](.github/workflows/release.yml).

---

## Limites

Limites assumées de la version 1.0 :

1. La publication passe par une pull request et une revue manuelle ; pas encore d’analyse automatique des malwares.
2. Pas de notification de mise à jour, de résolution de dépendances ni d’ordre de chargement entre mods.
3. Les gros fichiers via l’API Contents de GitHub ne conviennent pas (environ au-delà de 50–100 Mo) ; utilisez les assets de release.
4. Le SDK Unity ne prend pas en charge WebGL.
5. SHA-256 garantit l’intégrité, pas la confiance ; les mods ne sont pas signés.

---

## Licence

MIT — voir [LICENSE](LICENSE).
