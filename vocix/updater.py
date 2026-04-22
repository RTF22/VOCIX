"""Auto-Update gegen GitHub Releases.

Prüft das neueste stabile Release im Repo RTF22/VOCIX und meldet ein
UpdateInfo zurück, wenn die verfügbare Version höher ist als die laufende
und nicht explizit vom User übersprungen wurde.

Zusätzlich: Download des Release-ZIPs, SHA256-Verifikation und Spawn eines
Helper-Batches, der nach Beenden von VOCIX die Dateien austauscht und neu
startet. Nur sinnvoll im PyInstaller-Bundle (`sys.frozen`).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib import error, request

logger = logging.getLogger(__name__)

_RELEASES_API = "https://api.github.com/repos/RTF22/VOCIX/releases/latest"
_REQUEST_TIMEOUT = 5.0
_DOWNLOAD_TIMEOUT = 60.0
_ASSET_PATTERN = re.compile(r"^VOCIX-v\d+\.\d+\.\d+-win-x64\.zip$", re.IGNORECASE)


@dataclass(frozen=True)
class UpdateInfo:
    version: str             # normalisiert ohne 'v'-Prefix, z.B. "0.9.0"
    url: str                 # html_url des Release
    notes: str               # Release-Notes (body), kann leer sein
    asset_url: str = ""      # browser_download_url des Win-x64-ZIPs
    asset_name: str = ""     # Dateiname des Assets
    sha256: str | None = None  # erwarteter SHA256 (lowercase hex), wenn von der API geliefert


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
    req = request.Request(
        _RELEASES_API,
        headers={
            "User-Agent": f"VOCIX/{current_version}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with request.urlopen(req, timeout=_REQUEST_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as e:
        logger.warning("Update-Check fehlgeschlagen: %s", e)
        return None


def _pick_asset(data: dict) -> tuple[str, str, str | None]:
    """Sucht das Win-x64-ZIP im Release. Returnt (url, name, sha256?)."""
    for asset in data.get("assets", []) or []:
        name = asset.get("name", "")
        if _ASSET_PATTERN.match(name):
            url = asset.get("browser_download_url", "") or ""
            digest = asset.get("digest", "") or ""
            sha = None
            if digest.lower().startswith("sha256:"):
                sha = digest.split(":", 1)[1].strip().lower() or None
            return url, name, sha
    return "", "", None


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

    asset_url, asset_name, sha256 = _pick_asset(data)
    return UpdateInfo(
        version=normalized,
        url=data.get("html_url", ""),
        notes=data.get("body", "") or "",
        asset_url=asset_url,
        asset_name=asset_name,
        sha256=sha256,
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


# ---------------------------------------------------------------------------
# Download / Install
# ---------------------------------------------------------------------------


def is_frozen_bundle() -> bool:
    """True nur, wenn als PyInstaller-Bundle ausgeführt — dann ist Auto-Install
    sinnvoll. Im Source-Run gibt's keine .exe, die ersetzt werden könnte."""
    return bool(getattr(sys, "frozen", False))


def install_dir() -> Path:
    """Verzeichnis, in dem die laufende VOCIX-EXE liegt."""
    return Path(sys.executable).resolve().parent


def download_asset(
    info: UpdateInfo,
    dest_dir: Path,
    progress_cb: Callable[[int, int], None] | None = None,
) -> Path:
    """Lädt das Release-ZIP. Raised RuntimeError bei Fehlern."""
    if not info.asset_url:
        raise RuntimeError("Kein Asset-URL im Release gefunden")
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / (info.asset_name or "vocix-update.zip")

    req = request.Request(
        info.asset_url,
        headers={"User-Agent": f"VOCIX-updater/{info.version}"},
    )
    try:
        with request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT) as resp, open(target, "wb") as out:
            total = int(resp.headers.get("Content-Length", 0) or 0)
            downloaded = 0
            chunk = 64 * 1024
            while True:
                buf = resp.read(chunk)
                if not buf:
                    break
                out.write(buf)
                downloaded += len(buf)
                if progress_cb is not None:
                    try:
                        progress_cb(downloaded, total)
                    except Exception:
                        pass
    except (error.URLError, TimeoutError, OSError) as e:
        raise RuntimeError(f"Download fehlgeschlagen: {e}") from e
    return target


def verify_sha256(path: Path, expected: str | None) -> bool:
    """True bei Match oder wenn kein Expected gesetzt."""
    if not expected:
        logger.warning("Kein erwarteter SHA256 — überspringe Verifikation für %s", path.name)
        return True
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    actual = h.hexdigest().lower()
    expected = expected.strip().lower()
    if actual != expected:
        logger.error("SHA256-Mismatch: erwartet=%s, tatsächlich=%s", expected, actual)
        return False
    return True


def _extract_payload(zip_path: Path, work_dir: Path) -> Path:
    """Entpackt das ZIP in work_dir und liefert den Pfad zum Inhalt der
    inneren VOCIX/-Verzeichnisses (Quelle für den späteren xcopy)."""
    work_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(work_dir)
    inner = work_dir / "VOCIX"
    if inner.is_dir():
        return inner
    # Fallback: ZIP enthält Inhalt direkt ohne VOCIX-Wrapper
    return work_dir


_HELPER_BATCH_TEMPLATE = """@echo off
setlocal
set "PID={pid}"
set "STAGING={staging}"
set "TARGET={target}"
set "EXE={exe}"
set "LOG=%TEMP%\\vocix-update.log"

echo [%date% %time%] Updater gestartet, warte auf PID %PID% > "%LOG%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "try {{ Wait-Process -Id %PID% -Timeout 30 -ErrorAction Stop }} catch {{ }}" >>"%LOG%" 2>&1

powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-Process -Id %PID% -ErrorAction SilentlyContinue) {{ Stop-Process -Id %PID% -Force }}" >>"%LOG%" 2>&1

timeout /t 2 /nobreak >NUL

echo [%date% %time%] VOCIX beendet, kopiere Dateien >> "%LOG%"
xcopy /E /I /Y /Q "%STAGING%\\*" "%TARGET%\\" >>"%LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] xcopy fehlgeschlagen >> "%LOG%"
    goto end
)

echo [%date% %time%] Starte %TARGET%\\%EXE% >> "%LOG%"
start "" "%TARGET%\\%EXE%"

:end
rd /s /q "%STAGING%" 2>NUL
endlocal
(goto) 2>nul & del "%~f0"
"""


def _write_helper_batch(staging: Path, target: Path, exe_name: str, pid: int) -> Path:
    """Schreibt den Helper-Batch in %TEMP% und gibt seinen Pfad zurück."""
    temp = Path(tempfile.gettempdir()) / f"vocix-update-{pid}.bat"
    content = _HELPER_BATCH_TEMPLATE.format(
        pid=pid,
        staging=str(staging),
        target=str(target),
        exe=exe_name,
    )
    temp.write_text(content, encoding="ascii", errors="replace")
    return temp


def install_update(
    info: UpdateInfo,
    progress_cb: Callable[[int, int], None] | None = None,
    target_dir: Path | None = None,
    exe_name: str = "VOCIX.exe",
    spawn: bool = True,
) -> Path:
    """Vollständiger Update-Flow: Download → SHA256 → Extract → Helper-Batch.

    Bei Erfolg ist der Helper-Batch gestartet (sofern spawn=True) und der Caller
    sollte die App sauber beenden, damit der Helper die Dateien austauschen
    kann. Returnt den Pfad zum geschriebenen Batch.
    """
    if not is_frozen_bundle():
        raise RuntimeError("Auto-Update nur im PyInstaller-Bundle verfügbar")

    target = (target_dir or install_dir()).resolve()
    work_root = Path(tempfile.mkdtemp(prefix=f"vocix-update-{info.version}-"))
    try:
        zip_path = download_asset(info, work_root, progress_cb=progress_cb)
        if not verify_sha256(zip_path, info.sha256):
            raise RuntimeError("SHA256-Verifikation fehlgeschlagen")

        extract_dir = work_root / "extracted"
        staging = _extract_payload(zip_path, extract_dir)
        # ZIP nach Erfolg löschen, damit der Helper nicht unnötig kopiert
        try:
            zip_path.unlink()
        except OSError:
            pass

        batch = _write_helper_batch(staging, target, exe_name, os.getpid())
        if spawn:
            _spawn_detached(batch)
        return batch
    except Exception:
        # Bei Fehler Workdir aufräumen — Erfolgsfall macht der Helper selbst
        shutil.rmtree(work_root, ignore_errors=True)
        raise


def _spawn_detached(batch: Path) -> None:
    """Startet den Batch losgelöst, ohne sichtbares Fenster."""
    flags = 0
    if os.name == "nt":
        # CREATE_NO_WINDOW. Nicht mit DETACHED_PROCESS kombinieren —
        # die Flags sind laut Win32-Doku mutually exclusive und führen
        # sonst zu undefiniertem Verhalten (sichtbare Console).
        flags = 0x08000000
    subprocess.Popen(
        ["cmd.exe", "/c", str(batch)],
        creationflags=flags,
        close_fds=True,
        shell=False,
    )
