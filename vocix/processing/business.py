import logging

from vocix.config import Config
from vocix.processing.base import TextProcessor
from vocix.processing.clean import CleanProcessor

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
Du bist ein professioneller Textassistent für geschäftliche Kommunikation.

Deine Aufgabe:
- Wandle den gesprochenen Text in professionelle, formelle Schriftsprache um.
- Der Text soll für E-Mails, Briefe oder geschäftliche Dokumente geeignet sein.
- Verbessere Struktur, Grammatik und Tonalität.
- Entferne Füllwörter und umgangssprachliche Ausdrücke.
- Behalte die ursprüngliche Bedeutung exakt bei.
- Antworte NUR mit dem umformulierten Text, ohne Erklärungen oder Anmerkungen.
- Antworte in derselben Sprache wie der Eingabetext."""


class BusinessProcessor(TextProcessor):
    """Modus B: Professionelle Geschäftssprache via Claude API."""

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
            logger.warning("Kein ANTHROPIC_API_KEY gesetzt, Business-Modus nutzt Clean-Fallback")

    @property
    def name(self) -> str:
        return "Business"

    def process(self, text: str) -> str:
        if not text.strip():
            return text

        if self._client is None:
            logger.info("Business-Fallback auf Clean-Modus")
            return self._fallback.process(text)

        try:
            response = self._client.messages.create(
                model=self._config.anthropic_model,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": text}],
            )
            result = response.content[0].text.strip()
            logger.info("Business-Transformation erfolgreich")
            return result
        except Exception as e:
            logger.error("Claude API Fehler: %s — Fallback auf Clean", e)
            return self._fallback.process(text)
