# Sample mod

This is a minimal mod package for testing `WorkmodsSDK` and the package validator.
It is **not** a real Unity AssetBundle; replace `sample.bundle` with a bundle built
for your target platform before using it in a game.

Validate it locally:

```bash
python -m workmods validate unity-sdk/examples/sample-mod
python -m workmods validate-package unity-sdk/examples/sample-mod
```

Pack it exactly like the publisher does:

```bash
python -m workmods pack unity-sdk/examples/sample-mod
```
