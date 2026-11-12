# Security notes

Workmods distributes and executes user-generated content, and ships an OAuth
client plus a registry bot. This document is the honest threat model and the
release checklist.

## Secrets in this repository

| Secret | Where it is used | Status |
|---|---|---|
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | OAuth token exchange in the desktop client | Default value is committed in `workmods/config.py` |

A desktop application cannot keep an OAuth **client secret** confidential: anyone
can extract it from the binary or source. GitHub's device/browser flow for public
clients is still safe enough for a user-facing app *only* when the secret is
treated as public and there is no privileged backend behind it.

There is **no shared registry secret** anymore. Publishing works through a pull
request from the author's fork, so the registry never has to accept an
authenticated write from an anonymous client.

### Required before a public release

1. **Rotate the OAuth client secret.** GitHub → Settings → Developer settings →
   OAuth Apps → your app → generate a new client secret; keep the callback URL at
   `http://localhost:8080`.
2. **Do not bake new values into the source.** Provide them through the
   environment: `WORKMODS_GITHUB_CLIENT_ID`, `WORKMODS_GITHUB_CLIENT_SECRET`,
   `WORKMODS_REGISTRY_REPO`, `WORKMODS_REGISTRY_BRANCH`.
3. Keep branch protection on `main` with the **Validate Submission** check
   required, so no submission reaches the registry without validation.

## Publishing model and access control

```
publisher (fork) ──push branch──► pull request ──► Validate Submission (read-only)
                                        │
                                        ▼
                             maintainer review + merge
                                        │
                                        ▼
                        Rebuild Mod Registry (GITHUB_TOKEN, contents: write)
```

Consequences:

- **No registry credentials reach the client.** The author's token is used only
  on repositories they own plus their own fork; the fork is created by GitHub
  under their account.
- **Review is the gate.** CI checks structure, not intent. A malicious mod can
  still have a valid schema, a valid hash and a working download URL. A maintainer
  must look at the repository and the release before merging.
- **Merge rights are the access control.** Only maintainers can merge, so the
  registry cannot be modified by a submission alone.
- **Identity.** The submission records `submitted_by` from the authenticated
  GitHub login, and the pull request shows the fork owner. That is a weak identity
  claim, good enough for moderation, not for ownership disputes.
- **Mod id squatting.** Ids are global and lower-case. If two people submit the
  same `<game>/<id>.json`, the second pull request conflicts; the maintainer
  decides. There is no cryptographic proof that the id belongs to a repository.

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

## GitHub Actions

- `validate_submission.yml` runs on `pull_request` with `contents: read` only. It
  never checks out a privileged token and never executes submission content —
  submission files are parsed as data.
- `rebuild_registry.yml` runs on `push` to `main` (and manual dispatch) with
  `contents: write`, uses the default `GITHUB_TOKEN`, serialises runs with
  `concurrency`, and stages only `registry.json`.
- The bot rejects unknown fields, so a submission file cannot smuggle extra data
  (or a leaked secret) into the public registry.
- Pull requests are never auto-merged. Validation failing is a hard error, not a
  warning.

## Reporting

Open a private security advisory on the repository rather than a public issue for
anything involving credential exposure or mod-code execution.
