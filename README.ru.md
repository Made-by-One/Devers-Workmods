# ✦ Devers Workmods

**Независимый аналог Steam Workshop для любых Unity-игр — реестр модов, которым владеет сообщество.**

**Языки:** [English](README.md) · Русский · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md) · [中文](README.zh.md)

**Статус:** `v1.2b` — публичная бета с обновлённым клиентом. [Скачать последнюю бету](https://github.com/Made-by-One/Devers-Workmods/releases/tag/v1.2b) или прочитать [известные ограничения](#ограничения) перед использованием в реальной игре.

Workmods — это три части одного формата:

1. **Десктопный клиент** на Python + PyQt6: игроки просматривают, устанавливают, обновляют и удаляют моды для каждой игры.
2. **Публичный реестр** (`registry.json`), который пересобирается через GitHub Actions. Без центрального сервера и привязки к вендору.
3. **Unity SDK** (`unity-sdk/WorkmodsSDK.cs`) — один C#-файл, который разработчик игры добавляет в проект, чтобы находить и загружать моды.

Моды лежат в GitHub-репозитории автора и распространяются через GitHub Releases. Workmods хранит только метаданные.

```
клиент Workmods ── ZIP + Release ──► репозиторий мода
       │
       └── pull request ───────────► submissions/ + GitHub Action
                                             │
                                             ▼
                                      registry.json
                                             │
                                             ▼
                                    каталог в клиенте
                                             │
                                             ▼
                              папка модов + Unity SDK
```

---

## Скачать

Готовые сборки публикуются в [GitHub Releases](https://github.com/Made-by-One/Devers-Workmods/releases/tag/v1.2b):

| Система | Архив |
|---|---|
| Windows x64 | `Workmods-windows-x86_64.zip` |
| Linux x86_64 | `Workmods-linux-x86_64.tar.gz` |
| macOS | `Workmods-macos.zip` |

Распакуйте архив и запустите `Workmods.exe`, `Workmods` или `Workmods.app`. Python и PyQt6 уже включены. Сборка для macOS не подписана: при первом запуске используйте **ПКМ → Открыть**. Windows SmartScreen может показать аналогичное предупреждение.

### Что нового в 1.2b

- **Настройки → Обновления приложения**: проверка GitHub Release, проверка `SHA256SUMS` и подписи, атомарная установка и откат к резервной копии.
- **Установленные → Профиль модов**: наборы включённых/отключённых модов, пресеты настроек, применение через `.workmods-disabled`, экспорт и импорт JSON.
- Релизы содержат `SHA256SUMS` и, если настроен секрет подписи, `SHA256SUMS.sig`. Подробнее: [docs/RELEASE_SIGNING.md](docs/RELEASE_SIGNING.md).
- Сборка для Linux собирается на Ubuntu 22.04, поэтому запускается на Ubuntu 24.04 и системах с glibc 2.35+.
- Редактор мода не сдвигает интерфейс из-за длинных имён файлов иконок/баннеров и теперь поддерживает GIF-иконки и баннеры, включая анимированные обложки в каталоге.

---

## Игрокам

### Запуск из исходников

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

1. Откройте **Settings → Game Profiles → Add Game** и укажите `game_id`, название и папку установки (например, `~/DeversMods/space-rangers`).
2. Выберите игру в фильтре **Catalog** — показываются только моды с этим `game_id`.
3. Нажмите **Install**. Клиент скачает ZIP из Release, проверит SHA-256 по реестру и распакует мод в `<папка установки>/<modId>/`.
4. Укажите эту папку игре. Unity SDK по умолчанию использует `Application.persistentDataPath/Workmods`.

Установленные моды показываются по играм. **Delete** удаляет только папку мода. Для обновления установите мод заново — старая папка заменяется атомарно.

---

## Мододелам

Нужен аккаунт GitHub. Workmods сам создаёт и заполняет репозиторий — работать с git вручную не требуется.

1. **Подготовьте папку мода:** `.bundle`-файлы (рекомендуется), результат Addressables или DLL. Рядом можно положить `workmod.json`:

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

2. Войдите в **Author Studio** через GitHub OAuth.
3. Нажмите **New Repo**, создайте публичный репозиторий и выберите его в редакторе.
4. Заполните название, версию, описание, целевую игру, при необходимости добавьте иконку и баннер, выберите папку с файлами.
5. Нажмите **Publish & Request Addition**. Клиент упакует файлы в ZIP, посчитает SHA-256, загрузит релиз в ваш репозиторий и откроет pull request с файлом `submissions/<game_id>/<mod_id>.json`.

Права на запись в реестр не нужны: pull request создаётся из вашего форка. CI проверит файл, мейнтейнер рассмотрит изменение, а после merge GitHub Action пересоберёт `registry.json`.

**Обновление:** поднимите версию и опубликуйте снова — новый pull request заменит тот же файл заявки. **Unpublish** открывает pull request на удаление заявки; репозиторий и релизы мода остаются доступны.

Проверка папки или финального ZIP перед публикацией:

```bash
python -m workmods validate my-mod
python -m workmods validate-package dist/my-mod.zip --sha256 <ожидаемый-хэш>
```

Проверка пакета отклоняет небезопасные записи архива, слишком большие архивы и несовпадение SHA-256.

Подробный гайд: [docs/PUBLISHING.md](docs/PUBLISHING.md).

---

## Разработчикам Unity-игр

Workmods не привязан к конкретной игре: мод объявляет `game_id`, а игра инициализирует SDK с тем же id.

1. Скопируйте [`unity-sdk/WorkmodsSDK.cs`](unity-sdk/WorkmodsSDK.cs) в `Assets/Workmods/`. Пакеты и зависимости не нужны.
2. Выберите формат контента:

| Формат | Где работает | Для чего |
|---|---|---|
| **AssetBundles** (рекомендуется) | Mono + IL2CPP, все платформы | префабы, текстуры, звук, ScriptableObject |
| **Addressables** | Mono + IL2CPP | проекты, которые уже используют Addressables |
| **DLL** | только Mono | глубокие геймплейные моды |

3. Инициализация и загрузка:

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

SDK логирует найденные моды, загруженные бандлы и ошибки, но никогда не выбрасывает исключения в игровой цикл. Подробнее: [docs/UNITY_INTEGRATION.md](docs/UNITY_INTEGRATION.md).

---

## Реестр

`registry.json` генерируется только GitHub Action — не редактируйте его вручную. Схема v2 содержит `schema_version`, `games` и `mods`; у каждого мода есть `game_id`, `download_url`, `sha256` и метаданные. Документы версии 1 мигрируются при чтении в профиль `default`.

Полное описание полей и формат заявки: [docs/REGISTRY_SCHEMA.md](docs/REGISTRY_SCHEMA.md).

---

## Разработка и сборка

```bash
pip install -r requirements-dev.txt
pytest              # 84 теста, дисплей не нужен
ruff check workmods tests
```

Локальная сборка standalone-клиента:

```bash
# Linux / macOS
pyinstaller --noconfirm --clean --onefile --windowed --name Workmods --add-data "data:data" main.py

# Windows (обратите внимание на точку с запятой)
pyinstaller --noconfirm --clean --onefile --windowed --name Workmods --icon data/icon/app.ico --add-data "data;data" main.py
```

Результат появится в `dist/`. GitHub Actions собирает Windows, Linux и macOS и публикует релиз по тегу `v*`; конфигурация — [.github/workflows/release.yml](.github/workflows/release.yml).

---

## Ограничения

Это осознанные границы версии 1.0:

1. Публикация идёт через pull request и ручное ревью; автоматического анализа вредоносного кода пока нет.
2. Нет автоматических уведомлений об обновлениях, графа зависимостей и порядка загрузки модов.
3. Большие файлы через GitHub Contents API нежелательны (примерно до 50–100 МБ); для тяжёлого контента используйте release asset.
4. Unity SDK не поддерживает WebGL.
5. SHA-256 подтверждает целостность, но не доверие к моду; подписи модов нет.

---

## Лицензия

MIT — см. [LICENSE](LICENSE).
