"""Tests für LatexProcessor — Erfolgsfall, Pass-Through-Fallback, Prompt-Lookup."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from vocix.config import Config
from vocix.processing.latex import LatexProcessor
from vocix.processing.passthrough import PassthroughProcessor
from vocix.processing.providers import ProviderError


def _config() -> Config:
    c = Config()
    c.anthropic_api_key = ""
    c.llm = {
        "default": "anthropic",
        "providers": {"anthropic": {"api_key": "sk-x", "model": "claude-test", "validated": True}},
    }
    return c


def test_latex_uses_passthrough_fallback():
    proc = LatexProcessor(_config())
    assert isinstance(proc._fallback, PassthroughProcessor)


def test_latex_returns_provider_output_on_success():
    cfg = _config()
    fake_provider = MagicMock()
    fake_provider.complete.return_value = "die Energie ist $E = mc^2$"
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake_provider):
        proc = LatexProcessor(cfg)
        out = proc.process("die Energie ist E gleich m c quadrat")
    assert out == "die Energie ist $E = mc^2$"


def test_latex_prompt_key_passed_to_provider():
    cfg = _config()
    fake_provider = MagicMock()
    fake_provider.complete.return_value = "irrelevant"
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake_provider), \
         patch("vocix.processing.llm_backed.t", return_value="LATEX-PROMPT") as mock_t:
        proc = LatexProcessor(cfg)
        proc.process("x quadrat")
    mock_t.assert_called_with("prompt.latex")
    kwargs = fake_provider.complete.call_args.kwargs
    assert kwargs["system"] == "LATEX-PROMPT"
    assert kwargs["user"] == "x quadrat"


def test_latex_provider_error_passes_through_raw_text():
    """Bei Provider-Fehler darf der Whisper-Rohtext NICHT durch Clean
    verfälscht werden — sonst zerschneidet Clean Mathe-Ausdrücke."""
    cfg = _config()
    fake_provider = MagicMock()
    fake_provider.complete.side_effect = ProviderError("network down")
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake_provider):
        proc = LatexProcessor(cfg)
        out = proc.process("äh x quadrat plus y quadrat gleich z quadrat")
    # Pass-Through: Text bleibt unverändert (KEIN Clean-Output wie "X quadrat …")
    assert out == "äh x quadrat plus y quadrat gleich z quadrat"


def test_latex_fallback_callback_fires_with_mode_name():
    cfg = _config()
    fake_provider = MagicMock()
    fake_provider.complete.side_effect = ProviderError("boom")
    seen = []
    proc = LatexProcessor(cfg)
    proc.set_fallback_callback(lambda mode_name, reason: seen.append((mode_name, reason)))
    with patch("vocix.processing.llm_backed.build_provider", return_value=fake_provider):
        proc.process("hallo x quadrat")
    assert len(seen) == 1
    assert seen[0][0] == "LaTeX"
    assert "boom" in seen[0][1]


def test_latex_name_property():
    assert LatexProcessor(_config()).name == "LaTeX"


def test_latex_mode_slot_resolution():
    cfg = _config()
    cfg.llm["latex"] = "openai"
    cfg.llm.setdefault("providers", {})["openai"] = {
        "api_key": "k", "base_url": "https://x", "model": "m", "validated": True,
    }
    assert cfg.llm_mode_slot("latex") == "openai"
