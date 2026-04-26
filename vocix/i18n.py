"""Internationalization: JSON-based string lookup with fallback chain.

API:
    set_language(code)              switch active language
    get_language()                  current language code
    t(key, **kwargs)                translated string with str.format interpolation
    available_languages()           {code: display_name} discovered from locales/*.json
    whisper_code()                  current language as Whisper locale code
    register_language_listener(cb)  callback fires after every successful set_language()

Fallback: requested language -> English -> raw key.

Locale files may include a top-level "_meta" block:
    "_meta": {"name": "Deutsch", "whisper_code": "de"}
"""

import json
import logging
import sys
import threading
from functools import lru_cache
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

_DEFAULT_LANGUAGE = "en"
_FALLBACK_LANGUAGE = "en"

_translations: dict[str, dict] = {}
_current_language = _DEFAULT_LANGUAGE
_listeners: list[Callable[[str], None]] = []
# Guards _current_language, _translations and _listeners against races between
# set_language() (tray thread) and t() (pipeline thread). RLock so _ensure_loaded()
# can re-enter under the same lock.
_LOCK = threading.RLock()


def _locales_dir() -> Path:
    """Path to locales directory, works as script and as PyInstaller bundle."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "vocix" / "locales"
    return Path(__file__).resolve().parent / "locales"


def _load_file(code: str) -> dict:
    path = _locales_dir() / f"{code}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("Locale file missing: %s", path)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Locale file unreadable (%s): %s", path, e)
    return {}


def _ensure_loaded(code: str) -> None:
    with _LOCK:
        if code not in _translations:
            _translations[code] = _load_file(code)


def _meta(code: str) -> dict:
    _ensure_loaded(code)
    with _LOCK:
        meta = _translations.get(code, {}).get("_meta", {})
    return meta if isinstance(meta, dict) else {}


@lru_cache(maxsize=1)
def available_languages() -> dict[str, str]:
    """Discover languages by scanning locales/*.json. Display name comes from
    each file's _meta.name block, falling back to the file stem if absent.
    Result is cached for the process lifetime; call invalidate_languages()
    after dropping a new locale at runtime (only useful in tests)."""
    result: dict[str, str] = {}
    for path in sorted(_locales_dir().glob("*.json")):
        code = path.stem
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Skipping locale %s: %s", path, e)
            continue
        meta = data.get("_meta") if isinstance(data, dict) else None
        name = (meta or {}).get("name") if isinstance(meta, dict) else None
        result[code] = name if isinstance(name, str) and name else code
    if not result:
        result = {"en": "English"}
    return result


def invalidate_languages() -> None:
    """Reset the available_languages() cache and forget loaded translations.
    Used by tests that drop locale files at runtime."""
    available_languages.cache_clear()
    with _LOCK:
        _translations.clear()


def register_language_listener(callback: Callable[[str], None]) -> None:
    """Register a callback that fires after every successful set_language().
    The new language code is passed as the only argument."""
    with _LOCK:
        if callback not in _listeners:
            _listeners.append(callback)


def unregister_language_listener(callback: Callable[[str], None]) -> None:
    with _LOCK:
        if callback in _listeners:
            _listeners.remove(callback)


def _notify_listeners(code: str) -> None:
    with _LOCK:
        snapshot = list(_listeners)
    for cb in snapshot:
        try:
            cb(code)
        except Exception as e:
            logger.warning("Language listener failed: %s", e)


def set_language(code: str) -> None:
    global _current_language
    if code not in available_languages():
        with _LOCK:
            current = _current_language
        logger.warning("Unknown language code %r, staying with %r", code, current)
        return
    _ensure_loaded(code)
    _ensure_loaded(_FALLBACK_LANGUAGE)
    with _LOCK:
        if _current_language == code:
            return
        _current_language = code
    _notify_listeners(code)


def get_language() -> str:
    with _LOCK:
        return _current_language


def whisper_code() -> str:
    """Whisper locale code for the active UI language. Reads _meta.whisper_code
    from the locale JSON; falls back to the language code itself if absent."""
    with _LOCK:
        current = _current_language
    code = _meta(current).get("whisper_code")
    return code if isinstance(code, str) and code else current


def _lookup(translations: dict, key: str):
    """Lookup with fallback to dotted path: try the flat key first, then walk
    nested dicts. ``settings.tab.basics`` matches both
    ``{"settings.tab.basics": "..."}`` and
    ``{"settings": {"tab": {"basics": "..."}}}``."""
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
            logger.warning("Interpolation failed for %r: %s", key, e)
            return value
    return value
