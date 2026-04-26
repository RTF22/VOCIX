"""Tests für Business/Rage-Processor — Fallback-Verhalten.

Geprüft werden die drei Wege, auf denen der LLM-Pfad den Clean-Fallback
aktiviert: (1) Provider-Bau scheitert (kein Key), (2) Provider raised,
(3) Provider liefert leere/ungültige Antwort (im Provider gemappt).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from vocix.config import Config
from vocix.processing.business import BusinessProcessor
from vocix.processing.providers import ProviderError
from vocix.processing.rage import RageProcessor


def _config(api_key: str = "") -> Config:
    c = Config()
    c.anthropic_api_key = api_key
    if api_key:
        c.llm = {
            "default": "anthropic",
            "providers": {"anthropic": {"api_key": api_key, "model": "claude-test",
                                        "timeout": 15.0, "validated": True}},
        }
    return c


# --- BusinessProcessor ---------------------------------------------------

def test_business_no_api_key_falls_back_to_clean():
    proc = BusinessProcessor(_config(api_key=""))
    assert proc.process("äh das ist gut.") == "Das ist gut."


def test_business_provider_exception_falls_back_to_clean():
    proc = BusinessProcessor(_config(api_key="sk-fake"))
    fake = MagicMock()
    fake.complete.side_effect = ProviderError("network down")
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake):
        assert proc.process("äh das ist gut.") == "Das ist gut."


def test_business_successful_response_is_returned():
    proc = BusinessProcessor(_config(api_key="sk-fake"))
    fake = MagicMock()
    fake.complete.return_value = "Sehr geehrte Damen und Herren, der Vorgang ist abgeschlossen."
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake):
        assert proc.process("das ist fertig").startswith("Sehr geehrte")


def test_business_empty_input_short_circuits():
    proc = BusinessProcessor(_config(api_key="sk-fake"))
    assert proc.process("") == ""
    assert proc.process("   ") == "   "


# --- RageProcessor (Parität) ---------------------------------------------

def test_rage_no_api_key_falls_back():
    proc = RageProcessor(_config(api_key=""))
    assert proc.process("äh das ist gut.") == "Das ist gut."


def test_rage_provider_exception_falls_back():
    proc = RageProcessor(_config(api_key="sk-fake"))
    fake = MagicMock()
    fake.complete.side_effect = ProviderError("500")
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake):
        assert proc.process("äh das ist gut.") == "Das ist gut."


def test_rage_uses_rage_prompt_key():
    proc = RageProcessor(_config(api_key="sk-fake"))
    fake = MagicMock()
    fake.complete.return_value = "höflicher Text"
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake):
        proc.process("das ist scheisse")
    kwargs = fake.complete.call_args.kwargs
    assert "system" in kwargs and kwargs["system"]


def test_business_uses_business_prompt_key():
    proc = BusinessProcessor(_config(api_key="sk-fake"))
    fake = MagicMock()
    fake.complete.return_value = "professionell"
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake):
        proc.process("das ist fertig")
    kwargs = fake.complete.call_args.kwargs
    assert "system" in kwargs and kwargs["system"]


def test_names_are_stable():
    """Public names ändern sich durch das Refactor nicht."""
    assert BusinessProcessor(_config()).name == "Business"
    assert RageProcessor(_config()).name == "Rage"
