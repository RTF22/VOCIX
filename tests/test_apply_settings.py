import json
from dataclasses import replace
from unittest.mock import MagicMock

from vocix.config import Config
from vocix.main import VocixApp


def test_apply_settings_writes_state(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}")
    monkeypatch.setattr("vocix.config.STATE_FILE", state_file)

    app = VocixApp.__new__(VocixApp)
    app._config = Config(language="de", whisper_model="small")
    app._tray = MagicMock()
    app._overlay = MagicMock()
    app._reload_stt = MagicMock()
    app._rebind_hotkeys = MagicMock()

    new_cfg = replace(app._config, language="en", whisper_model="medium")
    app.apply_settings(new_cfg)

    saved = json.loads(state_file.read_text())
    assert saved["language"] == "en"
    assert saved["whisper_model"] == "medium"
    app._reload_stt.assert_called_once()
    app._rebind_hotkeys.assert_called_once()
    app._tray.refresh.assert_called_once()


def test_apply_settings_skips_reload_when_unchanged(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}")
    monkeypatch.setattr("vocix.config.STATE_FILE", state_file)

    app = VocixApp.__new__(VocixApp)
    app._config = Config(language="de", whisper_model="small")
    app._tray = MagicMock()
    app._overlay = MagicMock()
    app._reload_stt = MagicMock()
    app._rebind_hotkeys = MagicMock()

    app.apply_settings(replace(app._config))

    app._reload_stt.assert_not_called()
    app._rebind_hotkeys.assert_not_called()
