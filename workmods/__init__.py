"""Workmods — an independent, game-agnostic mod distribution client.

The package is split into small, independently testable layers:

    config.py    application settings + paths + credentials
    models.py    plain data objects (Game, Mod, InstalledMod)
    storage.py   filesystem work: packaging, hashing, safe install, scanning
    github_api.py  thin, Qt-free GitHub REST client
    publisher.py   publish/unpublish orchestration (zip -> repo -> release -> registry)
    registry.py    registry parsing, validation and filtering by game
    i18n.py      localization
    net.py       Qt network adapter for the registry
    ui/          PyQt6 widgets (no business logic beyond presentation)

Only the ``ui`` subpackage imports PyQt6, so everything else can be reused in a
CLI, a server job or a test without a display.
"""

from workmods.config import APP_NAME, APP_VERSION

__all__ = ["APP_NAME", "APP_VERSION"]
