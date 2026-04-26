"""Ringpuffer für die letzten Transkriptionen.

Persistiert in `%APPDATA%/VOCIX/history.json`. Thread-safe.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path

from vocix.config import APP_DIR

logger = logging.getLogger(__name__)


def _history_file() -> Path:
    appdata = os.getenv("APPDATA")
    base = Path(appdata) if appdata else APP_DIR
    return base / "VOCIX" / "history.json"


HISTORY_FILE = _history_file()

DEFAULT_LIMIT = 20


class History:
    def __init__(self, limit: int = DEFAULT_LIMIT, path: Path | None = None):
        self._limit = max(1, int(limit))
        self._path = path or HISTORY_FILE
        self._lock = threading.RLock()
        self._entries: list[dict] = self._load()

    def _load(self) -> list[dict]:
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return [e for e in data if isinstance(e, dict) and "text" in e][-self._limit:]
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to read history: %s", e)
        return []

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._entries, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            logger.warning("Failed to save history: %s", e)

    def add(self, text: str, mode: str) -> None:
        if not text or not text.strip():
            return
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "mode": mode,
            "text": text,
        }
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._limit:
                self._entries = self._entries[-self._limit:]
            self._save()

    def entries(self) -> list[dict]:
        """Neueste zuerst."""
        with self._lock:
            return list(reversed(self._entries))

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._save()

    def dump_text(self, path: Path | None = None) -> Path:
        """Schreibt eine menschlich lesbare Textdatei aller Einträge
        (neueste zuerst) und gibt den Pfad zurück."""
        target = path or self._path.with_suffix(".txt")
        with self._lock:
            entries = list(reversed(self._entries))
        lines = [f"VOCIX Verlauf — {len(entries)} Einträge", "=" * 50, ""]
        for e in entries:
            ts = e.get("ts", "")
            mode = e.get("mode", "")
            text = e.get("text", "")
            lines.append(f"[{ts}] ({mode})")
            lines.append(text)
            lines.append("")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("\n".join(lines), encoding="utf-8")
        except OSError as e:
            logger.warning("History text dump failed: %s", e)
        return target
