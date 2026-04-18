import logging

from dictum.config import Config
from dictum.processing.base import TextProcessor
from dictum.processing.clean import CleanProcessor

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
Du bist ein Deeskalations-Assistent.

Deine Aufgabe:
- Du erhältst Text, der möglicherweise aggressiv, unhöflich oder emotional aufgeladen ist.
- Wandle den Text in eine höfliche, respektvolle und sachliche Formulierung um.
- Die URSPRÜNGLICHE BEDEUTUNG und alle Sachargumente MÜSSEN vollständig erhalten bleiben.
- Entferne Beleidigungen, Schimpfwörter und aggressive Formulierungen.
- Ersetze sie durch sachliche, konstruktive Alternativen.
- Der Ton soll bestimmt aber höflich sein — nicht unterwürfig.
- Antworte NUR mit dem umformulierten Text, ohne Erklärungen oder Anmerkungen.
- Antworte in derselben Sprache wie der Eingabetext."""


class RageProcessor(TextProcessor):
    """Modus C: Deeskalation — aggressiv → höflich (Claude API)."""

    def __init__(self, config: Config):
        self._config = config
        self._fallback = CleanProcessor()
        self._client = None

        if config.anthropic_api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(
                    api_key=config.anthropic_api_key,
                    timeout=config.anthropic_timeout,
                )
            except ImportError:
                logger.warning("anthropic-Paket nicht installiert, Fallback auf Clean-Modus")
        else:
            logger.warning("Kein ANTHROPIC_API_KEY gesetzt, Rage-Modus nutzt Clean-Fallback")

    @property
    def name(self) -> str:
        return "Rage"

    def process(self, text: str) -> str:
        if not text.strip():
            return text

        if self._client is None:
            logger.info("Rage-Fallback auf Clean-Modus")
            return self._fallback.process(text)

        try:
            response = self._client.messages.create(
                model=self._config.anthropic_model,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": text}],
            )
            result = response.content[0].text.strip()
            logger.info("Rage-Transformation erfolgreich")
            return result
        except Exception as e:
            logger.error("Claude API Fehler: %s — Fallback auf Clean", e)
            return self._fallback.process(text)
