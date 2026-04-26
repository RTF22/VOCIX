"""Provider-Basis: abstrakte LLM-Schnittstelle, Fehlerklasse, Config-DTO."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class ProviderError(Exception):
    """Einheitliche Fehlerklasse für alle LLM-Provider.

    Wird vom LLMBackedProcessor gefangen und löst Clean-Fallback + Toast aus.
    Die Provider mappen native Fehler (HTTP, SDK, Timeout, Auth, leere Antwort)
    auf diese Klasse, damit der Aufrufer nur einen Typ kennen muss.
    """


@dataclass
class ProviderConfig:
    """In-Memory-Repräsentation eines Provider-Slots aus state.json."""
    kind: str                # "anthropic" | "openai" | "ollama"
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    timeout: float = 15.0


class LLMProvider(ABC):
    """Abstrakte Provider-Schnittstelle.

    Jede konkrete Implementierung kapselt SDK/HTTP-Aufruf und mappt
    Provider-Fehler auf ProviderError.
    """

    @abstractmethod
    def complete(self, *, system: str, user: str, max_tokens: int = 1024) -> str:
        """Sendet system+user an das Modell, liefert die Text-Completion.

        Raises:
            ProviderError: bei jedem Fehler (Netz, Auth, Timeout, leerer Content).
        """
        ...
