from abc import ABC, abstractmethod

import numpy as np


class STTEngine(ABC):
    """Abstrakte Basisklasse für Speech-to-Text Engines."""

    @abstractmethod
    def transcribe(self, audio: np.ndarray) -> str:
        """Transkribiert ein Audio-Array (float32, 16kHz mono) zu Text."""
        ...
