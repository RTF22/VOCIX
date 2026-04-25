import logging
import threading
import tkinter as tk
import webbrowser
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
        self._about_window: tk.Toplevel | None = None
        self._stats_window: tk.Toplevel | None = None
        self._settings_dialog = None
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

    # Heller als das Status-Overlay (#2c3e50) für bessere Lesbarkeit der Dialoge.
    _DIALOG_BG = "#3d566e"
    _DIALOG_FG = "#ffffff"
    _DIALOG_FG_MUTED = "#ecf0f1"
    _DIALOG_LINK = "#7fc4ff"

    def _make_dialog(self, title: str) -> "tk.Toplevel | None":
        """Erzeugt ein Toplevel mit einheitlichem Stil + Standard-Bindings.

        Muss aus der Tk-Mainloop heraus aufgerufen werden (also via _schedule).
        """
        if self._root is None:
            return None
        win = tk.Toplevel(self._root)
        win.title(title)
        win.attributes("-topmost", True)
        win.configure(bg=self._DIALOG_BG, padx=28, pady=22)
        win.resizable(False, False)
        win.bind("<Escape>", lambda _e: win.destroy())
        win.bind("<Return>", lambda _e: win.destroy())
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        return win

    def _center_and_focus(self, win: "tk.Toplevel") -> None:
        win.update_idletasks()
        w = win.winfo_width()
        h = win.winfo_height()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        win.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")
        win.focus_force()
        win.lift()

    def _focus_existing(self, attr: str) -> bool:
        """Hebt ein bereits offenes Singleton-Fenster nach vorne.

        Returns True, wenn ein gültiges Fenster gefunden und fokussiert wurde.
        """
        win = getattr(self, attr, None)
        if win is None:
            return False
        try:
            if not win.winfo_exists():
                setattr(self, attr, None)
                return False
        except tk.TclError:
            setattr(self, attr, None)
            return False
        win.deiconify()
        win.lift()
        win.focus_force()
        return True

    def show_about(
        self,
        title: str,
        version: str,
        tagline: str,
        description: str,
        url: str,
    ) -> None:
        """About-Dialog als Toplevel-Fenster mit anklickbarem URL-Label.

        Läuft in der Tk-Mainloop des Overlay-Threads — zuverlässiger als
        Win32-MessageBox/TaskDialog aus der pystray-Icon-Thread-Umgebung,
        wo die Dialoge auf manchen Setups nicht auf Klicks reagierten.
        """
        def _open():
            if self._focus_existing("_about_window"):
                return
            win = self._make_dialog(title)
            if win is None:
                return
            self._about_window = win
            def _on_close():
                self._about_window = None
                win.destroy()
            win.bind("<Escape>", lambda _e: _on_close())
            win.bind("<Return>", lambda _e: _on_close())
            win.protocol("WM_DELETE_WINDOW", _on_close)

            tk.Label(
                win, text=version, font=("Segoe UI", 14, "bold"),
                fg=self._DIALOG_FG, bg=self._DIALOG_BG,
            ).pack(anchor="w")
            tk.Label(
                win, text=tagline, font=("Segoe UI", 11, "italic"),
                fg=self._DIALOG_FG_MUTED, bg=self._DIALOG_BG,
            ).pack(anchor="w", pady=(0, 14))
            tk.Label(
                win, text=description, font=("Segoe UI", 11),
                fg=self._DIALOG_FG, bg=self._DIALOG_BG, justify="left",
            ).pack(anchor="w")

            link = tk.Label(
                win, text=url, font=("Segoe UI", 11, "underline"),
                fg=self._DIALOG_LINK, bg=self._DIALOG_BG, cursor="hand2",
            )
            link.pack(anchor="w", pady=(14, 16))
            link.bind("<Button-1>", lambda _e: webbrowser.open(url))

            tk.Button(
                win, text="OK", width=12, command=_on_close,
                font=("Segoe UI", 10),
            ).pack(anchor="e")

            self._center_and_focus(win)

        self._schedule(_open)

    def show_stats(self, title: str, body: str) -> None:
        """Statistik-Dialog im selben Stil wie show_about.

        Vorher lief das über native_dialog.show_info (Win32 MessageBoxW) aus
        dem pystray-Thread — dort ließ sich der Dialog auf manchen Setups
        nicht schließen. Tk-Toplevel im Overlay-Thread ist zuverlässig.
        """
        def _open():
            if self._focus_existing("_stats_window"):
                return
            win = self._make_dialog(title)
            if win is None:
                return
            self._stats_window = win
            def _on_close():
                self._stats_window = None
                win.destroy()
            win.bind("<Escape>", lambda _e: _on_close())
            win.bind("<Return>", lambda _e: _on_close())
            win.protocol("WM_DELETE_WINDOW", _on_close)

            tk.Label(
                win, text=title, font=("Segoe UI", 14, "bold"),
                fg=self._DIALOG_FG, bg=self._DIALOG_BG,
            ).pack(anchor="w", pady=(0, 12))
            tk.Label(
                win, text=body, font=("Segoe UI", 11),
                fg=self._DIALOG_FG, bg=self._DIALOG_BG, justify="left",
            ).pack(anchor="w", pady=(0, 16))

            tk.Button(
                win, text="OK", width=12, command=_on_close,
                font=("Segoe UI", 10),
            ).pack(anchor="e")

            self._center_and_focus(win)

        self._schedule(_open)

    def show_settings(self, config, on_apply) -> None:
        """Settings-Dialog im Overlay-Tk-Thread öffnen.

        Singleton-Verhalten analog show_about: ein bereits offenes Fenster
        wird nach vorne gehoben statt ein zweites zu öffnen.
        """
        def _open():
            existing = self._settings_dialog
            if existing is not None:
                try:
                    if existing._win.winfo_exists():
                        existing._win.lift()
                        existing._win.focus_force()
                        return
                except tk.TclError:
                    pass
                self._settings_dialog = None
            if self._root is None:
                return
            from vocix.ui.settings import SettingsDialog
            self._settings_dialog = SettingsDialog(
                self._root, config=config, on_apply=on_apply
            )

        self._schedule(_open)

    def destroy(self) -> None:
        def _quit():
            self._meter_active = False
            if self._root:
                self._root.quit()
                self._root.destroy()

        self._schedule(_quit)
