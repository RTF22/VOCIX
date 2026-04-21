"""Native Windows-Dialoge via Win32 MessageBoxW.

Vermeidet zusätzliche tkinter-Roots — z.B. für den About-Dialog und den
AVX-Fehler beim Modellladen, bei dem das Status-Overlay noch nicht läuft.
"""

from __future__ import annotations

import ctypes
import logging

logger = logging.getLogger(__name__)

# MessageBox-Flags (Win32)
_MB_OK = 0x00000000
_MB_OKCANCEL = 0x00000001
_MB_YESNO = 0x00000004
_MB_ICONERROR = 0x00000010
_MB_ICONINFORMATION = 0x00000040
_MB_SYSTEMMODAL = 0x00001000
_MB_TOPMOST = 0x00040000

_IDOK = 1
_IDYES = 6


def _message_box(title: str, body: str, flags: int) -> int:
    try:
        return int(ctypes.windll.user32.MessageBoxW(0, body, title, flags))
    except OSError as e:
        # Kein Windows / ctypes-Problem → Fallback auf stderr
        logger.warning("MessageBoxW fehlgeschlagen: %s", e)
        print(f"\n[{title}]\n{body}\n")
        return _IDOK


def show_error(title: str, body: str) -> None:
    """Modaler Fehler-Dialog mit OK-Button. Blockiert bis der User quittiert."""
    _message_box(title, body, _MB_OK | _MB_ICONERROR | _MB_TOPMOST)


def show_info_with_link(title: str, body: str) -> bool:
    """Info-Dialog mit Ja/Nein (Ja = „Browser öffnen"). Gibt True zurück bei Ja."""
    result = _message_box(title, body, _MB_YESNO | _MB_ICONINFORMATION | _MB_TOPMOST)
    return result == _IDYES


def show_info(title: str, body: str) -> None:
    """Modaler Info-Dialog mit OK-Button."""
    _message_box(title, body, _MB_OK | _MB_ICONINFORMATION | _MB_TOPMOST)
