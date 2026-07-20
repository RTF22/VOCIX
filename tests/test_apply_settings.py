import json
from dataclasses import replace
from unittest.mock import MagicMock

from vocix.config import Config
from vocix.main import VocixApp


def _make_app(config):
    app = VocixApp.__new__(VocixApp)
    app._config = config
    app._tray = MagicMock()
    app._overlay = MagicMock()
    app._injector = None
    app._reload_stt = MagicMock()
    app._rebind_hotkeys = MagicMock()
    return app


def test_apply_settings_writes_state(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}")
    monkeypatch.setattr("vocix.config.STATE_FILE", state_file)

    app = _make_app(Config(language="de", whisper_model="small"))

    new_cfg = replace(app._config, language="en", whisper_model="medium",
                      hotkey_record="f9")
    restart = app.apply_settings(new_cfg)

    saved = json.loads(state_file.read_text())
    assert saved["language"] == "en"
    assert saved["whisper_model"] == "medium"
    app._reload_stt.assert_called_once()
    app._rebind_hotkeys.assert_called_once()
    app._tray.refresh.assert_called_once()
    assert restart is False


def test_apply_settings_updates_config_in_place(tmp_path, monkeypatch):
    """Die gemeinsame Config-Instanz wird in-place aktualisiert (nicht ersetzt),
    damit Komponenten mit eigener Referenz den neuen Stand live sehen."""
    state_file = tmp_path / "state.json"
    state_file.write_text("{}")
    monkeypatch.setattr("vocix.config.STATE_FILE", state_file)

    app = _make_app(Config(language="de", whisper_model="small"))
    shared_ref = app._config

    app.apply_settings(replace(app._config, whisper_model="medium"))

    assert app._config is shared_ref  # gleiche Instanz
    assert app._config.whisper_model == "medium"


def test_apply_settings_rebinds_only_on_hotkey_change(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}")
    monkeypatch.setattr("vocix.config.STATE_FILE", state_file)

    app = _make_app(Config(language="de", overlay_display_seconds=1.5))

    # Nur ein Nicht-Hotkey-Feld ändern → kein Rebind
    app.apply_settings(replace(app._config, overlay_display_seconds=3.0))

    app._rebind_hotkeys.assert_not_called()


def test_apply_settings_reports_restart_for_log_change(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}")
    monkeypatch.setattr("vocix.config.STATE_FILE", state_file)

    app = _make_app(Config(language="de", log_level="INFO"))

    restart = app.apply_settings(replace(app._config, log_level="DEBUG"))

    assert restart is True


def test_apply_settings_rebuilds_injector_on_delay_change(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}")
    monkeypatch.setattr("vocix.config.STATE_FILE", state_file)

    app = _make_app(Config(language="de", clipboard_delay=0.05))
    app._injector = MagicMock()
    old_injector = app._injector

    app.apply_settings(replace(app._config, clipboard_delay=0.3))

    assert app._injector is not old_injector


def test_apply_settings_skips_reload_when_unchanged(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}")
    monkeypatch.setattr("vocix.config.STATE_FILE", state_file)

    app = _make_app(Config(language="de", whisper_model="small"))

    app.apply_settings(replace(app._config))

    app._reload_stt.assert_not_called()
    app._rebind_hotkeys.assert_not_called()
