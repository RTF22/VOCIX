"""Tests für LLM-Provider-Config-Resolution in vocix.config."""
from __future__ import annotations

from pathlib import Path

import pytest

from vocix.config import Config


def _cfg() -> Config:
    return Config()


def test_llm_resolve_reads_new_schema(monkeypatch, tmp_path):
    monkeypatch.setattr("vocix.config.STATE_FILE", tmp_path / "state.json")
    state = {
        "llm": {
            "default": "openai",
            "providers": {
                "openai": {"api_key": "sk-x", "base_url": "https://api.groq.com/openai/v1",
                           "model": "llama-3.1-70b-versatile", "timeout": 12.0, "validated": True},
            },
        },
    }
    (tmp_path / "state.json").write_text(__import__("json").dumps(state), encoding="utf-8")

    c = Config.load()
    pc = c.llm_resolve("openai")
    assert pc.kind == "openai"
    assert pc.api_key == "sk-x"
    assert pc.base_url == "https://api.groq.com/openai/v1"
    assert pc.model == "llama-3.1-70b-versatile"
    assert pc.timeout == 12.0


def test_llm_resolve_falls_back_to_legacy_anthropic(monkeypatch, tmp_path):
    monkeypatch.setattr("vocix.config.STATE_FILE", tmp_path / "state.json")
    # Alte Felder, kein neues llm-Schema
    state = {
        "anthropic_api_key": "sk-ant-old",
        "anthropic_model": "claude-old",
        "anthropic_timeout": 17.0,
    }
    (tmp_path / "state.json").write_text(__import__("json").dumps(state), encoding="utf-8")

    c = Config.load()
    pc = c.llm_resolve("anthropic")
    assert pc.kind == "anthropic"
    assert pc.api_key == "sk-ant-old"
    assert pc.model == "claude-old"
    assert pc.timeout == 17.0


def test_llm_provider_for_uses_default_when_override_null(monkeypatch, tmp_path):
    monkeypatch.setattr("vocix.config.STATE_FILE", tmp_path / "state.json")
    state = {
        "llm": {
            "default": "anthropic",
            "business": None,
            "providers": {
                "anthropic": {"api_key": "sk-ant", "model": "claude-test", "timeout": 15.0},
            },
        },
    }
    (tmp_path / "state.json").write_text(__import__("json").dumps(state), encoding="utf-8")

    c = Config.load()
    pc = c.llm_provider_for("business")
    assert pc.kind == "anthropic"


def test_llm_provider_for_uses_override_when_set(monkeypatch, tmp_path):
    monkeypatch.setattr("vocix.config.STATE_FILE", tmp_path / "state.json")
    state = {
        "llm": {
            "default": "anthropic",
            "business": "ollama",
            "providers": {
                "anthropic": {"api_key": "sk-ant", "model": "claude-test"},
                "ollama": {"base_url": "http://localhost:11434", "model": "llama3.1"},
            },
        },
    }
    (tmp_path / "state.json").write_text(__import__("json").dumps(state), encoding="utf-8")

    c = Config.load()
    pc = c.llm_provider_for("business")
    assert pc.kind == "ollama"
    assert pc.model == "llama3.1"


def test_llm_provider_for_legacy_implicit_anthropic_default(monkeypatch, tmp_path):
    """Kein neues Schema, nur Alt-Key → Default ist implizit anthropic."""
    monkeypatch.setattr("vocix.config.STATE_FILE", tmp_path / "state.json")
    state = {"anthropic_api_key": "sk-ant-old"}
    (tmp_path / "state.json").write_text(__import__("json").dumps(state), encoding="utf-8")

    c = Config.load()
    pc = c.llm_provider_for("business")
    assert pc.kind == "anthropic"
    assert pc.api_key == "sk-ant-old"


def test_llm_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setattr("vocix.config.STATE_FILE", tmp_path / "state.json")
    monkeypatch.setenv("VOCIX_LLM_DEFAULT", "ollama")
    monkeypatch.setenv("VOCIX_LLM_OLLAMA_BASE_URL", "http://envhost:11434")
    monkeypatch.setenv("VOCIX_LLM_OLLAMA_MODEL", "envmodel")
    monkeypatch.setenv("VOCIX_LLM_OLLAMA_TIMEOUT", "42")

    c = Config.load()
    pc = c.llm_provider_for("business")
    assert pc.kind == "ollama"
    assert pc.base_url == "http://envhost:11434"
    assert pc.model == "envmodel"
    assert pc.timeout == 42.0


def test_llm_validated_anthropic_requires_flag(monkeypatch, tmp_path):
    monkeypatch.setattr("vocix.config.STATE_FILE", tmp_path / "state.json")
    state = {"llm": {"providers": {"anthropic": {"api_key": "sk-ant", "validated": False}}}}
    (tmp_path / "state.json").write_text(__import__("json").dumps(state), encoding="utf-8")

    c = Config.load()
    assert c.llm_validated("anthropic") is False

    state["llm"]["providers"]["anthropic"]["validated"] = True
    (tmp_path / "state.json").write_text(__import__("json").dumps(state), encoding="utf-8")
    c = Config.load()
    assert c.llm_validated("anthropic") is True


def test_llm_validated_ollama_no_flag_required(monkeypatch, tmp_path):
    """Ollama braucht keine Validierung — base_url+model reicht."""
    monkeypatch.setattr("vocix.config.STATE_FILE", tmp_path / "state.json")
    state = {"llm": {"providers": {"ollama": {"base_url": "http://localhost:11434",
                                              "model": "llama3.1"}}}}
    (tmp_path / "state.json").write_text(__import__("json").dumps(state), encoding="utf-8")

    c = Config.load()
    assert c.llm_validated("ollama") is True


def test_llm_validated_legacy_anthropic_key_counts_as_validated(monkeypatch, tmp_path):
    """Der bestehende state-Flag anthropic_key_validated zählt als Migration."""
    monkeypatch.setattr("vocix.config.STATE_FILE", tmp_path / "state.json")
    state = {"anthropic_api_key": "sk-ant-old", "anthropic_key_validated": True}
    (tmp_path / "state.json").write_text(__import__("json").dumps(state), encoding="utf-8")

    c = Config.load()
    assert c.llm_validated("anthropic") is True
