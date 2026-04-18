import logging
import threading
import tkinter as tk

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

    def __init__(self, config: Config):
        self._config = config
        self._root: tk.Tk | None = None
        self._label: tk.Label | None = None
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)

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

    def show(self, text: str, status: str = "processing") -> None:
        color = self._STATUS_COLORS.get(status, "#2c3e50")

        def _update():
            if self._label and self._root:
                self._label.configure(text=text, bg=color)
                self._root.configure(bg=color)
                self._root.deiconify()
                self._root.lift()

        self._schedule(_update)

    def hide(self) -> None:
        def _hide():
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
            if self._root:
                self._root.quit()
                self._root.destroy()

        self._schedule(_quit)
