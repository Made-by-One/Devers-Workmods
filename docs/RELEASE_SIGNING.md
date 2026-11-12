# Signing releases

Workmods publishes three platform archives plus two verification files:

| Asset | Purpose |
|---|---|
| `Workmods-windows-x86_64.zip` | Windows client |
| `Workmods-linux-x86_64.tar.gz` | Linux client |
| `Workmods-macos.zip` | macOS client |
| `SHA256SUMS` | SHA-256 for every archive |
| `SHA256SUMS.sig` | Detached signature over `SHA256SUMS` (optional) |

The release workflow always creates `SHA256SUMS`. It creates
`SHA256SUMS.sig` only when the `RELEASE_SIGNING_KEY` secret is configured, so
releases keep working when signing is not set up yet.

## Generate a key

Use an RSA key (3072 bits or stronger) or an ECDSA P-256 key:

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out release-key.pem
openssl rsa -in release-key.pem -pubout -out release-public-key.pem

# Store this value as a GitHub Actions secret.
base64 -w0 release-key.pem
```

On macOS use `base64 -i release-key.pem` instead of `base64 -w0`.

Keep `release-key.pem` offline. The public key is safe to commit or distribute.

## Configure the workflow

1. Open the repository → **Settings → Secrets and variables → Actions**.
2. Add `RELEASE_SIGNING_KEY` with the base64 output above.
3. Push a new version or run **Build Release** with `force` enabled.

The release job writes `SHA256SUMS`, signs it with OpenSSL, and uploads both files.
No private key is written to the repository or logs.

## Configure the client

The in-app updater verifies `SHA256SUMS` against the downloaded archive. To also
verify `SHA256SUMS.sig`, give the client the public key:

```bash
export WORKMODS_RELEASE_PUBLIC_KEY=/path/to/release-public-key.pem
```

`WORKMODS_RELEASE_PUBLIC_KEY` may be a file path or the PEM text itself. When it
is set, signature verification is required; a missing or invalid signature
aborts the update before anything is replaced. Without it, the client still
checks the SHA-256 but cannot establish who produced the checksums.

The CLI accepts the same key explicitly:

```bash
python -m workmods update check --public-key release-public-key.pem
python -m workmods update apply Workmods-linux-x86_64.tar.gz \
  --public-key release-public-key.pem --version 1.1d
```

## Verify manually

```bash
sha256sum -c SHA256SUMS
openssl dgst -sha256 -verify release-public-key.pem \
  -signature SHA256SUMS.sig SHA256SUMS
```

The first command checks the downloaded archives. The second proves that
`SHA256SUMS` was signed by the private key matching the public key you trust.

## Relation to platform code signing

Detached release signatures are separate from platform code signing:

- Windows Authenticode (`WINDOWS_CERTIFICATE_BASE64`) and macOS Developer ID
  (`MACOS_CERTIFICATE_BASE64` + notarization) prove the executable’s publisher to
  the operating system.
- `SHA256SUMS.sig` lets the updater verify the release metadata before replacing
  an executable, including on Linux where there is no Authenticode equivalent.

Configure both when distributing signed builds to players.
