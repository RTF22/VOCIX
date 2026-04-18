import logging
import time

import keyboard
import pyperclip

from dictum.config import Config

logger = logging.getLogger(__name__)


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

        # Aktuelle Zwischenablage sichern
        try:
            original_clipboard = pyperclip.paste()
        except pyperclip.PyperclipException:
            original_clipboard = ""

        try:
            # Text in Zwischenablage
            pyperclip.copy(text)
            # Pause damit die Zwischenablage (und ggf. RDP-Sync) bereit ist
            time.sleep(self._clipboard_delay)
            # Ctrl+V senden
            keyboard.send("ctrl+v")
            # Pause damit die Anwendung den Paste verarbeiten kann
            # Bei längeren Texten brauchen manche Apps mehr Zeit
            extra_delay = len(text) / 5000  # ~0.2s pro 1000 Zeichen
            time.sleep(self._paste_delay + extra_delay)
            logger.info("Text eingefügt (%d Zeichen, paste_delay=%.2fs)",
                        len(text), self._paste_delay + extra_delay)
        except Exception as e:
            logger.error("Fehler beim Einfügen: %s", e)
            raise
        finally:
            # Zwischenablage wiederherstellen
            time.sleep(self._clipboard_delay)
            try:
                pyperclip.copy(original_clipboard)
            except pyperclip.PyperclipException:
                pass
