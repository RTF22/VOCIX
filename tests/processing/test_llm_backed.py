"""Tests für LLMBackedProcessor — Provider-Aufruf, Fallback, Callback."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vocix.config import Config
from vocix.processing.llm_backed import LLMBackedProcessor
from vocix.processing.providers import ProviderError


def _config() -> Config:
    c = Config()
    c.anthropic_api_key = ""
    c.llm = {
        "default": "anthropic",
        "providers": {"anthropic": {"api_key": "sk-x", "model": "claude-test", "validated": True}},
    }
    return c


def test_blank_input_short_circuits():
    proc = LLMBackedProcessor(_config(), name="Business", prompt_key="prompt.business", mode="business")
    assert proc.process("") == ""
    assert proc.process("   ") == "   "


def test_successful_completion_returned():
    cfg = _config()
    fake_provider = MagicMock()
    fake_provider.complete.return_value = "Sehr geehrte Damen und Herren."
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake_provider):
        proc = LLMBackedProcessor(cfg, name="Business", prompt_key="prompt.business", mode="business")
        out = proc.process("das ist fertig")
    assert out == "Sehr geehrte Damen und Herren."
    fake_provider.complete.assert_called_once()
    kwargs = fake_provider.complete.call_args.kwargs
    assert kwargs["user"] == "das ist fertig"
    assert kwargs["system"]  # nicht-leer aus i18n


def test_provider_error_falls_back_to_clean():
    cfg = _config()
    fake_provider = MagicMock()
    fake_provider.complete.side_effect = ProviderError("network down")
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake_provider):
        proc = LLMBackedProcessor(cfg, name="Business", prompt_key="prompt.business", mode="business")
        out = proc.process("äh das ist gut.")
    # Clean entfernt "äh" und setzt Satzanfang groß
    assert out == "Das ist gut."


def test_build_failure_falls_back_to_clean():
    cfg = _config()
    with patch("vocix.processing.llm_backed.build_provider",
               side_effect=ProviderError("config invalid")):
        proc = LLMBackedProcessor(cfg, name="Business", prompt_key="prompt.business", mode="business")
        out = proc.process("äh das ist gut.")
    assert out == "Das ist gut."


def test_fallback_callback_fired_with_mode_name():
    cfg = _config()
    fake_provider = MagicMock()
    fake_provider.complete.side_effect = ProviderError("boom")
    seen = []
    proc = LLMBackedProcessor(
        cfg, name="Business", prompt_key="prompt.business", mode="business",
        on_fallback=lambda mode_name, reason: seen.append((mode_name, reason)),
    )
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake_provider):
        proc.process("hallo")
    assert len(seen) == 1
    assert seen[0][0] == "Business"
    assert "boom" in seen[0][1]


def test_name_property():
    proc = LLMBackedProcessor(_config(), name="Rage", prompt_key="prompt.rage", mode="rage")
    assert proc.name == "Rage"
