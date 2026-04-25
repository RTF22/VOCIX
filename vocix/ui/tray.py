import logging
import os
import threading
import webbrowser
from typing import Callable

from PIL import Image, ImageDraw, ImageFont
from pystray import Icon, Menu, MenuItem

from vocix import __version__
from vocix import config as config_module
from vocix import updater
from vocix.history import History
from vocix.i18n import available_languages, get_language, t
from vocix.snippets import SnippetExpander
from vocix.stats import Stats

logger = logging.getLogger(__name__)
_MODE_COLORS = {
    "clean": (46, 204, 113),      # Grün
    "business": (52, 152, 219),   # Blau
    "rage": (231, 76, 60),        # Rot
}

_MODE_ACCENTS = {
    "clean": (39, 174, 96),
    "business": (41, 128, 185),
    "rage": (192, 57, 43),
}

_MODE_KEYS = ("clean", "business", "rage")

# Whitelist für das Tray-Untermenü. faster-whisper akzeptiert mehr (HF-Repos),
# aber im Menü beschränken wir uns auf die gängigen Größen.
_WHISPER_MODELS = ("tiny", "base", "small", "medium", "large-v3", "large-v3-turbo")
_WHISPER_ACCELERATIONS = ("auto", "gpu", "cpu")


def _mode_label(mode: str) -> str:
    return t(f"mode.{mode}")


def _create_icon_image(color: tuple[int, int, int], mode: str = "clean") -> Image.Image:
    """Erstellt ein Mikrofon-Icon im abgerundeten Quadrat, farbcodiert nach Modus."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    accent = _MODE_ACCENTS.get(mode, (100, 100, 100))

    draw.rounded_rectangle([2, 2, 61, 61], radius=14, fill=(*color, 240))

    mic_left, mic_right = 24, 40
    mic_top, mic_bottom = 10, 34

    draw.ellipse(
        [mic_left, mic_top, mic_right, mic_top + (mic_right - mic_left)],
        fill=(255, 255, 255, 230),
    )
    draw.rectangle(
        [mic_left, mic_top + 8, mic_right, mic_bottom],
        fill=(255, 255, 255, 230),
    )
    draw.ellipse(
        [mic_left, mic_bottom - 8, mic_right, mic_bottom + 8],
        fill=(255, 255, 255, 230),
    )

    for y in [16, 20, 24]:
        draw.line([(mic_left + 3, y), (mic_right - 3, y)], fill=(*accent, 180), width=1)

    draw.arc(
        [18, 20, 46, 48],
        start=0, end=180,
        fill=(255, 255, 255, 200),
        width=3,
    )

    draw.line([(32, 46), (32, 52)], fill=(255, 255, 255, 200), width=3)
    draw.line([(25, 52), (39, 52)], fill=(255, 255, 255, 200), width=3)

    return img


class TrayApp:
    """System Tray Icon mit Moduswechsel, Sprachwahl und Beenden."""

    def __init__(
        self,
        current_mode: str,
        on_mode_change: Callable[[str], None],
        on_quit: Callable[[], None],
        on_language_change: Callable[[str], None] | None = None,
        current_language: str | None = None,
        on_translate_toggle: Callable[[bool], None] | None = None,
        translate_to_english: bool = False,
        history: History | None = None,
        stats: Stats | None = None,
        snippets: SnippetExpander | None = None,
        on_history_reinject: Callable[[str], None] | None = None,
        on_install_update: Callable[["updater.UpdateInfo"], None] | None = None,
        wakeword_available: bool = False,
        wakeword_enabled: bool = False,
        on_wakeword_toggle: Callable[[bool], None] | None = None,
        on_show_about: Callable[[], None] | None = None,
        on_show_stats: Callable[[str, str], None] | None = None,
        on_overlay_message: Callable[[str, str], None] | None = None,
        current_whisper_model: str = "small",
        on_whisper_model_change: Callable[[str], None] | None = None,
        current_whisper_acceleration: str = "auto",
        on_whisper_acceleration_change: Callable[[str], None] | None = None,
        cuda_available: bool = False,
    ):
        self._current_mode = current_mode
        self._current_language = current_language or get_language()
        self._on_mode_change = on_mode_change
        self._on_quit = on_quit
        self._on_language_change = on_language_change
        self._on_translate_toggle = on_translate_toggle
        self._translate_to_english = translate_to_english
        self._history = history
        self._stats = stats
        self._snippets = snippets
        self._on_history_reinject = on_history_reinject
        self._on_install_update = on_install_update
        self._wakeword_available = wakeword_available
        self._wakeword_enabled = wakeword_enabled
        self._on_wakeword_toggle = on_wakeword_toggle
        self._on_show_about = on_show_about
        self._on_show_stats = on_show_stats
        self._on_overlay_message = on_overlay_message
        self._whisper_model = current_whisper_model
        self._whisper_acceleration = current_whisper_acceleration
        self._on_whisper_model_change = on_whisper_model_change
        self._on_whisper_acceleration_change = on_whisper_acceleration_change
        self._cuda_available = cuda_available
        self._icon: Icon | None = None
        self._thread: threading.Thread | None = None
        self._update_info: updater.UpdateInfo | None = None
        # Schützt Tray-State (Whisper-Modell/Beschleunigung) gegen
        # Lese-/Schreib-Race zwischen Worker-Thread (update_whisper_settings)
        # und pystray-Thread (_build_menu). Python-Assignments sind atomar,
        # aber zwei abhängige Felder (Modell + Beschleunigung) sollen konsistent
        # gelesen werden.
        self._state_lock = threading.Lock()

    def _build_menu(self) -> Menu:
        def make_switch(mode: str):
            return lambda: self._switch_mode(mode)

        def make_lang_switch(code: str):
            return lambda: self._switch_language(code)

        items = []
        for mode in _MODE_KEYS:
            checked = mode == self._current_mode
            items.append(
                MenuItem(
                    f"{'>> ' if checked else '   '}{_mode_label(mode)}",
                    make_switch(mode),
                )
            )
        items.append(Menu.SEPARATOR)

        # Sprach-Untermenü
        lang_items = []
        for code, name in available_languages().items():
            checked = code == self._current_language
            lang_items.append(
                MenuItem(
                    f"{'>> ' if checked else '   '}{name}",
                    make_lang_switch(code),
                )
            )
        items.append(MenuItem(t("tray.language"), Menu(*lang_items)))
        items.append(MenuItem(
            t("tray.translate_to_english"),
            self._toggle_translate,
            checked=lambda item: self._translate_to_english,
        ))
        if self._wakeword_available:
            items.append(MenuItem(
                t("tray.wakeword"),
                self._toggle_wakeword,
                checked=lambda item: self._wakeword_enabled,
            ))

        # Whisper-Modell-Untermenü
        def make_model_switch(name: str):
            return lambda: self._switch_whisper_model(name)

        def make_model_check(name: str):
            return lambda item: name == self._whisper_model

        model_items = []
        for name in _WHISPER_MODELS:
            model_items.append(MenuItem(
                name,
                make_model_switch(name),
                checked=make_model_check(name),
                radio=True,
            ))
        items.append(MenuItem(t("tray.whisper_model"), Menu(*model_items)))

        # Beschleunigungs-Untermenü
        def make_accel_switch(value: str):
            return lambda: self._switch_whisper_acceleration(value)

        def make_accel_check(value: str):
            return lambda item: value == self._whisper_acceleration

        accel_items = []
        for value in _WHISPER_ACCELERATIONS:
            label_key = f"tray.acceleration.{value}"
            label = t(label_key)
            gpu_disabled = value == "gpu" and not self._cuda_available
            if gpu_disabled:
                label = f"{label} {t('tray.acceleration.gpu_unavailable_suffix')}"
            accel_items.append(MenuItem(
                label,
                make_accel_switch(value),
                enabled=not gpu_disabled,
                checked=make_accel_check(value),
                radio=True,
            ))
        items.append(MenuItem(t("tray.whisper_acceleration"), Menu(*accel_items)))

        items.append(Menu.SEPARATOR)

        if self._history is not None:
            items.append(MenuItem(t("tray.history"), self._build_history_menu()))
        if self._stats is not None:
            items.append(MenuItem(t("tray.stats"), self._show_stats))
        if self._snippets is not None:
            items.append(MenuItem(t("tray.snippets_edit"), self._edit_snippets))
        if self._history is not None or self._stats is not None or self._snippets is not None:
            items.append(Menu.SEPARATOR)

        if self._update_info is not None:
            items.append(MenuItem(
                t("tray.update_available", version=self._update_info.version),
                self._on_open_release,
            ))
            if updater.is_frozen_bundle() and self._update_info.asset_url:
                items.append(MenuItem(
                    t("tray.update_install", version=self._update_info.version),
                    self._install_update_clicked,
                ))
            items.append(MenuItem(
                t("tray.skip_version"),
                self._on_skip_version,
            ))
            items.append(Menu.SEPARATOR)
        items.append(MenuItem(t("tray.check_updates"), self._on_manual_check))
        items.append(MenuItem(t("tray.info"), self._show_about))
        items.append(MenuItem(t("tray.quit"), self._quit))
        return Menu(*items)

    def _build_history_menu(self) -> Menu:
        if self._history is None:
            return Menu(MenuItem(t("tray.history_empty"), None, enabled=False))

        entries = self._history.entries()
        if not entries:
            return Menu(MenuItem(t("tray.history_empty"), None, enabled=False))

        def make_reinject(text: str):
            return lambda: self._reinject(text)

        items = []
        for entry in entries:
            text = entry.get("text", "")
            preview = text.replace("\n", " ").replace("\r", " ").strip()
            if len(preview) > 50:
                preview = preview[:47] + "..."
            mode = entry.get("mode", "")
            label = f"[{mode[:1].upper()}] {preview}" if mode else preview
            items.append(MenuItem(label, make_reinject(text)))
        items.append(Menu.SEPARATOR)
        items.append(MenuItem(t("tray.history_clear"), self._clear_history))
        return Menu(*items)

    def _reinject(self, text: str) -> None:
        if self._on_history_reinject is not None:
            self._on_history_reinject(text)

    def _clear_history(self) -> None:
        if self._history is not None:
            self._history.clear()
            self._update_icon()

    def refresh_history(self) -> None:
        """Wird nach jedem neuen History-Eintrag aufgerufen, damit das Submenü
        beim nächsten Öffnen die neuen Einträge zeigt."""
        self._update_icon()

    def _edit_snippets(self) -> None:
        if self._snippets is None:
            return
        path = self._snippets.file_path
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except (AttributeError, OSError) as e:
            logger.warning("Snippets-Datei konnte nicht geöffnet werden: %s", e)

    def _show_stats(self) -> None:
        if self._stats is None:
            return

        today = self._stats.today()
        week = self._stats.week()
        total = self._stats.total()

        def fmt(stats: dict) -> str:
            mins = Stats.estimated_minutes_saved(stats["chars"])
            modes = ", ".join(f"{m}:{c}" for m, c in sorted(stats["modes"].items())) or "-"
            return t(
                "stats.block",
                dictations=stats["dictations"],
                words=stats["words"],
                minutes=int(mins),
                modes=modes,
            )

        body = (
            f"{t('stats.today')}\n{fmt(today)}\n\n"
            f"{t('stats.week')}\n{fmt(week)}\n\n"
            f"{t('stats.total')}\n{fmt(total)}\n\n"
            f"{t('stats.assumption')}"
        )
        if self._on_show_stats is not None:
            self._on_show_stats(t("stats.title"), body)
        else:
            from vocix.ui import native_dialog
            native_dialog.show_info(t("stats.title"), body)

    def set_update_available(self, info: "updater.UpdateInfo") -> None:
        self._update_info = info
        logger.info("Update verfügbar: %s (%s)", info.version, info.url)
        self._update_icon()
        self._notify(t("toast.update_body", version=info.version), "done")

    def _on_open_release(self) -> None:
        if self._update_info is not None and self._update_info.url:
            webbrowser.open(self._update_info.url)

    def _install_update_clicked(self) -> None:
        if self._update_info is None or self._on_install_update is None:
            return
        info = self._update_info
        self._notify(t("toast.update_downloading", version=info.version), "processing")
        cb = self._on_install_update

        def _run():
            try:
                cb(info)
            except Exception as e:
                logger.error("Update-Install fehlgeschlagen: %s", e, exc_info=True)
                self._notify(t("toast.update_failed"), "error")

        threading.Thread(target=_run, name="UpdateInstaller", daemon=True).start()

    def _on_skip_version(self) -> None:
        if self._update_info is None:
            return
        with config_module.update_state() as state:
            state["skip_update_version"] = self._update_info.version
        logger.info("Update %s wird übersprungen", self._update_info.version)
        self._update_info = None
        self._update_icon()

    def _on_manual_check(self) -> None:
        def _run():
            logger.info("Manueller Update-Check angestoßen")
            self._notify(t("toast.checking"), "processing")
            info = updater.check_latest(__version__, skip_version=None)
            if info is None:
                logger.info("Update-Check: bereits aktuell")
                self._notify(t("toast.up_to_date"), "done")
            else:
                self.set_update_available(info)

        threading.Thread(target=_run, name="ManualUpdateCheck", daemon=True).start()

    def _notify(self, message: str, status: str = "done") -> None:
        """Zeigt eine kurze Statusmeldung — bevorzugt im Overlay, sonst
        Fallback auf Tray-Toast (z.B. wenn kein Overlay-Callback gesetzt
        wurde). Status steuert die Hintergrundfarbe im Overlay."""
        if self._on_overlay_message is not None:
            try:
                self._on_overlay_message(message, status)
                return
            except Exception as e:
                logger.warning("Overlay-Nachricht fehlgeschlagen: %s", e)
        if self._icon is None:
            return
        try:
            self._icon.notify(message, title="VOCIX")
        except Exception as e:
            logger.warning("Toast-Benachrichtigung fehlgeschlagen: %s", e)

    def _show_about(self) -> None:
        """Delegiert an den App-Callback, der den Dialog im Overlay-Tk-Thread
        rendert. Der vorherige Win32-Weg (MessageBox / TaskDialogIndirect)
        reagierte aus der pystray-Thread-Umgebung auf manchen Setups nicht
        zuverlässig auf Klicks.
        """
        if self._on_show_about is not None:
            self._on_show_about()

    def _toggle_translate(self) -> None:
        self._translate_to_english = not self._translate_to_english
        if self._on_translate_toggle is not None:
            self._on_translate_toggle(self._translate_to_english)
        self._update_icon()
        toast_key = "toast.translate_on" if self._translate_to_english else "toast.translate_off"
        self._notify(t(toast_key), "done")
        logger.info("Translate-to-English: %s", self._translate_to_english)

    def _toggle_wakeword(self) -> None:
        self._wakeword_enabled = not self._wakeword_enabled
        if self._on_wakeword_toggle is not None:
            self._on_wakeword_toggle(self._wakeword_enabled)
        self._update_icon()
        toast_key = "toast.wakeword_on" if self._wakeword_enabled else "toast.wakeword_off"
        self._notify(t(toast_key), "done")
        logger.info("Wake-Word: %s", self._wakeword_enabled)

    def update_wakeword(self, enabled: bool) -> None:
        self._wakeword_enabled = enabled
        self._update_icon()

    def update_translate(self, enabled: bool) -> None:
        self._translate_to_english = enabled
        self._update_icon()

    def _switch_mode(self, mode: str) -> None:
        self._current_mode = mode
        self._on_mode_change(mode)
        self._update_icon()
        logger.info("Modus gewechselt: %s", mode)

    def _switch_language(self, code: str) -> None:
        if code == self._current_language:
            return
        if self._on_language_change is not None:
            self._on_language_change(code)
        # update_language wird typischerweise von der App callback-gesteuert aufgerufen,
        # aber wir aktualisieren hier defensiv für den Fall, dass der Callback
        # synchron zurückkehrt, ohne update_language zu rufen.
        self._current_language = code
        self._update_icon()

    def _update_icon(self) -> None:
        if self._icon is not None:
            color = _MODE_COLORS.get(self._current_mode, (128, 128, 128))
            self._icon.icon = _create_icon_image(color, self._current_mode)
            self._icon.menu = self._build_menu()
            self._icon.title = t("tray.title", mode=_mode_label(self._current_mode))

    def _quit(self) -> None:
        self._on_quit()
        if self._icon is not None:
            self._icon.stop()

    def start(self) -> None:
        color = _MODE_COLORS.get(self._current_mode, (128, 128, 128))
        self._icon = Icon(
            name="VOCIX",
            icon=_create_icon_image(color, self._current_mode),
            title=t("tray.title", mode=_mode_label(self._current_mode)),
            menu=self._build_menu(),
        )
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()
        logger.info("Tray-Icon gestartet")

    def refresh(self) -> None:
        """Tray-Icon und Menü neu aufbauen — z.B. nach apply_settings, wenn
        sich Sprache, Modus, Whisper-Settings o.ä. geändert haben."""
        self._update_icon()

    def update_mode(self, mode: str) -> None:
        self._current_mode = mode
        self._update_icon()

    def update_language(self, code: str) -> None:
        self._current_language = code
        self._update_icon()

    def update_whisper_settings(self, model: str | None = None,
                                 acceleration: str | None = None) -> None:
        with self._state_lock:
            if model is not None:
                self._whisper_model = model
            if acceleration is not None:
                self._whisper_acceleration = acceleration
        self._update_icon()

    def _switch_whisper_model(self, name: str) -> None:
        if name == self._whisper_model:
            return
        if self._on_whisper_model_change is not None:
            self._on_whisper_model_change(name)

    def _switch_whisper_acceleration(self, value: str) -> None:
        if value == self._whisper_acceleration:
            return
        if value == "gpu" and not self._cuda_available:
            logger.warning("GPU-Auswahl ignoriert — kein CUDA verfügbar")
            return
        if self._on_whisper_acceleration_change is not None:
            self._on_whisper_acceleration_change(value)

    def stop(self) -> None:
        if self._icon is not None:
            self._icon.stop()
