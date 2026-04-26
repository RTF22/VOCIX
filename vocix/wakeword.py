"""Wake-Word-Erkennung als opt-in Alternative zu Push-to-Talk.

Nutzt openWakeWord (Apache-2.0). Die Abhängigkeit ist optional — wenn
`openwakeword` nicht installiert ist, gibt `is_available()` False zurück und
der Tray-Toggle bleibt ausgeblendet.

Aktiv hört der Listener kontinuierlich auf 16-kHz-Mono-Chunks (~80 ms) vom
Mikrofon und ruft `on_detect()` auf, sobald der Modell-Score eine Schwelle
überschreitet. Ein Cooldown verhindert Mehrfach-Trigger.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

import numpy as np

logger = logging.getLogger(__name__)

# Lazy-Imports: openwakeword + sounddevice werden erst bei Verwendung gezogen,
# damit `import vocix.wakeword` keine Pflichtabhängigkeit erzwingt.
try:
    import openwakeword  # noqa: F401
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


def is_available() -> bool:
    return AVAILABLE


# Empfohlene Defaults aus der openWakeWord-Doku
SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1280  # 80 ms bei 16 kHz
DEFAULT_MODEL = "hey_jarvis_v0.1"
DEFAULT_THRESHOLD = 0.5
DEFAULT_COOLDOWN = 3.0  # Sekunden nach einer Erkennung, bevor erneut gefeuert wird


class WakeWordListener:
    """Hintergrund-Listener; thread-safe start/stop. Idempotent."""

    def __init__(
        self,
        on_detect: Callable[[], None],
        model: str = DEFAULT_MODEL,
        threshold: float = DEFAULT_THRESHOLD,
        cooldown: float = DEFAULT_COOLDOWN,
    ):
        self._on_detect = on_detect
        self._model_name = model
        self._threshold = float(threshold)
        self._cooldown = float(cooldown)
        self._thread: threading.Thread | None = None
        self._running = threading.Event()
        self._lock = threading.Lock()
        self._last_trigger = 0.0

    def start(self) -> None:
        if not AVAILABLE:
            raise RuntimeError("openwakeword ist nicht installiert")
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._running.set()
            self._thread = threading.Thread(
                target=self._run, name="WakeWordListener", daemon=True
            )
            self._thread.start()
            logger.info("Wake-word listener started (model: %s)", self._model_name)

    def stop(self) -> None:
        with self._lock:
            self._running.clear()
            thread = self._thread
            self._thread = None
        if thread is not None:
            thread.join(timeout=2.0)
            logger.info("Wake-word listener stopped")

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    def _run(self) -> None:
        # Lazy-Imports erst hier, damit Ladezeit & Fehler nur den Listener
        # treffen und nicht die App-Initialisierung.
        try:
            import sounddevice as sd
            from openwakeword.model import Model
        except Exception as e:
            logger.error("Wake-word dependencies missing: %s", e)
            self._running.clear()
            return

        try:
            model = Model(wakeword_models=[self._model_name])
        except Exception as e:
            logger.error("Failed to load wake-word model %r: %s",
                         self._model_name, e)
            self._running.clear()
            return

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=CHUNK_SAMPLES,
            ) as stream:
                while self._running.is_set():
                    audio, _overflow = stream.read(CHUNK_SAMPLES)
                    if not self._running.is_set():
                        break
                    chunk = np.asarray(audio, dtype=np.int16).flatten()
                    try:
                        scores = model.predict(chunk)
                    except Exception as e:
                        logger.warning("Wake-word predict() failed: %s", e)
                        continue
                    self._handle_scores(scores)
        except Exception as e:
            logger.error("Wake-word stream error: %s", e, exc_info=True)
        finally:
            self._running.clear()

    def _handle_scores(self, scores: dict[str, float]) -> None:
        if not scores:
            return
        best = max(scores.values())
        if best < self._threshold:
            return
        now = time.monotonic()
        if now - self._last_trigger < self._cooldown:
            return
        self._last_trigger = now
        logger.info("Wake-word detected (score=%.2f)", best)
        try:
            self._on_detect()
        except Exception as e:
            logger.error("Wake-word callback error: %s", e, exc_info=True)
