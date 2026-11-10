# Security notes

Workmods distributes and executes user-generated content, and ships an OAuth
client plus a registry bot. This document is the honest threat model and the
release checklist.

## Secrets in this repository

| Secret | Where it is used | Status |
|---|---|---|
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | OAuth token exchange in the desktop client | Default value is committed in `workmods/config.py` |
| `BOT_SECRET` | Authenticates `add_mod` / `remove_mod` dispatches | Default value is committed in `workmods/config.py` |
| `BOT_SECRET_TOKEN` | GitHub Actions secret compared by the workflow | Repository secret |

A desktop application cannot keep an OAuth **client secret** confidential: anyone
can extract it from the binary or source. GitHub's OAuth flow for public clients
is still safe enough for a user-facing app *only* when the secret is treated as
public and the app has no privileged backend. The registry bot secret has the same
property.

### Required before a public v1.0 release

1. **Rotate both defaults.**
   - GitHub → Settings → Developer settings → OAuth Apps → your app → generate a
     new client secret; set the callback URL to `http://localhost:8080`.
   - Update the repository secret `BOT_SECRET_TOKEN` (Settings → Secrets and
     variables → Actions) and the value the client sends.
2. **Do not bake new secrets into the source.** Provide them through the
   environment:
   - `WORKMODS_GITHUB_CLIENT_ID`
   - `WORKMODS_GITHUB_CLIENT_SECRET`
   - `WORKMODS_BOT_SECRET`
   - `WORKMODS_REGISTRY_REPO` / `WORKMODS_REGISTRY_BRANCH`
3. Understand that the bot secret is **defence in depth, not access control**.
   The real gate for `repository_dispatch` is GitHub's permission model: the
   caller must have write access to the registry repository. Anybody who can
   publish already has that access; the shared secret only prevents accidental or
   naive writes (and produces a clear failure in the Action log).

## Publishing model and access control

```
modder's token ──► POST /repos/<registry>/dispatches  ──► GitHub requires write access
```

Consequences:

- **Curated workshop (current):** add trusted modders as collaborators on the
  registry repository. The secret is redundant but harmless.
- **Open workshop (not implemented):** a client cannot hold a token with write
  access to a shared registry. Options for the next version:
  1. publish through pull requests from the modder's fork, with the Action
     validating and merging (no secret in the client);
  2. a small GitHub App / serverless proxy that holds a scoped installation token
     and authenticates users via their GitHub identity;
  3. one registry repository per game, owned by that game's developer.

  Until then, document the collaborator requirement clearly instead of pretending
  open publishing works.

## Token at rest

- The OAuth token is written to `~/.devers_workmods/config.json` in plain text.
  The client requests the `repo` scope because it must create repositories and
  releases. Users should treat that file as a credential and not sync it.
- Recommended future hardening: OS keyring (`keyring` package) with the config
  file storing only a reference.

## Mod integrity and trust

- The client verifies SHA-256 from the registry **after** download, before
  extraction. The install is atomic; a failed check leaves nothing installed.
- SHA-256 proves the file matches what the registry advertised. It does **not**
  make the mod trustworthy. A malicious author can publish a malicious hash.
- ZIP extraction rejects path traversal entries and mod ids containing separators.
- Mod folders are replaced only after successful extraction; deletion is confined
  to `<install_dir>/<mod_id>`.
- Games should treat mods as untrusted input, prefer AssetBundles over DLLs, and
  never run mod code with more privilege than the game itself has.

## GitHub Action

- `update_registry.py` compares the secret with `hmac.compare_digest`.
- Payload fields are whitelisted; `secret` is dropped before writing
  `registry.json`, so the public registry cannot leak it.
- A wrong/missing secret fails the job (exit 1) instead of silently succeeding.
- `concurrency` serialises updates; only `registry.json` is staged.
- The workflow uses the default `GITHUB_TOKEN` with `contents: write`, no
  personal token.

## Reporting

Open a private security advisory on the repository rather than a public issue for
anything involving credential exposure or mod-code execution.
