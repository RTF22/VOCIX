import logging
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

from vocix.config import Config
from vocix.stt.base import STTEngine

logger = logging.getLogger(__name__)


def cuda_available() -> bool:
    """Prüft, ob CTranslate2 mindestens ein CUDA-Gerät sieht.

    Robust gegen fehlende Bibliotheken (cuDNN/cuBLAS) — bei jeder Exception
    wird CPU genutzt. Wird aus dem Tray-Thread und beim Modellladen aufgerufen.
    """
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception as e:
        logger.debug("CUDA-Check fehlgeschlagen: %s", e)
        return False


def _resolve_device(acceleration: str) -> tuple[str, str]:
    """Wählt (device, compute_type) aus dem Acceleration-Setting.

    auto → CUDA wenn verfügbar, sonst CPU
    gpu  → CUDA erzwingen (Modellladen schlägt fehl, falls nicht da)
    cpu  → CPU erzwingen
    """
    accel = (acceleration or "auto").lower()
    if accel == "cpu":
        return "cpu", "int8"
    if accel == "gpu":
        return "cuda", "float16"
    if cuda_available():
        return "cuda", "float16"
    return "cpu", "int8"


class WhisperSTT(STTEngine):
    """Speech-to-Text mit faster-whisper (CTranslate2)."""

    def __init__(self, config: Config):
        self._config = config
        model_dir = Path(config.whisper_model_dir)
        model_dir.mkdir(parents=True, exist_ok=True)

        device, compute_type = _resolve_device(config.whisper_acceleration)
        logger.info(
            "Lade Whisper-Modell '%s' (device=%s, compute=%s, Verzeichnis: %s)...",
            config.whisper_model, device, compute_type, model_dir,
        )
        # CTranslate2 wirft hier bei pre-AVX-CPUs (RuntimeError/OSError) sowie
        # bei GPU-Wahl ohne cuDNN/cuBLAS. Caller entscheidet, ob das fatal ist
        # (Startup → Dialog + sys.exit) oder nur ein Toast (Laufzeit-Wechsel).
        self._model = WhisperModel(
            config.whisper_model,
            device=device,
            compute_type=compute_type,
            download_root=str(model_dir),
        )
        self._device = device
        self._compute_type = compute_type
        logger.info("Whisper-Modell geladen (device=%s)", device)

    @property
    def device(self) -> str:
        return self._device

    def transcribe(self, audio: np.ndarray) -> str:
        kwargs = {
            "language": self._config.whisper_language,
            "beam_size": 5,
            "vad_filter": True,
        }
        if self._config.translate_to_english:
            kwargs["task"] = "translate"
        segments, info = self._model.transcribe(audio, **kwargs)
        text = " ".join(segment.text.strip() for segment in segments)
        task = kwargs.get("task", "transcribe")
        logger.info("Transkription (task=%s, source=%s, %.0f%% Konfidenz): %s",
                     task, info.language, info.language_probability * 100, text)
        return text
