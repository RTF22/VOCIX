"""Internationalisierung: JSON-basierter String-Lookup mit Fallback-Kette.

API:
    set_language(code)   — aktive Sprache wechseln
    get_language()       — aktuelle Sprache
    t(key, **kwargs)     — übersetzten String holen, mit str.format-Interpolation
    available_languages()— {"de": "Deutsch", "en": "English"}
    whisper_code()       — aktuelle Sprache als Whisper-Locale-Code

Fallback: gesuchte Sprache → Englisch → Schlüssel als String.
"""

import json
import logging
import sys
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_LANGUAGE = "en"
_FALLBACK_LANGUAGE = "en"

_translations: dict[str, dict[str, str]] = {}
_current_language = _DEFAULT_LANGUAGE
# Schützt _current_language und _translations vor Races zwischen set_language()
# (Tray-Thread) und t() (Pipeline-Thread). RLock, weil _ensure_loaded() intern
# wieder unter Lock laufen darf.
_LOCK = threading.RLock()


def _locales_dir() -> Path:
    """Pfad zum locales-Verzeichnis — funktioniert als Script und als PyInstaller-Bundle."""
    if getattr(sys, "frozen", False):
        # Im Bundle: neben der .exe (PyInstaller kopiert datas in _MEIPASS)
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "vocix" / "locales"
    return Path(__file__).resolve().parent / "locales"


def _load_file(code: str) -> dict[str, str]:
    path = _locales_dir() / f"{code}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("Locale-Datei fehlt: %s", path)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Locale-Datei konnte nicht gelesen werden (%s): %s", path, e)
    return {}


def _ensure_loaded(code: str) -> None:
    with _LOCK:
        if code not in _translations:
            _translations[code] = _load_file(code)


def available_languages() -> dict[str, str]:
    return {"de": "Deutsch", "en": "English"}


def set_language(code: str) -> None:
    global _current_language
    if code not in available_languages():
        with _LOCK:
            current = _current_language
        logger.warning("Unbekannter Sprachcode %r — bleibe bei %r", code, current)
        return
    _ensure_loaded(code)
    _ensure_loaded(_FALLBACK_LANGUAGE)
    with _LOCK:
        _current_language = code


def get_language() -> str:
    with _LOCK:
        return _current_language


def whisper_code() -> str:
    """Whisper-Sprachcode für aktuelle UI-Sprache (derzeit 1:1-Mapping)."""
    with _LOCK:
        return _current_language


def _lookup(translations: dict, key: str):
    """Lookup mit Fallback auf dotted-Pfad: erst flacher Key, dann durch
    verschachtelte Dicts gehen. ``settings.tab.basics`` findet also sowohl
    ``{"settings.tab.basics": "..."}`` als auch ``{"settings": {"tab": {"basics": "..."}}}``."""
    flat = translations.get(key)
    if isinstance(flat, str):
        return flat
    parts = key.split(".")
    node = translations
    for part in parts:
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node if isinstance(node, str) else None


def t(key: str, **kwargs) -> str:
    with _LOCK:
        current = _current_language
    _ensure_loaded(current)
    _ensure_loaded(_FALLBACK_LANGUAGE)
    with _LOCK:
        value = (
            _lookup(_translations.get(current, {}), key)
            or _lookup(_translations.get(_FALLBACK_LANGUAGE, {}), key)
            or key
        )
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError) as e:
            logger.warning("Interpolation fehlgeschlagen für %r: %s", key, e)
            return value
    return value
