import ctypes
import logging
import time

import keyboard
import pyperclip

from vocix.config import Config
from vocix.i18n import t

logger = logging.getLogger(__name__)

# Windows Clipboard-Format-IDs (Win32 API)
_CF_UNICODETEXT = 13


class TextInjector:
    """Fügt Text an der aktuellen Cursorposition ein (systemweit).

    Methode: Zwischenablage sichern → Text kopieren → Ctrl+V → Zwischenablage wiederherstellen.
    Dies ist die einzige Methode, die zuverlässig in allen Windows-Anwendungen
    funktioniert, einschließlich Umlaute und Sonderzeichen.

    Im RDP-Modus werden längere Delays verwendet, da die Clipboard-Synchronisation
    zwischen lokalem und Remote-Rechner Zeit benötigt.
    """

    def __init__(self, config: Config):
        self._clipboard_delay = config.clipboard_delay
        self._paste_delay = config.paste_delay
        if config.rdp_mode:
            logger.info("TextInjector: RDP-Modus aktiv (clipboard_delay=%.2fs, paste_delay=%.2fs)",
                        self._clipboard_delay, self._paste_delay)

    def inject(self, text: str) -> None:
        if not text.strip():
            logger.warning("Leerer Text, nichts einzufügen")
            return

        # None signalisiert "Restore überspringen" — pyperclip.paste() liefert bei
        # Bild/Datei-Clipboards "", der Restore würde den Nicht-Text-Inhalt zerstören.
        user32 = ctypes.windll.user32
        has_text = bool(user32.IsClipboardFormatAvailable(_CF_UNICODETEXT))
        if has_text:
            try:
                original_clipboard = pyperclip.paste()
            except pyperclip.PyperclipException:
                original_clipboard = None
        else:
            original_clipboard = None
            if user32.CountClipboardFormats() > 0:
                logger.warning(t("error.clipboard_nontext"))

        try:
            # Text in Zwischenablage
            pyperclip.copy(text)
            # Pause damit die Zwischenablage (und ggf. RDP-Sync) bereit ist
            time.sleep(self._clipboard_delay)
            # Ctrl+V senden
            keyboard.send("ctrl+v")
            # Pause damit die Anwendung den Paste verarbeiten kann.
            # Bei längeren Texten brauchen manche Apps mehr Zeit (~0.2s pro 1000
            # Zeichen), aber bei 2 s abgeriegelt — sonst fühlt sich die App nach
            # einem langen Diktat/Business-Output wie eingefroren an.
            extra_delay = min(len(text) / 5000, 2.0)
            time.sleep(self._paste_delay + extra_delay)
            logger.info("Text eingefügt (%d Zeichen, paste_delay=%.2fs)",
                        len(text), self._paste_delay + extra_delay)
        except Exception as e:
            logger.error("Fehler beim Einfügen: %s", e)
            raise
        finally:
            time.sleep(self._clipboard_delay)
            if original_clipboard is not None:
                try:
                    pyperclip.copy(original_clipboard)
                except pyperclip.PyperclipException:
                    pass
