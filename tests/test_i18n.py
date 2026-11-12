from workmods.i18n import Localization, get_available_languages, normalize_language, resolve_language

EXPECTED_LANGUAGES = {"de", "en", "es", "fr", "ru", "zh"}


def test_shipped_catalogs_share_the_english_key_set():
    base = set(Localization("en").strings)
    assert EXPECTED_LANGUAGES <= set(get_available_languages())
    for code in EXPECTED_LANGUAGES:
        strings = Localization(code).strings
        assert set(strings) == base, f"{code}.json is out of sync with en.json"
        assert all(value.strip() for value in strings.values())


def test_normalize_language_accepts_locale_variants():
    assert normalize_language("ru_RU.UTF-8") == "ru"
    assert normalize_language("de-DE") == "de"
    assert normalize_language("ZH") == "zh"
    assert normalize_language("pt_BR") == "en"
    assert normalize_language("") == "en"


def test_resolve_language_prefers_config_and_falls_back_to_system(monkeypatch):
    assert resolve_language("fr") == "fr"
    monkeypatch.setenv("WORKMODS_LANGUAGE", "es_MX")
    assert resolve_language("") == "es"


def test_missing_key_falls_back_to_english_then_default():
    loc = Localization("de")
    assert loc.t("catalog") == "KATALOG"
    # A key that only exists in the fallback file still resolves.
    loc.strings.pop("catalog", None)
    assert loc.t("catalog") == "CATALOG"
    assert loc.t("no_such_key", "fallback") == "fallback"
