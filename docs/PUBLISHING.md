# Publishing a mod

This is the modder's manual. You need a GitHub account; you do **not** need git,
a terminal or a server.

> **Access requirement:** publishing sends a `repository_dispatch` to the registry
> repository, and GitHub only accepts that from a user with **write access** to
> that repository. On a self-hosted registry add publishers as collaborators (or
> let them publish through your fork/PR flow). See
> [Known limitations](../README.md#known-limitations-before-public-launch).

## 1. Prepare the mod

A mod is a folder. Its contents are exactly what the game's SDK will see.

```
neon-ui/
├── workmod.json
├── neon-ui.bundle
└── bundles/
    └── shared.bundle
```

Guidelines:

- **Game id** must match what the game passes to `WorkmodsSDK.Initialize`.
  Ask the game developer or read their docs.
- **AssetBundles** are the recommended format. Build for the platform(s) players
  use; a bundle is not portable between platforms.
- Keep **dependencies inside the mod** (shared bundles, textures) — the SDK loads
  all bundles of a mod together.
- Don't publish `.devers_meta.json`, caches or source folders; the client strips
  `.devers_meta.json`, `.git`, `__pycache__`, `.DS_Store` and `Thumbs.db`
  automatically, but keep the folder clean anyway.

`workmod.json`:

```json
{
  "id": "a1b2c3d4",
  "game_id": "space-rangers",
  "name": "Neon UI",
  "version": "1.2.0",
  "author": "your-handle",
  "description": "Neon HUD replacement for the tactical screen.",
  "entry_asset": "NeonHud",
  "bundles": ["neon-ui.bundle", "bundles/shared.bundle"],
  "tags": ["ui", "hud"]
}
```

Everything except the content itself is optional, but `name` and `version` are
required by the client when publishing.

## 2. Create the repository

1. Start Workmods, open **Author Studio**.
2. **Login via GitHub** → a browser window opens; approve the `repo` scope.
3. **New Repo** → enter a name, for example `workmods-neon-ui`. Workmods creates a
   public repository (with an initial commit, so releases work immediately).

You can also use an existing repository — it appears in the repository dropdown.

## 3. Create the mod entry

1. **Create** opens the editor.
2. Mod ID is generated (8 characters). **Never change it between versions** —
   it is the identity used by players, the registry and the SDK.
3. Fill in:
   - **Target Game** — pick a configured profile or type the game id;
   - **Mod Name**, **Version**, **Author**, **Description**;
   - **Icon / Banner** — PNG/JPG, uploaded to the repo root as
     `icon.png` / `banner.png`;
   - **Entry Asset** — optional default asset name the game can load;
   - **Tags** — comma separated, searchable;
   - **Files Folder** — the folder prepared in step 1.
4. **Save Mod** writes a local draft to the selected game's install folder. You can
   install and test it in-game before publishing.

## 4. Publish

Click **Publish & Request Addition**. Workmods then:

1. zips the folder (root = mod folder, no wrapper directory);
2. computes SHA-256;
3. uploads every file to the repository (default branch) and the icon/banner;
4. creates/uses release `v<version>` and uploads `<modId>.zip`;
5. dispatches `add_mod` to the registry repository.

The GitHub Action validates the shared secret, writes/updates the entry in
`registry.json` and commits it. The catalog refresh may take a minute because
`raw.githubusercontent.com` is CDN-cached — press **Refresh** again a bit later.

### Versioning

- `1.0.0`, `1.2.0`, `2.0.0-beta.1` — anything without spaces or slashes.
- The tag is always `v<version>`. Publishing twice with the same version reuses the
  release and replaces the asset (the old asset is deleted first).
- Use a new version for every update; the client always downloads the URL from the
  registry, which points at its version's tag.

### Updating

Open the mod → **Edit** → bump the version → **Publish**. The registry entry is
replaced by id, so players see one entry, not two.

## 5. Unpublish

**Unpublish** removes the entry from `registry.json`. Your repository, files and
releases stay online — existing players keep their local copy. Re-publish to
restore it.

## Limits and failure modes

| Symptom | Meaning | Fix |
|---|---|---|
| `GitHub API 401` | Token missing/expired | Log out and log in again. |
| `GitHub API 403` | Token lacks write access to the target repo, or a rate limit | Re-login; check repository permissions. |
| `GitHub API 404` | Repository not found or no access | Pick another repository in the editor. |
| `GitHub API 422` | Release/tag rejected, or a file too large | Use a new version; see the size limit below. |
| `Registry rejected: 404` | Your account has no write access to the registry repository | Ask the registry owner for access (required for `repository_dispatch`). |
| Registry entry never appears | The Action failed | Open the registry repository → **Actions** → *Update Mod Registry* and read the log. |
| `Checksum mismatch` for players | The uploaded asset changed after publishing (e.g. release asset replaced manually) | Publish again so the SHA-256 matches. |

**File size:** the client uploads mod files through the GitHub Contents API, which
is unsuitable for very large files (GitHub rejects files over 100 MB, and the API
is not a CDN). Keep individual files well below that; the release ZIP itself can
be up to 2 GB. For huge content, publish the release manually and open a PR that
adds the registry entry.

**Repository contents:** every published file is committed to the mod repository,
so players and the game developer can inspect what a mod ships. That is
intentional.

## Checklist before you hit publish

- [ ] `game_id` matches the game exactly.
- [ ] Bundles built for the right platform, LZ4 compression for mobile.
- [ ] `workmod.json` lists bundles when names are ambiguous.
- [ ] Version bumped, mod id unchanged.
- [ ] Mod tested locally in the game.
- [ ] Icon/banner look right (they are cached by players' clients).
- [ ] No secrets, personal data or copyrighted assets you cannot redistribute.
