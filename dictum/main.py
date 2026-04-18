"""DICTUM — DICtation with Text Understanding & Modification.

Push-to-Talk: Rechte Strg halten → sprechen → loslassen.
Moduswechsel: Ctrl+Shift+1 (Clean) / 2 (Business) / 3 (Rage).
"""

import logging
import logging.handlers
import sys
import threading

import keyboard

from dictum import __version__
from dictum.audio.recorder import AudioRecorder
from dictum.config import Config
from dictum.output.injector import TextInjector
from dictum.processing.base import TextProcessor
from dictum.processing.business import BusinessProcessor
from dictum.processing.clean import CleanProcessor
from dictum.processing.rage import RageProcessor
from dictum.stt.whisper_stt import WhisperSTT
from dictum.ui.overlay import StatusOverlay
from dictum.ui.tray import TrayApp

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _setup_logging(config: Config) -> None:
    """Konfiguriert Logging auf Console + Logfile mit konfigurierbarem Level."""
    level = getattr(logging, config.log_level, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Console-Handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT))
    root_logger.addHandler(console)

    # Datei-Handler (RotatingFile: max 5 MB, 3 Backups)
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            config.log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT))
        root_logger.addHandler(file_handler)
    except OSError as e:
        root_logger.warning("Logfile konnte nicht erstellt werden: %s", e)


logger = logging.getLogger(__name__)


class DictumApp:
    def __init__(self):
        self._config = Config()
        _setup_logging(self._config)

        self._current_mode = self._config.default_mode
        self._running = True
        self._processing = False
        self._state_lock = threading.Lock()

        logger.info("=" * 50)
        logger.info("DICTUM v%s startet...", __version__)
        logger.info("Log-Level: %s | Logfile: %s", self._config.log_level, self._config.log_file)
        logger.info("Hotkey (PTT): %s", self._config.hotkey_record)
        logger.info("Standard-Modus: %s", self._config.default_mode)
        logger.info("API-Key: %s", "gesetzt" if self._config.anthropic_api_key else "NICHT gesetzt (Modus B/C → Fallback auf A)")
        if self._config.rdp_mode:
            logger.info("RDP-Modus: aktiv")
        logger.info("=" * 50)

        # Komponenten
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

        self._overlay.show_temporary("DICTUM bereit", "done")
        logger.info("DICTUM bereit — Modus: %s", self._current_mode)

    def _set_mode(self, mode: str) -> None:
        self._current_mode = mode
        self._tray.update_mode(mode)
        proc = self._processors.get(mode)
        name = proc.name if proc else mode
        self._overlay.show_temporary(f"Modus: {name}", "done")
        logger.info("Modus: %s", mode)

    def _on_record_start(self) -> None:
        # Key-Repeat: Windows feuert on_press_key kontinuierlich, solange die
        # Taste gehalten wird. Wenn Recorder bereits läuft, Event geräuschlos
        # verwerfen (keine Logmessages, kein Overlay-Redraw).
        if self._recorder.is_recording:
            return
        with self._state_lock:
            if self._processing:
                logger.debug("Aufnahme ignoriert — Pipeline läuft noch")
                return
        try:
            self._recorder.start()
            self._overlay.show("Aufnahme...", "recording")
            logger.info(">> Aufnahme gestartet (Hotkey gedrückt)")
        except RuntimeError as e:
            logger.error("Aufnahme fehlgeschlagen: %s", e)
            self._overlay.show_temporary(str(e), "error")

    def _on_record_stop(self) -> None:
        if not self._recorder.is_recording:
            return
        with self._state_lock:
            if self._processing:
                return  # Pipeline läuft bereits — zweiten Stop ignorieren
            self._processing = True
            # Modus beim Aufnahmeende einfrieren, damit ein Moduswechsel
            # während STT/Processing die laufende Pipeline nicht beeinflusst
            mode_snapshot = self._current_mode
        logger.info(">> Aufnahme beendet (Hotkey losgelassen)")
        # Pipeline in separatem Thread, damit Hotkey-Handler nicht blockiert
        threading.Thread(target=self._process_pipeline, args=(mode_snapshot,), daemon=True).start()

    def _process_pipeline(self, mode: str) -> None:
        try:
            audio = self._recorder.stop()
            if audio is None:
                logger.warning("Keine verwertbare Aufnahme (zu kurz oder zu leise)")
                self._overlay.show_temporary("Keine Sprache erkannt", "error")
                return

            duration = len(audio) / self._config.sample_rate
            logger.info("   Audio: %.1fs aufgenommen", duration)

            # STT
            self._overlay.show("Transkribiere...", "processing")
            raw_text = self._stt.transcribe(audio)
            if not raw_text.strip():
                logger.warning("STT lieferte leeren Text")
                self._overlay.show_temporary("Kein Text erkannt", "error")
                return

            logger.info("   Rohtext: \"%s\"", raw_text[:100] + ("..." if len(raw_text) > 100 else ""))

            # Transformation — Modus-Snapshot vom Aufnahmeende verwenden
            processor = self._processors.get(mode, self._processors["clean"])
            self._overlay.show(f"Verarbeite ({processor.name})...", "processing")
            processed_text = processor.process(raw_text)

            if not processed_text.strip():
                logger.warning("Prozessor lieferte leeres Ergebnis")
                self._overlay.show_temporary("Leeres Ergebnis", "error")
                return

            logger.info("   Ergebnis (%s): \"%s\"", processor.name,
                        processed_text[:100] + ("..." if len(processed_text) > 100 else ""))

            # Einfügen
            self._injector.inject(processed_text)
            self._overlay.show_temporary("Eingefügt", "done")
            logger.info("   Text eingefügt (%d Zeichen)", len(processed_text))

        except Exception as e:
            logger.error("Pipeline-Fehler: %s", e, exc_info=True)
            self._overlay.show_temporary("Fehler!", "error")
        finally:
            with self._state_lock:
                self._processing = False

    def _register_hotkeys(self) -> None:
        # Push-to-Talk: Einzeltaste via on_press_key/on_release_key. Kombos
        # werden bereits in Config.__post_init__ abgelehnt (ADR 004).
        record_key = self._config.hotkey_record
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
        logger.info("DICTUM wird beendet...")
        self._running = False
        keyboard.unhook_all()
        try:
            self._tray.stop()
        except Exception as e:
            logger.warning("Tray-Stop fehlgeschlagen: %s", e)
        self._overlay.destroy()
        # tkinter-Thread kurz Zeit geben, sauber abzuräumen
        overlay_thread = getattr(self._overlay, "_thread", None)
        if overlay_thread is not None:
            overlay_thread.join(timeout=1.0)
        sys.exit(0)

    def run(self) -> None:
        self._tray.start()
        self._register_hotkeys()

        logger.info("DICTUM läuft. Zum Beenden: Tray-Icon → Beenden")
        try:
            keyboard.wait()  # Blockiert bis alle Hooks entfernt werden
        except KeyboardInterrupt:
            self._quit()


def main():
    app = DictumApp()
    app.run()


if __name__ == "__main__":
    main()
