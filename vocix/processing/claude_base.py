import logging

from vocix.config import Config
from vocix.i18n import t
from vocix.processing.base import TextProcessor
from vocix.processing.clean import CleanProcessor

logger = logging.getLogger(__name__)


class ClaudeProcessor(TextProcessor):
    """Gemeinsame Basis für Claude-API-gestützte Modi (Business, Rage).

    Fehlender API-Key, fehlendes anthropic-Paket, API-Fehler oder leere
    Antworten führen alle auf denselben Clean-Mode-Fallback — der Modus-Wechsel
    bleibt für den User unsichtbar.
    """

    def __init__(self, config: Config, *, name: str, prompt_key: str):
        self._config = config
        self._name = name
        self._prompt_key = prompt_key
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
                logger.warning("anthropic package not installed, %s mode uses Clean fallback", name)
        else:
            logger.warning("No ANTHROPIC_API_KEY set, %s mode uses Clean fallback", name)

    @property
    def name(self) -> str:
        return self._name

    def process(self, text: str) -> str:
        if not text.strip():
            return text

        if self._client is None:
            logger.info("%s falling back to Clean mode", self._name)
            return self._fallback.process(text)

        try:
            response = self._client.messages.create(
                model=self._config.anthropic_model,
                max_tokens=1024,
                system=t(self._prompt_key),
                messages=[{"role": "user", "content": text}],
            )
        except Exception as e:
            logger.error("Claude API error (%s): %s — falling back to Clean", self._name, e)
            return self._fallback.process(text)

        # Claude kann theoretisch einen leeren content-Array oder einen
        # Non-Text-Block (z.B. tool_use) zurückgeben. Beides würde beim
        # .text-Zugriff crashen; sauber auf Clean-Fallback ausweichen.
        content = response.content if hasattr(response, "content") else None
        if not content or not hasattr(content[0], "text"):
            logger.warning("%s: empty/invalid Claude response — falling back to Clean", self._name)
            return self._fallback.process(text)

        result = content[0].text.strip()
        if not result:
            logger.warning("%s: empty text in Claude response — falling back to Clean", self._name)
            return self._fallback.process(text)

        logger.info("%s transformation succeeded", self._name)
        return result
