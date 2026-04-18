from abc import ABC, abstractmethod


class TextProcessor(ABC):
    """Abstrakte Basisklasse für Text-Transformationen."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Anzeigename des Modus."""
        ...

    @abstractmethod
    def process(self, text: str) -> str:
        """Transformiert den transkribierten Text."""
        ...
