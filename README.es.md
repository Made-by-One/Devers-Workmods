# ✦ Devers Workmods

**Un análogo independiente de Steam Workshop para cualquier juego de Unity: un taller de mods que pertenece a la comunidad.**

**Idiomas:** [English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · Español · [Français](README.fr.md) · [中文](README.zh.md)

**Estado:** `v1.1b` — beta pública con el cliente rediseñado. [Descargar la última beta](https://github.com/Made-by-One/Devers-Workmods/releases/tag/v1.1b) o consultar las [limitaciones conocidas](#limitaciones) antes de usarlo en un juego real.

Workmods son tres piezas que comparten un mismo formato:

1. **Cliente de escritorio** (Python + PyQt6): los jugadores exploran, instalan, actualizan y eliminan mods por juego.
2. **Registro público** (`registry.json`) reconstruido por GitHub Actions, sin servidor central ni dependencia de un proveedor.
3. **SDK de Unity** (`unity-sdk/WorkmodsSDK.cs`): un único archivo C# que el desarrollador del juego añade para descubrir y cargar los mods.

Los mods viven en el repositorio de GitHub del autor y se distribuyen mediante GitHub Releases. Workmods solo almacena metadatos.

```
Cliente Workmods ── ZIP + Release ──► repositorio del mod
       │
       └── pull request ────────────► submissions/ + GitHub Action
                                             │
                                             ▼
                                      registry.json
                                             │
                                             ▼
                                    catálogo del cliente
                                             │
                                             ▼
                              carpeta de mods + SDK de Unity
```

---

## Descargar

Las compilaciones se publican en [GitHub Releases](https://github.com/Made-by-One/Devers-Workmods/releases/tag/v1.1b):

| Sistema | Archivo |
|---|---|
| Windows x64 | `Workmods-windows-x86_64.zip` |
| Linux x86_64 | `Workmods-linux-x86_64.tar.gz` |
| macOS | `Workmods-macos.zip` |

Descomprime el archivo y ejecuta `Workmods.exe`, `Workmods` o `Workmods.app`. Python y PyQt6 están incluidos. La compilación de macOS no está firmada: en el primer inicio usa **Clic derecho → Abrir**. Windows SmartScreen puede mostrar una advertencia similar.

---

## Para jugadores

### Ejecutar desde el código fuente

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

1. Abre **Settings → Game Profiles → Add Game** y define el `game_id`, el nombre y la carpeta de instalación (por ejemplo, `~/DeversMods/space-rangers`).
2. Elige un juego en el filtro **Catalog**: solo aparecen los mods con ese `game_id`.
3. Pulsa **Install**. El cliente descarga el ZIP del Release, comprueba su SHA-256 contra el registro y extrae el mod en `<carpeta de instalación>/<modId>/`.
4. Indica esa carpeta al juego. El SDK de Unity usa por defecto `Application.persistentDataPath/Workmods`.

Los mods instalados se agrupan por juego. **Delete** elimina únicamente la carpeta del mod. Para actualizar, instala de nuevo: la carpeta anterior se reemplaza de forma atómica.

---

## Para creadores de mods

Necesitas una cuenta de GitHub. Workmods crea y llena el repositorio por ti; no tienes que usar git manualmente.

1. **Prepara la carpeta del mod:** archivos `.bundle` (recomendado), la salida de Addressables o DLL. Opcionalmente añade `workmod.json`:

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

2. Inicia sesión en **Author Studio** con GitHub OAuth.
3. Pulsa **New Repo**, crea un repositorio público y selecciónalo en el editor.
4. Completa nombre, versión, descripción, juego objetivo y, si quieres, icono y banner; elige la carpeta de archivos.
5. Pulsa **Publish & Request Addition**. El cliente empaqueta los archivos en un ZIP, calcula el SHA-256, sube el release a tu repositorio y abre un pull request con `submissions/<game_id>/<mod_id>.json`.

No necesitas permiso de escritura en el registro: el pull request sale de tu fork. CI valida el archivo, un mantenedor lo revisa y, tras el merge, la GitHub Action reconstruye `registry.json`.

**Actualizar:** sube la versión y publica de nuevo; el nuevo pull request reemplaza la misma solicitud. **Unpublish** abre un pull request para eliminarla; tu repositorio y tus releases siguen disponibles.

Comprueba la carpeta o el ZIP final antes de publicar:

```bash
python -m workmods validate my-mod
python -m workmods validate-package dist/my-mod.zip --sha256 <hash-esperado>
```

La validación del paquete rechaza entradas de archivo inseguras, archivos demasiado grandes y un SHA-256 incorrecto.

Guía completa: [docs/PUBLISHING.md](docs/PUBLISHING.md).

---

## Para desarrolladores de Unity

Workmods no está atado a un juego concreto: el mod declara un `game_id` y el juego inicializa el SDK con ese mismo id.

1. Copia [`unity-sdk/WorkmodsSDK.cs`](unity-sdk/WorkmodsSDK.cs) en `Assets/Workmods/`. No requiere paquetes ni dependencias.
2. Elige el formato del contenido:

| Formato | Funciona en | Ideal para |
|---|---|---|
| **AssetBundles** (recomendado) | Mono + IL2CPP, todas las plataformas | prefabs, texturas, audio, ScriptableObjects |
| **Addressables** | Mono + IL2CPP | proyectos que ya usan Addressables |
| **DLL** | solo Mono | mods de jugabilidad profundos |

3. Inicializa y carga:

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

El SDK registra los mods encontrados, los bundles cargados y los errores, pero nunca lanza excepciones al bucle del juego. Más información: [docs/UNITY_INTEGRATION.md](docs/UNITY_INTEGRATION.md).

---

## Registro

`registry.json` solo lo genera la GitHub Action; no lo edites a mano. El esquema v2 contiene `schema_version`, `games` y `mods`; cada mod tiene `game_id`, `download_url`, `sha256` y metadatos. Los documentos de la versión 1 se migran al perfil `default` al leerse.

Referencia completa de campos y formato de solicitud: [docs/REGISTRY_SCHEMA.md](docs/REGISTRY_SCHEMA.md).

---

## Desarrollo y compilación

```bash
pip install -r requirements-dev.txt
pytest              # 81 pruebas, no requiere pantalla
ruff check workmods tests
```

Compilar el cliente independiente en local:

```bash
# Linux / macOS
pyinstaller --noconfirm --clean --onefile --windowed --name Workmods --add-data "data:data" main.py

# Windows (ojo con el punto y coma en --add-data)
pyinstaller --noconfirm --clean --onefile --windowed --name Workmods --icon data/icon/app.ico --add-data "data;data" main.py
```

El resultado queda en `dist/`. GitHub Actions compila Windows, Linux y macOS y publica el release con la etiqueta `v*`; configuración: [.github/workflows/release.yml](.github/workflows/release.yml).

---

## Limitaciones

Límites deliberados de la versión 1.0:

1. La publicación es por pull request y revisión manual; todavía no hay análisis automático de malware.
2. No hay avisos automáticos de actualización, resolución de dependencias ni orden de carga entre mods.
3. Los archivos grandes mediante la API de contenidos de GitHub no son adecuados (aproximadamente por encima de 50–100 MB); usa assets de release.
4. El SDK de Unity no admite WebGL.
5. SHA-256 garantiza integridad, no confianza; no hay firma de mods.

---

## Licencia

MIT — consulta [LICENSE](LICENSE).
