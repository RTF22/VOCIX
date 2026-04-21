import logging
import threading
import tkinter as tk
from typing import Callable

from vocix.config import Config

logger = logging.getLogger(__name__)


class StatusOverlay:
    """Halbtransparentes Overlay-Fenster für Status-Feedback.

    Läuft in einem eigenen Thread mit eigener tkinter-Mainloop.
    Thread-safe über _schedule()-Mechanismus.
    """

    _STATUS_COLORS = {
        "recording": "#e74c3c",   # Rot
        "processing": "#f39c12",  # Orange
        "done": "#2ecc71",        # Grün
        "error": "#e74c3c",       # Rot
    }

    _METER_WIDTH = 220
    _METER_HEIGHT = 6
    _METER_POLL_MS = 50
    # Skaliert Roh-RMS so, dass normale Sprache den Balken weitgehend füllt.
    _METER_GAIN = 8.0

    def __init__(self, config: Config):
        self._config = config
        self._root: tk.Tk | None = None
        self._label: tk.Label | None = None
        self._meter_canvas: tk.Canvas | None = None
        self._meter_bar: int | None = None
        self._level_source: Callable[[], float] | None = None
        self._meter_active = False
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)

    def set_level_source(self, source: Callable[[], float]) -> None:
        """Quelle für den VU-Meter — wird gepollt, solange status='recording'."""
        self._level_source = source

    def _run(self) -> None:
        self._root = tk.Tk()
        self._root.title("VOCIX")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", 0.85)
        self._root.configure(bg="#2c3e50")

        self._label = tk.Label(
            self._root,
            text="",
            font=("Segoe UI", 12, "bold"),
            fg="white",
            bg="#2c3e50",
            padx=16,
            pady=8,
        )
        self._label.pack()

        self._meter_canvas = tk.Canvas(
            self._root,
            width=self._METER_WIDTH,
            height=self._METER_HEIGHT,
            bg="#1b2733",
            highlightthickness=0,
        )
        self._meter_bar = self._meter_canvas.create_rectangle(
            0, 0, 0, self._METER_HEIGHT, fill="#2ecc71", width=0
        )

        # Fenster rechts oben positionieren
        self._root.update_idletasks()
        screen_w = self._root.winfo_screenwidth()
        self._root.geometry(f"+{screen_w - 300}+40")

        # Initial versteckt
        self._root.withdraw()
        self._ready.set()
        self._root.mainloop()

    def _schedule(self, func) -> None:
        if self._root is not None:
            try:
                self._root.after(0, func)
            except tk.TclError:
                pass

    def show(self, text: str, status: str = "processing", badge: str | None = None) -> None:
        color = self._STATUS_COLORS.get(status, "#2c3e50")
        display = f"{text}   {badge}" if badge else text
        is_recording = status == "recording"

        def _update():
            if self._label and self._root:
                self._label.configure(text=display, bg=color)
                self._root.configure(bg=color)
                if is_recording and self._level_source is not None:
                    if self._meter_canvas is not None:
                        self._meter_canvas.configure(bg=color)
                        self._meter_canvas.pack(padx=12, pady=(0, 8))
                    if not self._meter_active:
                        self._meter_active = True
                        self._poll_level()
                else:
                    self._meter_active = False
                    if self._meter_canvas is not None:
                        self._meter_canvas.pack_forget()
                self._root.deiconify()
                self._root.lift()

        self._schedule(_update)

    def _poll_level(self) -> None:
        if not self._meter_active or self._root is None or self._meter_canvas is None:
            return
        if self._level_source is None or self._meter_bar is None:
            return
        try:
            level = self._level_source()
        except Exception:
            level = 0.0

        scaled = max(0.0, min(1.0, level * self._METER_GAIN))
        width = int(self._METER_WIDTH * scaled)
        # Unter Silence-Threshold: rot (kein Pegel erkannt). Sonst weiß.
        too_quiet = level < self._config.silence_threshold
        color = "#ffffff" if not too_quiet else "#ffb3b3"
        try:
            self._meter_canvas.coords(self._meter_bar, 0, 0, width, self._METER_HEIGHT)
            self._meter_canvas.itemconfigure(self._meter_bar, fill=color)
            self._root.after(self._METER_POLL_MS, self._poll_level)
        except tk.TclError:
            pass

    def hide(self) -> None:
        def _hide():
            self._meter_active = False
            if self._root:
                self._root.withdraw()

        self._schedule(_hide)

    def show_temporary(self, text: str, status: str = "done") -> None:
        """Zeigt eine Nachricht und versteckt sie nach der konfigurierten Zeit."""
        self.show(text, status)
        delay_ms = int(self._config.overlay_display_seconds * 1000)

        def _hide_later():
            if self._root:
                self._root.after(delay_ms, self.hide)

        self._schedule(_hide_later)

    def destroy(self) -> None:
        def _quit():
            self._meter_active = False
            if self._root:
                self._root.quit()
                self._root.destroy()

        self._schedule(_quit)
