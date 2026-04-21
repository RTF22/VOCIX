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
_REPO_URL = "https://github.com/RTF22/VOCIX"

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
        self._icon: Icon | None = None
        self._thread: threading.Thread | None = None
        self._update_info: updater.UpdateInfo | None = None

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
        from vocix.ui import native_dialog

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
        native_dialog.show_info(t("stats.title"), body)

    def set_update_available(self, info: "updater.UpdateInfo") -> None:
        self._update_info = info
        logger.info("Update verfügbar: %s (%s)", info.version, info.url)
        self._update_icon()
        self._notify(
            t("toast.update_title"),
            t("toast.update_body", version=info.version),
        )

    def _on_open_release(self) -> None:
        if self._update_info is not None and self._update_info.url:
            webbrowser.open(self._update_info.url)

    def _install_update_clicked(self) -> None:
        if self._update_info is None or self._on_install_update is None:
            return
        info = self._update_info
        self._notify("VOCIX", t("toast.update_downloading", version=info.version))
        cb = self._on_install_update

        def _run():
            try:
                cb(info)
            except Exception as e:
                logger.error("Update-Install fehlgeschlagen: %s", e, exc_info=True)
                self._notify("VOCIX", t("toast.update_failed"))

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
            self._notify("VOCIX", t("toast.checking"))
            info = updater.check_latest(__version__, skip_version=None)
            if info is None:
                self._notify("VOCIX", t("toast.up_to_date"))
            else:
                self.set_update_available(info)

        threading.Thread(target=_run, name="ManualUpdateCheck", daemon=True).start()

    def _notify(self, title: str, message: str) -> None:
        if self._icon is None:
            return
        try:
            self._icon.notify(message, title=title)
        except Exception as e:
            logger.warning("Toast-Benachrichtigung fehlgeschlagen: %s", e)

    @staticmethod
    def _show_about() -> None:
        """About-Dialog mit Versionsinfo und Repo-Link.

        Nutzt native Win32-MessageBox (via `native_dialog`) statt tkinter —
        vermeidet einen zweiten Tk-Root neben dem StatusOverlay (siehe #13).
        """
        from vocix.ui import native_dialog

        body = (
            f"VOCIX v{__version__}\n"
            f"{t('about.tagline')}\n\n"
            f"{t('about.description')}\n\n"
            f"{t('about.repository')}\n{_REPO_URL}\n\n"
            f"{t('about.open_browser')}"
        )
        if native_dialog.show_info_with_link(t("about.title"), body):
            webbrowser.open(_REPO_URL)

    def _toggle_translate(self) -> None:
        self._translate_to_english = not self._translate_to_english
        if self._on_translate_toggle is not None:
            self._on_translate_toggle(self._translate_to_english)
        self._update_icon()
        toast_key = "toast.translate_on" if self._translate_to_english else "toast.translate_off"
        self._notify("VOCIX", t(toast_key))
        logger.info("Translate-to-English: %s", self._translate_to_english)

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

    def update_mode(self, mode: str) -> None:
        self._current_mode = mode
        self._update_icon()

    def update_language(self, code: str) -> None:
        self._current_language = code
        self._update_icon()

    def stop(self) -> None:
        if self._icon is not None:
            self._icon.stop()
