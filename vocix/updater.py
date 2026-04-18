"""Auto-Update-Check gegen GitHub Releases.

Prüft das neueste stabile Release im Repo RTF22/VOCIX und meldet ein
UpdateInfo zurück, wenn die verfügbare Version höher ist als die laufende
und nicht explizit vom User übersprungen wurde.
"""

import json
import logging
import threading
from dataclasses import dataclass
from typing import Callable
from urllib import error, request

logger = logging.getLogger(__name__)

_RELEASES_API = "https://api.github.com/repos/RTF22/VOCIX/releases/latest"
_REQUEST_TIMEOUT = 5.0


@dataclass(frozen=True)
class UpdateInfo:
    version: str   # normalisiert ohne 'v'-Prefix, z.B. "0.9.0"
    url: str       # html_url des Release
    notes: str     # Release-Notes (body), kann leer sein


def _parse_version(tag: str) -> tuple[int, int, int]:
    """'v0.9.0' oder '0.9.0' -> (0, 9, 0). Raised ValueError bei Fehlern."""
    s = tag.strip()
    if s.startswith(("v", "V")):
        s = s[1:]
    parts = s.split(".")
    if len(parts) != 3:
        raise ValueError(f"Unerwartetes Version-Format: {tag!r}")
    return tuple(int(p) for p in parts)  # type: ignore[return-value]


def _fetch_latest_release(current_version: str) -> dict | None:
    """Holt das latest Release von GitHub. Liefert None bei Fehlern."""
    req = request.Request(
        _RELEASES_API,
        headers={
            "User-Agent": f"VOCIX/{current_version}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with request.urlopen(req, timeout=_REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data
    except (error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as e:
        logger.warning("Update-Check fehlgeschlagen: %s", e)
        return None


def check_latest(
    current_version: str,
    skip_version: str | None = None,
) -> UpdateInfo | None:
    """Prüft GitHub auf neueres Release.

    Returns:
        UpdateInfo, wenn latest > current und latest != skip_version.
        None sonst (inkl. Netzwerkfehler).
    """
    data = _fetch_latest_release(current_version)
    if data is None:
        return None

    tag = data.get("tag_name", "")
    try:
        latest = _parse_version(tag)
        current = _parse_version(current_version)
    except ValueError as e:
        logger.warning("Version-Parse fehlgeschlagen: %s", e)
        return None

    if latest <= current:
        return None

    normalized = ".".join(str(x) for x in latest)
    if skip_version and skip_version.lstrip("vV") == normalized:
        logger.info("Update %s wurde vom User übersprungen", normalized)
        return None

    return UpdateInfo(
        version=normalized,
        url=data.get("html_url", ""),
        notes=data.get("body", "") or "",
    )


def check_async(
    current_version: str,
    skip_version: str | None,
    on_update_found: Callable[[UpdateInfo], None],
) -> threading.Thread:
    """Startet Daemon-Thread, ruft Callback nur bei verfügbarem Update."""
    def _run():
        try:
            info = check_latest(current_version, skip_version)
            if info is not None:
                on_update_found(info)
        except Exception as e:
            logger.error("Update-Thread-Fehler: %s", e, exc_info=True)

    thread = threading.Thread(target=_run, name="UpdateChecker", daemon=True)
    thread.start()
    return thread
