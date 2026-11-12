# Mod submissions

`registry.json` is generated from this directory — do not edit it by hand. Each
mod is one file:

```
submissions/<game_id>/<mod_id>.json
```

`<mod_id>` must match `id` inside the file and letters are lower-case. One id
belongs to one game and one repository.

## File format

```json
{
  "id": "a1b2c3d4",
  "game_id": "space-rangers",
  "name": "Neon UI",
  "version": "1.2.0",
  "author": "your-handle",
  "description": "Neon HUD replacement for the tactical screen.",
  "repo": "your-handle/workmods-neon-ui",
  "download_url": "https://github.com/your-handle/workmods-neon-ui/releases/download/v1.2.0/a1b2c3d4.zip",
  "sha256": "9f2c...64 hex characters...",
  "entry_asset": "NeonHud",
  "tags": ["ui", "hud"],
  "icon_url": "https://raw.githubusercontent.com/your-handle/workmods-neon-ui/main/icon.png",
  "banner_url": "",
  "updated_at": "2026-11-12T00:00:00+00:00",
  "submitted_by": "your-handle"
}
```

The Workmods client generates this file automatically when the author clicks
**Publish**, so manual editing is only needed for maintenance.

## Review flow

1. The client uploads the mod to the author's repository and creates a release.
2. It opens a pull request that adds this file (or replaces it for a new version).
3. CI runs `python .github/scripts/update_registry.py validate` on the pull request.
4. A maintainer checks the repository contents and the metadata, then merges.
5. The **Rebuild Mod Registry** workflow regenerates `registry.json` from all
   submission files and commits it. Clients see the mod after the next refresh.

## Removing a mod

Delete its submission file in a pull request. The client's **Unpublish** button
does this for you. The author's repository and release are not touched.

## Validation rules

- `id`, `game_id`, `name`, `version`, `repo`, `download_url`, `sha256` are required.
- `id` is 2–64 characters: lower-case letters, digits, `.`, `_`, `-`.
- The file path must match the metadata: `submissions/<game_id>/<id>.json`.
- `sha256` is the SHA-256 of the release ZIP, 64 lower-case hex characters.
- `download_url` must be an `https://github.com/.../releases/download/...` URL.
- `icon_url` / `banner_url` are optional and must be GitHub `https` URLs.
- Unknown fields are rejected, so a submission file cannot smuggle extra data
  into the registry.
- Duplicate ids across games are rejected.
