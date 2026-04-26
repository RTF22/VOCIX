"""LLM-gestützter Text-Processor — generalisiert ClaudeProcessor.

Löst pro process()-Call den Provider via Config auf. Bei jedem Fehler
(ProviderError aus dem Provider, oder Config-Issue beim Bau) fällt auf
CleanProcessor zurück und ruft optional den on_fallback-Callback für
das Toast-Overlay.
"""
from __future__ import annotations

import logging
from typing import Callable

from vocix.config import Config
from vocix.i18n import t
from vocix.processing.base import TextProcessor
from vocix.processing.clean import CleanProcessor
from vocix.processing.providers import ProviderError, build_provider

logger = logging.getLogger(__name__)

FallbackCallback = Callable[[str, str], None]
"""(mode_name, reason) → wird gefeuert, wenn auf Clean-Fallback zurückgefallen wird."""


class LLMBackedProcessor(TextProcessor):
    """Modus-Processor, der ein LLM via konfigurierbarem Provider aufruft."""

    def __init__(
        self,
        config: Config,
        *,
        name: str,
        prompt_key: str,
        mode: str,  # "business" | "rage"
        on_fallback: FallbackCallback | None = None,
    ):
        self._config = config
        self._name = name
        self._prompt_key = prompt_key
        self._mode = mode
        self._fallback = CleanProcessor()
        self._on_fallback = on_fallback

    def set_fallback_callback(self, cb: FallbackCallback | None) -> None:
        self._on_fallback = cb

    @property
    def name(self) -> str:
        return self._name

    def process(self, text: str) -> str:
        if not text.strip():
            return text

        provider_cfg = self._config.llm_provider_for(self._mode)
        try:
            provider = build_provider(provider_cfg)
            result = provider.complete(system=t(self._prompt_key), user=text)
        except ProviderError as e:
            logger.info("%s: provider failed (%s) — falling back to Clean", self._name, e)
            if self._on_fallback is not None:
                try:
                    self._on_fallback(self._name, str(e))
                except Exception:  # nie an Callback-Fehler scheitern
                    logger.exception("on_fallback callback raised")
            return self._fallback.process(text)

        return result
