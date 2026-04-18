import logging
import threading

import numpy as np
import sounddevice as sd

from vocix.config import Config

logger = logging.getLogger(__name__)


class AudioRecorder:
    """Nimmt Audio vom Mikrofon auf. Thread-safe start/stop."""

    def __init__(self, config: Config):
        self._config = config
        self._buffer: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self._recording = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        with self._lock:
            if self._recording:
                return
            self._buffer.clear()
            try:
                self._stream = sd.InputStream(
                    samplerate=self._config.sample_rate,
                    channels=self._config.channels,
                    dtype="float32",
                    callback=self._audio_callback,
                )
                self._stream.start()
                self._recording = True
                logger.info("Aufnahme gestartet")
            except sd.PortAudioError as e:
                logger.error("Mikrofon nicht verfügbar: %s", e)
                raise RuntimeError(
                    "Mikrofon nicht verfügbar. Bitte prüfe die Audioeinstellungen."
                ) from e

    def stop(self) -> np.ndarray | None:
        """Stoppt die Aufnahme und gibt das Audio als float32 numpy array zurück.
        Gibt None zurück wenn die Aufnahme zu kurz oder zu leise war."""
        with self._lock:
            if not self._recording:
                return None
            # Flag zuerst zurücksetzen, damit der Callback keine neuen Frames
            # mehr in den Buffer schreibt, auch wenn PortAudio noch nachfeuert.
            self._recording = False
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception as e:
                    logger.warning("Fehler beim Stream-Shutdown: %s", e)
                finally:
                    self._stream = None

        if not self._buffer:
            logger.warning("Leerer Audio-Buffer")
            return None

        audio = np.concatenate(self._buffer, axis=0).flatten()
        duration = len(audio) / self._config.sample_rate

        if duration < self._config.min_duration:
            logger.warning("Aufnahme zu kurz: %.2fs", duration)
            return None

        rms = np.sqrt(np.mean(audio**2))
        if rms < self._config.silence_threshold:
            logger.warning("Aufnahme zu leise (RMS=%.4f)", rms)
            return None

        logger.info("Aufnahme beendet: %.2fs, RMS=%.4f", duration, rms)
        return audio

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        # PortAudio-Callback läuft in einem fremden Thread und kann nach stop()
        # noch nachfeuern, bevor PortAudio den Callback drainiert. Ohne Guard
        # würden Daten in den Buffer einer bereits beendeten Session fließen.
        if not self._recording:
            return
        if status:
            logger.warning("Audio-Status: %s", status)
        self._buffer.append(indata.copy())
