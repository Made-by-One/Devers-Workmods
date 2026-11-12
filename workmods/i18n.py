"""Localization helpers.

Translation files are plain JSON in ``data/localization/<lang>.json``. Missing
keys fall back to the English file and then to the literal default passed by the
caller, so adding a language never requires translating everything at once.
"""

from __future__ import annotations

import json
import locale
import os
from pathlib import Path

from workmods.config import DATA_DIR

FALLBACK_LANGUAGE = "en"

# Native names shown in the language picker. The file name is the language code
# stored in the configuration.
LANGUAGE_NAMES = {
    "en": "English",
    "ru": "Русский",
    "de": "Deutsch",
    "es": "Español",
    "fr": "Français",
    "zh": "中文 (简体)",
}


def localization_dir() -> Path:
    return DATA_DIR / "localization"


def get_available_languages() -> list[str]:
    directory = localization_dir()
    if not directory.is_dir():
        return [FALLBACK_LANGUAGE]
    languages = sorted(path.stem for path in directory.glob("*.json"))
    if FALLBACK_LANGUAGE not in languages:
        languages.insert(0, FALLBACK_LANGUAGE)
    return languages


def get_language_options() -> list[tuple[str, str]]:
    """Return ``(code, native name)`` pairs for the language picker."""
    return [(code, LANGUAGE_NAMES.get(code, code)) for code in get_available_languages()]


def normalize_language(value: str | None) -> str:
    """Map ``ru_RU``/``ru-RU``/``RU`` to an available ``ru`` file, else English."""
    available = get_available_languages()
    raw = str(value or "").strip().lower().replace("-", "_")
    if not raw:
        return FALLBACK_LANGUAGE
    if raw in available:
        return raw
    base = raw.split("_", 1)[0]
    return base if base in available else FALLBACK_LANGUAGE


def detect_system_language() -> str:
    """Best-effort system language detection without importing Qt."""
    candidates = [
        os.environ.get("WORKMODS_LANGUAGE", ""),
        os.environ.get("LC_ALL", ""),
        os.environ.get("LC_MESSAGES", ""),
        os.environ.get("LANG", ""),
    ]
    try:
        candidates.append(locale.getlocale()[0] or "")
    except (ValueError, TypeError):
        pass
    for candidate in candidates:
        if candidate:
            language = normalize_language(str(candidate).split(".", 1)[0])
            if language != FALLBACK_LANGUAGE or str(candidate).lower().startswith("en"):
                return language
    return FALLBACK_LANGUAGE


def resolve_language(preferred: str | None) -> str:
    """Use the configured language, otherwise the system language."""
    return normalize_language(preferred) if str(preferred or "").strip() else detect_system_language()


class Localization:
    def __init__(self, lang: str = FALLBACK_LANGUAGE):
        self.lang = FALLBACK_LANGUAGE
        self.strings: dict[str, str] = {}
        self._fallback: dict[str, str] = {}
        self.load(lang)

    def load(self, lang: str) -> None:
        self.lang = normalize_language(lang)
        self.strings = self._read(self.lang)
        self._fallback = self._read(FALLBACK_LANGUAGE) if self.lang != FALLBACK_LANGUAGE else {}

    @staticmethod
    def _read(lang: str) -> dict[str, str]:
        path = localization_dir() / f"{lang}.json"
        if not path.is_file():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def t(self, key: str, default: str = "") -> str:
        return self.strings.get(key) or self._fallback.get(key) or default or key


__all__ = [
    "FALLBACK_LANGUAGE",
    "LANGUAGE_NAMES",
    "Localization",
    "detect_system_language",
    "get_available_languages",
    "get_language_options",
    "localization_dir",
    "normalize_language",
    "resolve_language",
]
