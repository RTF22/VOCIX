import tkinter as tk
from dataclasses import replace

import pytest

from vocix.config import Config
from vocix.ui.settings import SettingsDialog


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("Kein Display verfuegbar")
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def base_config():
    return Config(language="de", whisper_model="small", whisper_acceleration="auto")


def test_dialog_opens_with_three_tabs(root, base_config):
    dlg = SettingsDialog(root, config=base_config, on_apply=lambda c: None)
    assert dlg.notebook is not None
    assert len(dlg.notebook.tabs()) == 3
    dlg.destroy()


def test_dialog_cancel_calls_no_apply(root, base_config):
    called = {"n": 0}
    dlg = SettingsDialog(root, config=base_config, on_apply=lambda c: called.update(n=called["n"] + 1))
    dlg._on_cancel()
    assert called["n"] == 0


def test_dialog_apply_calls_callback_with_config_copy(root, base_config):
    received = []
    dlg = SettingsDialog(root, config=base_config, on_apply=lambda c: received.append(c))
    dlg._on_apply()
    assert len(received) == 1
    assert received[0] is not base_config
    assert received[0].language == "de"
    dlg.destroy()


def test_basics_initial_values_match_config(root):
    cfg = Config(language="en", whisper_model="medium", whisper_acceleration="cpu",
                 default_mode="clean", anthropic_api_key="")
    dlg = SettingsDialog(root, config=cfg, on_apply=lambda c: None)
    assert dlg._var_input_lang.get() == "en"
    assert dlg._var_whisper_model.get() == "medium"
    assert dlg._var_acceleration.get() == "cpu"
    dlg.destroy()


def test_basics_default_mode_only_clean_when_no_valid_key(root):
    cfg = Config(anthropic_api_key="")
    dlg = SettingsDialog(root, config=cfg, on_apply=lambda c: None)
    values = dlg._mode_combo["values"]
    assert tuple(values) == ("clean",)
    dlg.destroy()


def test_basics_changing_input_lang_updates_draft(root):
    cfg = Config(language="de")
    dlg = SettingsDialog(root, config=cfg, on_apply=lambda c: None)
    dlg._var_input_lang.set("en")
    dlg._on_input_lang_changed()
    assert dlg._draft.language == "en"
    dlg.destroy()


def test_advanced_rdp_toggle_disables_delays(root):
    cfg = Config(language="de", rdp_mode=False)
    dlg = SettingsDialog(root, config=cfg, on_apply=lambda c: None)
    dlg._var_rdp.set(True)
    dlg._on_rdp_changed()
    assert "disabled" in dlg._clipboard_spin.state()
    dlg.destroy()


def test_advanced_silence_threshold_round_trip(root):
    cfg = Config(language="de")
    dlg = SettingsDialog(root, config=cfg, on_apply=lambda c: None)
    dlg._var_silence.set(0.05)
    setattr(dlg._draft, "silence_threshold", float(dlg._var_silence.get()))
    assert dlg._draft.silence_threshold == pytest.approx(0.05)
    dlg.destroy()


def test_api_key_masked_display_for_saved_key(root):
    cfg = Config(language="de", anthropic_api_key="sk-ant-abcdefghijklmnopqrstuvwxyz1234")
    dlg = SettingsDialog(root, config=cfg, on_apply=lambda c: None)
    assert dlg._displayed_api_key() == "sk-ant-…1234"
    dlg.destroy()


def test_api_key_test_marks_validated(root, tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}")
    monkeypatch.setattr("vocix.config.STATE_FILE", state_file)
    cfg = Config(language="de")
    dlg = SettingsDialog(root, config=cfg, on_apply=lambda c: None)
    dlg._var_api_key.set("sk-ant-test-XYZ")
    monkeypatch.setattr("vocix.ui.settings._ping_anthropic", lambda key, model, timeout: True)
    dlg._on_test_api()
    import json
    assert json.loads(state_file.read_text())["anthropic_key_validated"] is True
    assert dlg._draft.anthropic_api_key == "sk-ant-test-XYZ"
    dlg.destroy()


def test_expert_factory_reset_clears_state(root, tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text('{"language": "en"}')
    monkeypatch.setattr("vocix.config.STATE_FILE", state_file)
    cfg = Config(language="de")
    dlg = SettingsDialog(root, config=cfg, on_apply=lambda c: None)
    monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **k: True)
    monkeypatch.setattr("tkinter.messagebox.showinfo", lambda *a, **k: None)
    dlg._on_factory_reset()
    import json
    assert json.loads(state_file.read_text()) == {}


def test_duplicate_hotkey_blocks_apply(root):
    received = []
    cfg = Config(language="de")
    dlg = SettingsDialog(root, config=cfg, on_apply=lambda c: received.append(c))
    dlg._draft.hotkey_record = "f9"
    dlg._draft.hotkey_mode_a = "f9"
    dlg._on_apply()
    assert received == []
    assert dlg._error_var.get() != ""
    dlg.destroy()


def test_ptt_combo_blocks_apply(root):
    received = []
    cfg = Config(language="de")
    dlg = SettingsDialog(root, config=cfg, on_apply=lambda c: received.append(c))
    dlg._draft.hotkey_record = "ctrl+f9"
    dlg._on_apply()
    assert received == []
    dlg.destroy()
