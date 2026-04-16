"""TextME — Sprachdiktion für Windows 11.

Push-to-Talk: Ctrl+Shift+Space halten → sprechen → loslassen.
Moduswechsel: Ctrl+Shift+1 (Clean) / 2 (Business) / 3 (Rage).
"""

import logging
import sys
import threading

import keyboard

from textme.audio.recorder import AudioRecorder
from textme.config import Config
from textme.output.injector import TextInjector
from textme.processing.base import TextProcessor
from textme.processing.business import BusinessProcessor
from textme.processing.clean import CleanProcessor
from textme.processing.rage import RageProcessor
from textme.stt.whisper_stt import WhisperSTT
from textme.ui.overlay import StatusOverlay
from textme.ui.tray import TrayApp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class TextMEApp:
    def __init__(self):
        self._config = Config()
        self._current_mode = self._config.default_mode
        self._running = True
        self._processing = False

        # Komponenten
        logger.info("Initialisiere TextME...")
        self._overlay = StatusOverlay(self._config)
        self._overlay.show("Lade Whisper-Modell...", "processing")

        self._recorder = AudioRecorder(self._config)
        self._stt = WhisperSTT(self._config)
        self._injector = TextInjector(self._config)

        # Prozessoren
        self._processors: dict[str, TextProcessor] = {
            "clean": CleanProcessor(),
            "business": BusinessProcessor(self._config),
            "rage": RageProcessor(self._config),
        }

        # Tray
        self._tray = TrayApp(
            current_mode=self._current_mode,
            on_mode_change=self._set_mode,
            on_quit=self._quit,
        )

        self._overlay.show_temporary("TextME bereit", "done")
        logger.info("TextME bereit — Modus: %s", self._current_mode)

    def _set_mode(self, mode: str) -> None:
        self._current_mode = mode
        self._tray.update_mode(mode)
        proc = self._processors.get(mode)
        name = proc.name if proc else mode
        self._overlay.show_temporary(f"Modus: {name}", "done")
        logger.info("Modus: %s", mode)

    def _on_record_start(self) -> None:
        if self._processing:
            return
        try:
            self._recorder.start()
            self._overlay.show("Aufnahme...", "recording")
        except RuntimeError as e:
            self._overlay.show_temporary(str(e), "error")

    def _on_record_stop(self) -> None:
        if not self._recorder.is_recording:
            return
        # Pipeline in separatem Thread, damit Hotkey-Handler nicht blockiert
        threading.Thread(target=self._process_pipeline, daemon=True).start()

    def _process_pipeline(self) -> None:
        self._processing = True
        try:
            audio = self._recorder.stop()
            if audio is None:
                self._overlay.show_temporary("Keine Sprache erkannt", "error")
                return

            # STT
            self._overlay.show("Transkribiere...", "processing")
            raw_text = self._stt.transcribe(audio)
            if not raw_text.strip():
                self._overlay.show_temporary("Kein Text erkannt", "error")
                return

            # Transformation
            processor = self._processors.get(self._current_mode, self._processors["clean"])
            self._overlay.show(f"Verarbeite ({processor.name})...", "processing")
            processed_text = processor.process(raw_text)

            if not processed_text.strip():
                self._overlay.show_temporary("Leeres Ergebnis", "error")
                return

            # Einfügen
            self._injector.inject(processed_text)
            self._overlay.show_temporary("Eingefügt", "done")

        except Exception as e:
            logger.error("Pipeline-Fehler: %s", e, exc_info=True)
            self._overlay.show_temporary("Fehler!", "error")
        finally:
            self._processing = False

    def _register_hotkeys(self) -> None:
        record_key = self._config.hotkey_record

        # Push-to-Talk: Erkennung ob Einzeltaste oder Kombination
        # Einzeltaste (z.B. "right ctrl", "f9"): on_press/on_release direkt
        # Kombination (z.B. "ctrl+shift+space"): letzte Taste als Trigger, Rest als Modifier
        if "+" in record_key:
            parts = [p.strip() for p in record_key.split("+")]
            trigger_key = parts[-1]
            modifier_keys = parts[:-1]

            def _check_and_start(e):
                if all(keyboard.is_pressed(mod) for mod in modifier_keys):
                    self._on_record_start()

            keyboard.on_press_key(trigger_key, _check_and_start, suppress=False)
            keyboard.on_release_key(trigger_key, lambda e: self._on_record_stop(), suppress=False)
        else:
            keyboard.on_press_key(record_key, lambda e: self._on_record_start(), suppress=False)
            keyboard.on_release_key(record_key, lambda e: self._on_record_stop(), suppress=False)

        # Moduswechsel
        keyboard.add_hotkey(self._config.hotkey_mode_a, lambda: self._set_mode("clean"))
        keyboard.add_hotkey(self._config.hotkey_mode_b, lambda: self._set_mode("business"))
        keyboard.add_hotkey(self._config.hotkey_mode_c, lambda: self._set_mode("rage"))

        logger.info("Hotkeys registriert: '%s' (PTT), %s/%s/%s (Modi)",
                     record_key,
                     self._config.hotkey_mode_a,
                     self._config.hotkey_mode_b,
                     self._config.hotkey_mode_c)

    def _quit(self) -> None:
        logger.info("TextME wird beendet...")
        self._running = False
        self._overlay.destroy()
        keyboard.unhook_all()

    def run(self) -> None:
        self._tray.start()
        self._register_hotkeys()

        logger.info("TextME läuft. Zum Beenden: Tray-Icon → Beenden")
        try:
            keyboard.wait()  # Blockiert bis alle Hooks entfernt werden
        except KeyboardInterrupt:
            self._quit()


def main():
    app = TextMEApp()
    app.run()


if __name__ == "__main__":
    main()
