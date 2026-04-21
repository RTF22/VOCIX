"""Aggregierte Nutzungsstatistik (Diktate pro Tag/Modus, Wortzahl).

Persistiert in `%APPDATA%/VOCIX/stats.json`. Thread-safe.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from vocix.config import APP_DIR

logger = logging.getLogger(__name__)


def _stats_file() -> Path:
    appdata = os.getenv("APPDATA")
    base = Path(appdata) if appdata else APP_DIR
    return base / "VOCIX" / "stats.json"


STATS_FILE = _stats_file()

# Anschläge pro Minute beim Tippen — Annahme für gesparte-Zeit-Schätzung
TYPING_CHARS_PER_MINUTE = 200


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text, flags=re.UNICODE))


class Stats:
    def __init__(self, path: Path | None = None):
        self._path = path or STATS_FILE
        self._lock = threading.RLock()
        self._data: dict = self._load()

    def _load(self) -> dict:
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Stats konnten nicht gelesen werden: %s", e)
        return {}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            logger.warning("Stats konnten nicht gespeichert werden: %s", e)

    def record(self, text: str, mode: str) -> None:
        if not text:
            return
        words = _word_count(text)
        chars = len(text)
        today = date.today().isoformat()
        with self._lock:
            day = self._data.setdefault(today, {
                "words": 0, "chars": 0, "dictations": 0, "modes": {},
            })
            day["words"] += words
            day["chars"] += chars
            day["dictations"] += 1
            day["modes"][mode] = day["modes"].get(mode, 0) + 1
            self._save()

    def reset(self) -> None:
        with self._lock:
            self._data.clear()
            self._save()

    # --- Aggregationen ---

    def _sum_range(self, days: int) -> dict:
        cutoff = date.today() - timedelta(days=days - 1)
        words = chars = dictations = 0
        modes: dict[str, int] = {}
        with self._lock:
            for day_str, day in self._data.items():
                try:
                    d = datetime.strptime(day_str, "%Y-%m-%d").date()
                except ValueError:
                    continue
                if d < cutoff:
                    continue
                words += int(day.get("words", 0))
                chars += int(day.get("chars", 0))
                dictations += int(day.get("dictations", 0))
                for m, c in day.get("modes", {}).items():
                    modes[m] = modes.get(m, 0) + int(c)
        return {"words": words, "chars": chars, "dictations": dictations, "modes": modes}

    def today(self) -> dict:
        return self._sum_range(1)

    def week(self) -> dict:
        return self._sum_range(7)

    def total(self) -> dict:
        words = chars = dictations = 0
        modes: dict[str, int] = {}
        with self._lock:
            for day in self._data.values():
                words += int(day.get("words", 0))
                chars += int(day.get("chars", 0))
                dictations += int(day.get("dictations", 0))
                for m, c in day.get("modes", {}).items():
                    modes[m] = modes.get(m, 0) + int(c)
        return {"words": words, "chars": chars, "dictations": dictations, "modes": modes}

    @staticmethod
    def estimated_minutes_saved(chars: int) -> float:
        if chars <= 0:
            return 0.0
        return chars / TYPING_CHARS_PER_MINUTE
