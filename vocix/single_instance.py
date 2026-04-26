"""Single-Instance-Guard per Windows Named Mutex.

acquire() liefert True beim ersten Prozess und reserviert das Mutex-Handle
als Modul-Attribut bis zum Prozessende (Windows gibt das Mutex automatisch
beim Exit frei). Weitere Prozesse bekommen False und können gezielt
terminieren.
"""

import ctypes
import logging
import sys

logger = logging.getLogger(__name__)

# Bewusst session-lokal (kein "Global\"-Prefix): VOCIX startet pro Windows-User
# einmal. Bei schnellem Benutzerwechsel darf jeder User seine eigene Instanz
# haben — ein global eindeutiges Mutex würde das verhindern.
_MUTEX_NAME = "VOCIX-SingleInstance-Mutex-v1"
_ERROR_ALREADY_EXISTS = 183

_handle = None


def acquire() -> bool:
    global _handle
    if sys.platform != "win32":
        return True
    if _handle is not None:
        return True
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if not handle:
        logger.warning("CreateMutexW failed — single-instance guard inactive")
        return True
    if kernel32.GetLastError() == _ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False
    _handle = handle
    return True
