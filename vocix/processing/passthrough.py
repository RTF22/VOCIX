"""Identity-Processor — gibt Text unverändert zurück.

Wird vom LatexProcessor als Fallback genutzt: Bei Provider-Fehlern soll
der Whisper-Rohtext durchgereicht werden, nicht durch CleanProcessor
verfälscht (sonst werden „x quadrat" o. ä. zerschnitten).
"""
from __future__ import annotations

from vocix.processing.base import TextProcessor


class PassthroughProcessor(TextProcessor):
    @property
    def name(self) -> str:
        return "Passthrough"

    def process(self, text: str) -> str:
        return text
