import json
from pathlib import Path

from vocix.config import Config


def test_config_load_reads_new_state_fields(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({
        "language": "en",
        "whisper_model": "medium",
        "whisper_acceleration": "cpu",
        "translate_to_english": True,
        "default_mode": "business",
        "hotkey_record": "f9",
        "hotkey_mode_a": "ctrl+shift+1",
        "hotkey_mode_b": "ctrl+shift+2",
        "hotkey_mode_c": "ctrl+shift+3",
        "log_level": "DEBUG",
        "log_file": str(tmp_path / "vocix.log"),
        "whisper_model_dir": str(tmp_path / "models"),
        "overlay_display_seconds": 2.5,
        "rdp_mode": True,
        "silence_threshold": 0.02,
        "min_duration": 0.7,
        "sample_rate": 16000,
        "anthropic_api_key": "sk-ant-test",
        "anthropic_model": "claude-sonnet-4-6",
        "anthropic_timeout": 20.0,
        "whisper_language_override": "fr",
        "anthropic_key_validated": True,
    }))
    monkeypatch.setattr("vocix.config.STATE_FILE", state_file)

    config = Config.load(env_file=tmp_path / ".env-does-not-exist")

    assert config.language == "en"
    assert config.whisper_model == "medium"
    assert config.default_mode == "business"
    assert config.hotkey_record == "f9"
    assert config.log_level == "DEBUG"
    assert config.overlay_display_seconds == 2.5
    assert config.rdp_mode is True
    assert config.silence_threshold == 0.02
    assert config.anthropic_api_key == "sk-ant-test"
    assert config.anthropic_model == "claude-sonnet-4-6"
    assert config.whisper_language_override == "fr"
