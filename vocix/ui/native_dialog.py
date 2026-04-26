"""Native Windows-Dialoge via Win32 MessageBoxW.

Vermeidet zusätzliche tkinter-Roots — z.B. für den AVX-Fehler beim
Modellladen, bei dem das Status-Overlay noch nicht läuft. Der About-
Dialog läuft NICHT hier durch, sondern als Tk-Toplevel im Overlay-
Thread (siehe StatusOverlay.show_about), weil Win32-Dialoge aus der
pystray-Icon-Thread-Umgebung auf manchen Setups nicht zuverlässig auf
Klicks reagierten.
"""

from __future__ import annotations

import ctypes
import logging

logger = logging.getLogger(__name__)

# MessageBox-Flags (Win32)
_MB_OK = 0x00000000
_MB_ICONERROR = 0x00000010
_MB_ICONINFORMATION = 0x00000040
_MB_TOPMOST = 0x00040000

_IDOK = 1


def _message_box(title: str, body: str, flags: int) -> int:
    try:
        return int(ctypes.windll.user32.MessageBoxW(0, body, title, flags))
    except OSError as e:
        # Kein Windows / ctypes-Problem → Fallback auf stderr
        logger.warning("MessageBoxW failed: %s", e)
        print(f"\n[{title}]\n{body}\n")
        return _IDOK


def show_error(title: str, body: str) -> None:
    """Modaler Fehler-Dialog mit OK-Button. Blockiert bis der User quittiert."""
    _message_box(title, body, _MB_OK | _MB_ICONERROR | _MB_TOPMOST)


def show_info(title: str, body: str) -> None:
    """Modaler Info-Dialog mit OK-Button."""
    _message_box(title, body, _MB_OK | _MB_ICONINFORMATION | _MB_TOPMOST)
