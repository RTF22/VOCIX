"""Snippet-Expansion: Kürzel wie /sig im Diktat durch Volltext ersetzen.

Datei: %APPDATA%/VOCIX/snippets.json — Mapping {kürzel: ersatztext}.
Hot-Reload via mtime-Check bei jedem expand()-Aufruf.

Whisper transkribiert Slashes oft als "Schrägstrich" / "slash" — eine
Heuristik normalisiert diese Phrasen vor dem Lookup zurück zu "/wort".
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path

from vocix.config import APP_DIR

logger = logging.getLogger(__name__)


def _snippets_file() -> Path:
    appdata = os.getenv("APPDATA")
    base = Path(appdata) if appdata else APP_DIR
    return base / "VOCIX" / "snippets.json"


SNIPPETS_FILE = _snippets_file()

DEFAULT_SNIPPETS: dict[str, str] = {
    "/sig": "Mit freundlichen Grüßen\nJens Fricke",
    "/adr": "Musterstraße 1\n12345 Musterstadt",
}

# "Schrägstrich Wort" / "slash word" → "/wort"
_SLASH_PHRASE = re.compile(r"\b(?:schrägstrich|slash)\s+(\w+)", re.IGNORECASE)


def _normalize_slash_phrases(text: str) -> str:
    return _SLASH_PHRASE.sub(lambda m: "/" + m.group(1), text)


class SnippetExpander:
    def __init__(self, path: Path | None = None):
        self._path = path or SNIPPETS_FILE
        self._lock = threading.RLock()
        self._snippets: dict[str, str] = {}
        self._mtime: float | None = None
        self._ensure_default_file()
        self._load()

    def _ensure_default_file(self) -> None:
        if self._path.exists():
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(DEFAULT_SNIPPETS, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("Snippets-Datei angelegt: %s", self._path)
        except OSError as e:
            logger.warning("Snippets-Default konnte nicht geschrieben werden: %s", e)

    def _load(self) -> None:
        with self._lock:
            try:
                if not self._path.exists():
                    self._snippets = {}
                    self._mtime = None
                    return
                mtime = self._path.stat().st_mtime
                if mtime == self._mtime:
                    return
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._snippets = {str(k): str(v) for k, v in data.items()}
                    self._mtime = mtime
                    logger.debug("Snippets neu geladen: %d Einträge", len(self._snippets))
                else:
                    logger.warning("Snippets-Datei: erwarte JSON-Object, ignoriere")
                    self._snippets = {}
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("Snippets konnten nicht gelesen werden: %s", e)

    def expand(self, text: str) -> str:
        if not text:
            return text
        self._load()
        with self._lock:
            snippets = dict(self._snippets)
        if not snippets:
            return text

        normalized = _normalize_slash_phrases(text)

        # Längere Keys zuerst, damit /sigplus nicht von /sig geschnappt wird.
        for key in sorted(snippets, key=len, reverse=True):
            if not key:
                continue
            # Token-Match: links Wortanfang oder Whitespace/Start, rechts kein Buchstabe/Ziffer.
            pattern = re.compile(
                rf"(?<![\w]){re.escape(key)}(?![\w])",
                re.IGNORECASE,
            )
            normalized = pattern.sub(lambda _m, v=snippets[key]: v, normalized)
        return normalized

    @property
    def file_path(self) -> Path:
        return self._path
