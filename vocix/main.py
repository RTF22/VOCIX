"""VOCIX — Voice Capture & Intelligent eXpression.

Push-to-Talk: Pause halten → sprechen → loslassen (Hotkey konfigurierbar via VOCIX_HOTKEY_RECORD).
Moduswechsel: Ctrl+Shift+1 (Clean) / 2 (Business) / 3 (Rage).
"""

import gc
import logging
import logging.handlers
import os
import sys
import threading
import time
from dataclasses import replace

import keyboard

from vocix import __version__, i18n, single_instance, updater
from vocix.audio.recorder import AudioRecorder
from vocix.config import Config, load_state, update_state
from vocix.history import History
from vocix.i18n import t
from vocix.output.injector import TextInjector
from vocix.snippets import SnippetExpander
from vocix.stats import Stats
from vocix import wakeword
from vocix.processing.base import TextProcessor
from vocix.processing.business import BusinessProcessor
from vocix.processing.clean import CleanProcessor
from vocix.processing.rage import RageProcessor
from vocix.stt.whisper_stt import WhisperSTT, cuda_available
from vocix.ui import native_dialog
from vocix.ui.overlay import StatusOverlay
from vocix.ui.tray import TrayApp

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


class VocixApp:
    _STATE_PERSISTED_FIELDS = (
        "language", "whisper_model", "whisper_acceleration", "translate_to_english",
        "default_mode", "hotkey_record", "hotkey_mode_a", "hotkey_mode_b", "hotkey_mode_c",
        "log_level", "log_file", "whisper_model_dir",
        "overlay_display_seconds",
        "rdp_mode", "clipboard_delay", "paste_delay",
        "silence_threshold", "min_duration", "sample_rate",
        "anthropic_api_key", "anthropic_model", "anthropic_timeout",
        "whisper_language_override",
    )

    def __init__(self):
        self._config = Config.load()
        _setup_logging(self._config)
        i18n.set_language(self._config.language)

        self._current_mode = self._config.default_mode
        self._running = True
        self._processing = False
        self._state_lock = threading.Lock()
        self._quit_event = threading.Event()

        logger.info("=" * 50)
        logger.info("VOCIX v%s startet...", __version__)
        logger.info("Log-Level: %s | Logfile: %s", self._config.log_level, self._config.log_file)
        logger.info("Hotkey (PTT): %s", self._config.hotkey_record)
        logger.info("Standard-Modus: %s", self._config.default_mode)
        logger.info("API-Key: %s", "gesetzt" if self._config.anthropic_api_key else "NICHT gesetzt (Modus B/C → Fallback auf A)")
        if self._config.rdp_mode:
            logger.info("RDP-Modus: aktiv")
        logger.info("=" * 50)

        # Komponenten
        self._overlay = StatusOverlay(self._config)
        self._overlay.show(t("overlay.loading_model"), "processing")

        self._recorder = AudioRecorder(self._config)
        self._overlay.set_level_source(lambda: self._recorder.current_level)
        try:
            self._stt = WhisperSTT(self._config)
        except Exception as e:
            # Pre-AVX-CPU oder fehlende CUDA-Libs bei explizitem GPU-Wunsch.
            # Wenn der User "gpu" forciert hat, retten wir den Start mit CPU
            # und melden im Overlay — sonst harter Abbruch mit nativem Dialog.
            logger.critical("Whisper-Modell konnte nicht geladen werden: %s", e, exc_info=True)
            if self._config.whisper_acceleration == "gpu":
                logger.warning("GPU-Erzwingung schlug fehl — wechsle dauerhaft auf CPU")
                self._config.whisper_acceleration = "cpu"
                with update_state() as state:
                    state["whisper_acceleration"] = "cpu"
                try:
                    self._stt = WhisperSTT(self._config)
                    self._overlay.show_temporary(t("overlay.gpu_unavailable"), "error")
                except Exception as e2:
                    native_dialog.show_error(
                        t("error.cpu_unsupported_title"),
                        t("error.cpu_unsupported_body", details=str(e2)[:200]),
                    )
                    sys.exit(1)
            else:
                native_dialog.show_error(
                    t("error.cpu_unsupported_title"),
                    t("error.cpu_unsupported_body", details=str(e)[:200]),
                )
                sys.exit(1)
        self._stt_reload_lock = threading.Lock()
        self._injector = TextInjector(self._config)
        self._history = History()
        self._stats = Stats()
        self._snippets = SnippetExpander()
        self._wakeword: wakeword.WakeWordListener | None = None
        self._wakeword_enabled = bool(load_state().get("wakeword_enabled", False))

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
            on_language_change=self._set_language,
            current_language=self._config.language,
            on_translate_toggle=self._set_translate,
            translate_to_english=self._config.translate_to_english,
            history=self._history,
            stats=self._stats,
            snippets=self._snippets,
            on_history_reinject=self._reinject_text,
            on_install_update=self._install_update,
            wakeword_available=wakeword.is_available(),
            wakeword_enabled=self._wakeword_enabled,
            on_wakeword_toggle=self._set_wakeword_enabled,
            on_show_about=self._show_about,
            on_show_stats=self._overlay.show_stats,
            on_overlay_message=self._overlay.show_temporary,
            current_whisper_model=self._config.whisper_model,
            on_whisper_model_change=self._set_whisper_model,
            current_whisper_acceleration=self._config.whisper_acceleration,
            on_whisper_acceleration_change=self._set_whisper_acceleration,
            cuda_available=cuda_available(),
            on_open_settings=self.open_settings,
        )

        self._overlay.show_temporary(t("overlay.ready"), "done")
        logger.info("VOCIX bereit — Modus: %s | Sprache: %s",
                    self._current_mode, self._config.language)

    def _set_mode(self, mode: str) -> None:
        self._current_mode = mode
        self._tray.update_mode(mode)
        proc = self._processors.get(mode)
        name = proc.name if proc else mode
        self._overlay.show_temporary(t("overlay.mode_switched", name=name), "done")
        logger.info("Modus: %s", mode)

    def _set_language(self, code: str) -> None:
        """Tray-Callback: UI + Whisper-STT + Prozessor-Prompts umschalten."""
        if code == self._config.language:
            return
        i18n.set_language(code)
        self._config.language = code
        with update_state() as state:
            state["language"] = code
        # Tray-Menü neu aufbauen (Labels jetzt in neuer Sprache)
        self._tray.update_language(code)
        self._overlay.show_temporary(t("overlay.ready"), "done")
        logger.info("Sprache gewechselt: %s", code)

    def _set_whisper_model(self, model: str) -> None:
        if model == self._config.whisper_model:
            return
        self._reload_stt(model=model)

    def _set_whisper_acceleration(self, acceleration: str) -> None:
        if acceleration == self._config.whisper_acceleration:
            return
        self._reload_stt(acceleration=acceleration)

    def _reload_stt(self, model: str | None = None, acceleration: str | None = None) -> None:
        """Lädt WhisperSTT mit neuem Modell/Beschleunigung in einem Worker-Thread.

        Pipeline-Aufrufe in einem parallelen Thread halten ihre eigene Referenz
        auf das alte STT-Objekt — der Tausch hier ist also race-frei. Ein zweiter
        Reload-Versuch während eines laufenden Reloads wird abgewiesen.
        """
        target_model = model if model is not None else self._config.whisper_model
        target_accel = acceleration if acceleration is not None else self._config.whisper_acceleration

        def _worker():
            if not self._stt_reload_lock.acquire(blocking=False):
                self._overlay.show_temporary(t("overlay.model_reload_busy"), "error")
                return
            try:
                self._overlay.show(t("overlay.loading_model_named", name=target_model), "processing")
                new_config = replace(
                    self._config,
                    whisper_model=target_model,
                    whisper_acceleration=target_accel,
                )
                try:
                    new_stt = WhisperSTT(new_config)
                except Exception as e:
                    logger.error("Modellwechsel fehlgeschlagen (model=%s, accel=%s): %s",
                                 target_model, target_accel, e, exc_info=True)
                    self._overlay.show_temporary(
                        t("overlay.model_load_failed_active", active=self._config.whisper_model),
                        "error",
                    )
                    return
                old_stt = self._stt
                self._stt = new_stt
                self._config = new_config
                # CUDA-VRAM des alten Modells deterministisch freigeben — sonst
                # bleibt es belegt, bis der Pipeline-Thread seine Referenz fallen
                # lässt (auf 4 GB-Karten OOM-Risiko bei large→tiny-Wechsel).
                del old_stt
                gc.collect()
                with update_state() as state:
                    state["whisper_model"] = target_model
                    state["whisper_acceleration"] = target_accel
                self._tray.update_whisper_settings(
                    model=target_model,
                    acceleration=target_accel,
                )
                logger.info("Whisper-STT neu geladen: model=%s, device=%s",
                            target_model, new_stt.device)
                self._overlay.show_temporary(
                    t("overlay.model_loaded", name=target_model, device=new_stt.device.upper()),
                    "done",
                )
            finally:
                self._stt_reload_lock.release()

        threading.Thread(target=_worker, daemon=True).start()

    def _set_translate(self, enabled: bool) -> None:
        self._config.translate_to_english = enabled
        with update_state() as state:
            state["translate_to_english"] = enabled
        logger.info("Translate-to-English: %s", enabled)

    def _reinject_text(self, text: str) -> None:
        """Tray-Callback: einen History-Eintrag erneut einfügen.

        Läuft im Tray-Thread; lange Inject-Delays würden das Menü blockieren,
        daher in eigenen Thread auslagern.
        """
        def _worker():
            try:
                self._injector.inject(text)
                self._overlay.show_temporary(t("overlay.inserted"), "done")
            except Exception as e:
                logger.error("Re-Inject fehlgeschlagen: %s", e, exc_info=True)
                self._overlay.show_temporary(t("overlay.error"), "error")
        threading.Thread(target=_worker, daemon=True).start()

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
            badge = t("overlay.translate_badge") if self._config.translate_to_english else None
            self._overlay.show(t("overlay.recording"), "recording", badge=badge)
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
                self._overlay.show_temporary(t("overlay.no_speech"), "error")
                return

            duration = len(audio) / self._config.sample_rate
            logger.info("   Audio: %.1fs aufgenommen", duration)

            # STT
            self._overlay.show(t("overlay.transcribing"), "processing")
            raw_text = self._stt.transcribe(audio)
            if not raw_text.strip():
                logger.warning("STT lieferte leeren Text")
                self._overlay.show_temporary(t("overlay.no_text"), "error")
                return

            logger.info("   Rohtext: \"%s\"", raw_text[:100] + ("..." if len(raw_text) > 100 else ""))

            # Transformation — Modus-Snapshot vom Aufnahmeende verwenden
            processor = self._processors.get(mode, self._processors["clean"])
            self._overlay.show(t("overlay.processing", name=processor.name), "processing")
            processed_text = processor.process(raw_text)

            if not processed_text.strip():
                logger.warning("Prozessor lieferte leeres Ergebnis")
                self._overlay.show_temporary(t("overlay.empty_result"), "error")
                return

            # Snippet-Expansion (z.B. /sig → Signatur). Läuft nach dem Modus-
            # Prozessor, sodass Claude den Platzhalter unangetastet lässt.
            processed_text = self._snippets.expand(processed_text)

            logger.info("   Ergebnis (%s): \"%s\"", processor.name,
                        processed_text[:100] + ("..." if len(processed_text) > 100 else ""))

            # Einfügen
            self._injector.inject(processed_text)
            self._overlay.show_temporary(t("overlay.inserted"), "done")
            logger.info("   Text eingefügt (%d Zeichen)", len(processed_text))

            # History + Stats nach erfolgreichem Inject
            self._history.add(processed_text, mode)
            self._stats.record(processed_text, mode)
            self._tray.refresh_history()

        except Exception as e:
            logger.error("Pipeline-Fehler: %s", e, exc_info=True)
            self._overlay.show_temporary(t("overlay.error"), "error")
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

    def _rebind_hotkeys(self) -> None:
        """Hotkeys nach einer Settings-Änderung neu binden.

        `keyboard.unhook_all()` wirft alle vorhandenen Bindings weg, danach
        registriert `_register_hotkeys()` PTT- und Modus-Hotkeys aus der
        aktuellen Config neu.
        """
        keyboard.unhook_all()
        self._register_hotkeys()

    def apply_settings(self, new_config) -> None:
        """Übernimmt einen neuen Config-Stand: persistieren, dann selektiv
        Whisper neu laden, Hotkeys neu binden, Sprache umschalten, Tray
        refreshen — abhängig vom Diff zur alten Config."""
        old = self._config

        with update_state() as s:
            for field_name in self._STATE_PERSISTED_FIELDS:
                s[field_name] = getattr(new_config, field_name)

        self._config = new_config

        if old.language != new_config.language:
            i18n.set_language(new_config.language)

        if (old.whisper_model != new_config.whisper_model
            or old.whisper_acceleration != new_config.whisper_acceleration
            or old.whisper_model_dir != new_config.whisper_model_dir):
            self._reload_stt()

        any_diff = any(
            getattr(old, f) != getattr(new_config, f)
            for f in self._STATE_PERSISTED_FIELDS
        )
        if any_diff:
            self._rebind_hotkeys()

        if self._tray is not None:
            self._tray.refresh()

    def open_settings(self) -> None:
        """Tray-Callback: Settings-Dialog im Overlay-Tk-Thread öffnen."""
        if self._overlay is not None:
            self._overlay.show_settings(self._config, self.apply_settings)

    def _quit(self) -> None:
        logger.info("VOCIX wird beendet...")
        self._running = False
        if self._wakeword is not None:
            self._wakeword.stop()
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
        # Main-Thread aus run() entlassen. sys.exit() hier wirkt nur im
        # Tray-Thread (Daemon) und würde den Prozess nicht beenden.
        self._quit_event.set()

    def _show_about(self) -> None:
        """Tray-Callback: About-Dialog im Overlay-Tk-Thread öffnen."""
        self._overlay.show_about(
            title=t("about.title"),
            version=f"VOCIX v{__version__}",
            tagline=t("about.tagline"),
            description=t("about.description"),
            url="https://vocix.de",
        )

    def _set_wakeword_enabled(self, enabled: bool) -> None:
        """Tray-Toggle: Wake-Word ein/aus. Persistiert in state.json."""
        self._wakeword_enabled = enabled
        with update_state() as state:
            state["wakeword_enabled"] = enabled
        if enabled:
            self._start_wakeword()
        else:
            self._stop_wakeword()

    def _start_wakeword(self) -> None:
        if not wakeword.is_available():
            logger.warning("Wake-Word angefordert, aber openwakeword fehlt")
            self._overlay.show_temporary(t("overlay.wakeword_unavailable"), "error")
            return
        if self._wakeword is None:
            self._wakeword = wakeword.WakeWordListener(on_detect=self._on_wakeword_triggered)
        try:
            self._wakeword.start()
            self._overlay.show_temporary(t("overlay.wakeword_on"), "done")
        except Exception as e:
            logger.error("Wake-Word-Start fehlgeschlagen: %s", e, exc_info=True)
            self._overlay.show_temporary(t("overlay.error"), "error")

    def _stop_wakeword(self) -> None:
        if self._wakeword is not None:
            self._wakeword.stop()
        self._overlay.show_temporary(t("overlay.wakeword_off"), "done")

    def _on_wakeword_triggered(self) -> None:
        """Vom Listener-Thread aufgerufen, sobald das Wake-Word fällt.

        Startet die Aufnahme wie ein PTT-Press und überwacht den RMS-Pegel —
        nach `silence_seconds` ohne Signal wird die Pipeline ausgelöst.
        """
        if self._recorder.is_recording:
            return
        with self._state_lock:
            if self._processing:
                return
        self._on_record_start()
        threading.Thread(
            target=self._wakeword_silence_watch,
            args=(self._current_mode,),
            name="WakeWordSilenceWatch",
            daemon=True,
        ).start()

    def _wakeword_silence_watch(self, mode: str) -> None:
        """Stoppt die Aufnahme automatisch nach Stille — Pendant zum PTT-Release.

        - `min_speech_seconds` muss erst Sprache erkannt worden sein, bevor
          Stille überhaupt zählt (sonst stoppt es noch vor dem ersten Wort).
        - `silence_seconds` ununterbrochene Stille = Pipeline auslösen.
        - `max_seconds` als Sicherheitsnetz, falls Stille-Erkennung versagt.
        """
        poll_interval = 0.1
        min_speech_seconds = 0.6
        silence_seconds = 1.5
        max_seconds = 30.0

        start = time.monotonic()
        speech_started = False
        silence_run = 0.0

        while self._recorder.is_recording:
            time.sleep(poll_interval)
            elapsed = time.monotonic() - start
            level = self._recorder.current_level
            if level >= self._config.silence_threshold:
                speech_started = True
                silence_run = 0.0
            elif speech_started:
                silence_run += poll_interval
                if silence_run >= silence_seconds:
                    break
            if elapsed >= max_seconds:
                logger.info("Wake-Word-Aufnahme: max_seconds erreicht")
                break

        if self._recorder.is_recording:
            self._on_record_stop()

    def _install_update(self, info: updater.UpdateInfo) -> None:
        """Tray-Callback: ZIP herunterladen, verifizieren, Helper-Batch starten,
        VOCIX beenden — Helper kopiert die neuen Dateien und startet neu."""
        try:
            updater.install_update(info)
        except Exception as e:
            logger.error("install_update fehlgeschlagen: %s", e, exc_info=True)
            self._overlay.show_temporary(t("overlay.error"), "error")
            raise
        # Helper läuft bereits und wartet auf Prozessende — sauber beenden.
        logger.info("Update-Helper gestartet, beende VOCIX zum Austausch")
        self._quit()
        # Sicherheitsnetz: non-daemon Threads (audio, keyboard hooks, pystray)
        # können _quit() überleben und den Prozess am Leben halten — der
        # Helper-Batch würde dann ewig auf das Prozess-Ende warten.
        threading.Timer(2.0, lambda: os._exit(0)).start()

    def _start_update_check(self) -> None:
        """Startet asynchronen Update-Check im Hintergrund. Silent bei Fehlern."""
        skip_version = load_state().get("skip_update_version")
        updater.check_async(
            current_version=__version__,
            skip_version=skip_version,
            on_update_found=self._tray.set_update_available,
        )

    def run(self) -> None:
        self._tray.start()
        self._register_hotkeys()
        self._start_update_check()
        if self._wakeword_enabled and wakeword.is_available():
            self._start_wakeword()

        logger.info("VOCIX läuft. Zum Beenden: Tray-Icon → Beenden")
        try:
            # Blockiert bis _quit() das Event setzt (aus Tray-Thread oder Ctrl+C).
            # keyboard.wait() blockiert auch nach unhook_all() weiter, daher
            # verwenden wir ein eigenes Event.
            while not self._quit_event.wait(timeout=0.5):
                pass
        except KeyboardInterrupt:
            self._quit()


def _notify_already_running() -> None:
    """Zweitinstanz: kurze Overlay-Meldung anzeigen und sauber beenden."""
    config = Config.load()
    i18n.set_language(config.language)
    overlay = StatusOverlay(config)
    overlay.show_temporary(t("overlay.already_running"), "error")
    # Overlay blendet sich nach overlay_display_seconds selbst aus — danach
    # noch kurz Luft für das Hide-Rendering, dann Tk sauber abbauen.
    time.sleep(config.overlay_display_seconds + 0.4)
    overlay.destroy()


def main():
    if not single_instance.acquire():
        _notify_already_running()
        return
    app = VocixApp()
    app.run()


if __name__ == "__main__":
    main()
