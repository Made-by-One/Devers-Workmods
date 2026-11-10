"""Localization helpers.

Translation files are plain JSON in ``data/localization/<lang>.json``. Missing
keys fall back to the English file and then to the literal default passed by the
caller, so adding a language never requires translating everything at once.
"""

from __future__ import annotations

import json
from pathlib import Path

from workmods.config import DATA_DIR

FALLBACK_LANGUAGE = "en"


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


class Localization:
    def __init__(self, lang: str = FALLBACK_LANGUAGE):
        self.lang = lang
        self.strings: dict[str, str] = {}
        self._fallback: dict[str, str] = {}
        self.load(lang)

    def load(self, lang: str) -> None:
        self.lang = lang or FALLBACK_LANGUAGE
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


__all__ = ["FALLBACK_LANGUAGE", "Localization", "get_available_languages", "localization_dir"]
