"""Unit-Tests für vocix.i18n — Lookup, Fallback, Interpolation, Sprachwechsel."""

import importlib

import pytest


@pytest.fixture
def i18n(monkeypatch):
    """Liefert ein frisch geladenes i18n-Modul mit DE als Startsprache."""
    import vocix.i18n as mod
    importlib.reload(mod)
    mod.set_language("de")
    return mod


def test_known_key_de(i18n):
    assert i18n.t("tray.quit") == "Beenden"


def test_language_switch(i18n):
    i18n.set_language("en")
    assert i18n.t("tray.quit") == "Quit"
    assert i18n.get_language() == "en"


def test_unknown_language_ignored(i18n):
    i18n.set_language("fr")
    assert i18n.get_language() == "de"


def test_interpolation(i18n):
    result = i18n.t("tray.update_available", version="1.2.3")
    assert "1.2.3" in result


def test_missing_key_returns_key(i18n):
    assert i18n.t("does.not.exist") == "does.not.exist"


def test_fallback_to_english(i18n, monkeypatch):
    # Simuliere fehlenden Key in DE, aber vorhanden in EN
    i18n._translations["de"] = {}
    i18n._translations["en"] = {"tray.quit": "Quit"}
    assert i18n.t("tray.quit") == "Quit"


def test_available_languages(i18n):
    langs = i18n.available_languages()
    assert "de" in langs
    assert "en" in langs


def test_whisper_code_matches_language(i18n):
    i18n.set_language("en")
    assert i18n.whisper_code() == "en"
    i18n.set_language("de")
    assert i18n.whisper_code() == "de"


def test_meta_name_used_in_available_languages(i18n):
    langs = i18n.available_languages()
    assert langs["de"] == "Deutsch"
    assert langs["en"] == "English"


def test_auto_discovery_picks_up_new_locale(i18n, tmp_path, monkeypatch):
    import json
    from pathlib import Path
    fake_locales = tmp_path / "locales"
    fake_locales.mkdir()
    # Copy real locales so other tests still work
    real_dir = Path(__file__).resolve().parent.parent / "vocix" / "locales"
    for src in real_dir.glob("*.json"):
        (fake_locales / src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    # Drop a synthetic French locale
    (fake_locales / "fr.json").write_text(
        json.dumps({"_meta": {"name": "Français", "whisper_code": "fr"}, "tray.quit": "Quitter"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(i18n, "_locales_dir", lambda: fake_locales)
    i18n.invalidate_languages()
    langs = i18n.available_languages()
    assert langs.get("fr") == "Français"
    i18n.set_language("fr")
    assert i18n.t("tray.quit") == "Quitter"
    assert i18n.whisper_code() == "fr"


def test_meta_name_falls_back_to_stem(i18n, tmp_path, monkeypatch):
    import json
    from pathlib import Path
    fake_locales = tmp_path / "locales"
    fake_locales.mkdir()
    real_dir = Path(__file__).resolve().parent.parent / "vocix" / "locales"
    for src in real_dir.glob("*.json"):
        (fake_locales / src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    # Locale without _meta.name
    (fake_locales / "xx.json").write_text(json.dumps({"tray.quit": "Q"}), encoding="utf-8")
    monkeypatch.setattr(i18n, "_locales_dir", lambda: fake_locales)
    i18n.invalidate_languages()
    assert i18n.available_languages().get("xx") == "xx"


def test_listener_called_on_language_change(i18n):
    seen = []
    cb = lambda code: seen.append(code)
    i18n.register_language_listener(cb)
    try:
        i18n.set_language("en")
        assert seen == ["en"]
        i18n.set_language("en")  # unchanged → no second call
        assert seen == ["en"]
        i18n.set_language("de")
        assert seen == ["en", "de"]
    finally:
        i18n.unregister_language_listener(cb)


def test_listener_unregister_stops_calls(i18n):
    seen = []
    cb = lambda code: seen.append(code)
    i18n.register_language_listener(cb)
    i18n.unregister_language_listener(cb)
    i18n.set_language("en")
    assert seen == []
