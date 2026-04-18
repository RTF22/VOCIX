import logging
import os
import threading
import webbrowser
from typing import Callable

from PIL import Image, ImageDraw, ImageFont
from pystray import Icon, Menu, MenuItem

from dictum import __version__

logger = logging.getLogger(__name__)
_REPO_URL = "https://github.com/RTF22/DICTUM"

_MODE_COLORS = {
    "clean": (46, 204, 113),      # Grün
    "business": (52, 152, 219),   # Blau
    "rage": (231, 76, 60),        # Rot
}

_MODE_ACCENTS = {
    "clean": (39, 174, 96),       # Dunkler Grün
    "business": (41, 128, 185),   # Dunkler Blau
    "rage": (192, 57, 43),        # Dunkler Rot
}

_MODE_LABELS = {
    "clean": "A: Clean",
    "business": "B: Business",
    "rage": "C: Rage",
}


def _create_icon_image(color: tuple[int, int, int], mode: str = "clean") -> Image.Image:
    """Erstellt ein Mikrofon-Icon im abgerundeten Quadrat, farbcodiert nach Modus."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    accent = _MODE_ACCENTS.get(mode, (100, 100, 100))

    # --- Hintergrund: Abgerundetes Quadrat ---
    draw.rounded_rectangle([2, 2, 61, 61], radius=14, fill=(*color, 240))

    # --- Mikrofon-Körper (Rechteck mit runder Spitze) ---
    mic_left, mic_right = 24, 40
    mic_top, mic_bottom = 10, 34

    # Oberer Halbkreis des Mikrofons
    draw.ellipse(
        [mic_left, mic_top, mic_right, mic_top + (mic_right - mic_left)],
        fill=(255, 255, 255, 230),
    )
    # Rechteck-Körper
    draw.rectangle(
        [mic_left, mic_top + 8, mic_right, mic_bottom],
        fill=(255, 255, 255, 230),
    )
    # Unterer Abschluss (rund)
    draw.ellipse(
        [mic_left, mic_bottom - 8, mic_right, mic_bottom + 8],
        fill=(255, 255, 255, 230),
    )

    # --- Mikrofon-Gitter (3 horizontale Linien) ---
    for y in [16, 20, 24]:
        draw.line([(mic_left + 3, y), (mic_right - 3, y)], fill=(*accent, 180), width=1)

    # --- Bügel (Halbkreis um das Mikrofon) ---
    draw.arc(
        [18, 20, 46, 48],
        start=0, end=180,
        fill=(255, 255, 255, 200),
        width=3,
    )

    # --- Stiel (vertikal unter dem Bügel) ---
    draw.line([(32, 46), (32, 52)], fill=(255, 255, 255, 200), width=3)

    # --- Standfuß ---
    draw.line([(25, 52), (39, 52)], fill=(255, 255, 255, 200), width=3)

    return img


class TrayApp:
    """System Tray Icon mit Moduswechsel und Beenden."""

    def __init__(
        self,
        current_mode: str,
        on_mode_change: Callable[[str], None],
        on_quit: Callable[[], None],
    ):
        self._current_mode = current_mode
        self._on_mode_change = on_mode_change
        self._on_quit = on_quit
        self._icon: Icon | None = None
        self._thread: threading.Thread | None = None

    def _build_menu(self) -> Menu:
        def make_switch(mode: str):
            return lambda: self._switch_mode(mode)

        items = []
        for mode, label in _MODE_LABELS.items():
            checked = mode == self._current_mode
            items.append(
                MenuItem(
                    f"{'>> ' if checked else '   '}{label}",
                    make_switch(mode),
                )
            )
        items.append(Menu.SEPARATOR)
        items.append(MenuItem("Info", self._show_about))
        items.append(MenuItem("Beenden", self._quit))
        return Menu(*items)

    @staticmethod
    def _show_about() -> None:
        """Zeigt ein About-Fenster mit Versionsinformation und Repo-Link."""
        import tkinter as tk
        from tkinter import messagebox

        # Temporäres verstecktes Root-Fenster für den Dialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        result = messagebox.askquestion(
            "DICTUM — Info",
            f"DICTUM v{__version__}\n"
            f"DICtation with Text Understanding & Modification\n\n"
            f"Lokale Sprachdiktion fuer Windows\n"
            f"mit intelligentem Text-Processing.\n\n"
            f"Repository:\n{_REPO_URL}\n\n"
            f"Im Browser oeffnen?",
            icon="info",
        )
        if result == "yes":
            webbrowser.open(_REPO_URL)

        root.destroy()

    def _switch_mode(self, mode: str) -> None:
        self._current_mode = mode
        self._on_mode_change(mode)
        self._update_icon()
        logger.info("Modus gewechselt: %s", mode)

    def _update_icon(self) -> None:
        if self._icon is not None:
            color = _MODE_COLORS.get(self._current_mode, (128, 128, 128))
            self._icon.icon = _create_icon_image(color, self._current_mode)
            self._icon.menu = self._build_menu()
            self._icon.title = f"DICTUM — {_MODE_LABELS.get(self._current_mode, self._current_mode)}"

    def _quit(self) -> None:
        self._on_quit()
        if self._icon is not None:
            self._icon.stop()

    def start(self) -> None:
        color = _MODE_COLORS.get(self._current_mode, (128, 128, 128))
        self._icon = Icon(
            name="DICTUM",
            icon=_create_icon_image(color, self._current_mode),
            title=f"DICTUM — {_MODE_LABELS.get(self._current_mode, self._current_mode)}",
            menu=self._build_menu(),
        )
        # pystray.Icon.run() blockiert — in eigenem Thread starten
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()
        logger.info("Tray-Icon gestartet")

    def update_mode(self, mode: str) -> None:
        self._current_mode = mode
        self._update_icon()

    def stop(self) -> None:
        if self._icon is not None:
            self._icon.stop()
