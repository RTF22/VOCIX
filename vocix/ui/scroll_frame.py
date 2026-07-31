"""Scrollbarer Container fuer Dialog-Inhalte.

Wird vom Einstellungsdialog als Notebook-Seite benutzt: Der eigentliche
Inhalt kommt in `.inner`, die vertikale Scrollbar erscheint nur, wenn der
Inhalt hoeher ist als der verfuegbare Platz. Auf grossen Bildschirmen ist
sie damit unsichtbar, auf kleinen wird alles erreichbar.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ScrollableFrame(ttk.Frame):
    """Canvas-basierter Scroll-Container mit Scrollbar nur bei Bedarf.

    Der Canvas meldet die Wunschgroesse des Inhalts als eigene requested
    size weiter — so kann der Dialog seine Fenstergroesse weiterhin aus
    `winfo_reqheight()` ableiten und wird nur dann gescrollt, wenn das
    Fenster (z. B. wegen Bildschirmhoehe) kleiner ausfaellt.
    """

    def __init__(self, parent: tk.Misc, **inner_kwargs):
        super().__init__(parent)

        self._canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, takefocus=0)
        self._vbar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._vbar.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._bar_visible = False

        self.inner = ttk.Frame(self._canvas, **inner_kwargs)
        self._window = self._canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        # Mausrad global nur greifen, solange der Zeiger ueber diesem
        # Container steht — sonst scrollen alle Instanzen gleichzeitig.
        self._canvas.bind("<Enter>", self._bind_wheel)
        self._canvas.bind("<Leave>", self._unbind_wheel)
        # Sonst bliebe das globale Binding auf einem zerstoerten Canvas
        # haengen, wenn der Dialog schliesst waehrend der Zeiger drueber steht.
        self.bind("<Destroy>", self._on_destroy)

    # -- Layout ---------------------------------------------------------

    def _on_inner_configure(self, _event=None) -> None:
        req_w = self.inner.winfo_reqwidth()
        req_h = self.inner.winfo_reqheight()
        self._canvas.configure(scrollregion=(0, 0, req_w, req_h))
        # Wunschgroesse durchreichen (nur bei Aenderung — sonst Endlosschleife
        # aus Configure-Events).
        if self._canvas.winfo_reqwidth() != req_w or self._canvas.winfo_reqheight() != req_h:
            self._canvas.configure(width=req_w, height=req_h)
        self._sync_scrollbar()

    def _on_canvas_configure(self, event) -> None:
        # Inhalt auf Canvas-Breite aufziehen, aber nie unter seine
        # Wunschbreite quetschen (sonst wuerde horizontal abgeschnitten).
        width = max(event.width, self.inner.winfo_reqwidth())
        if self._canvas.itemcget(self._window, "width") != str(width):
            self._canvas.itemconfigure(self._window, width=width)
        self._sync_scrollbar()

    def _sync_scrollbar(self) -> None:
        """Scrollbar ein-/ausblenden, je nachdem ob der Inhalt passt."""
        height = self._canvas.winfo_height()
        if height <= 1:
            # Noch nicht gemappt (z. B. Notebook-Seite im Hintergrund) — die
            # echte Hoehe kommt mit dem ersten <Configure> beim Anzeigen.
            return
        needed = self.inner.winfo_reqheight() > height
        if needed and not self._bar_visible:
            self._vbar.pack(side="right", fill="y")
            self._bar_visible = True
        elif not needed and self._bar_visible:
            self._vbar.pack_forget()
            self._bar_visible = False
            self._canvas.yview_moveto(0.0)

    # -- Mausrad --------------------------------------------------------

    def _bind_wheel(self, _event=None) -> None:
        self._canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self, _event=None) -> None:
        try:
            self._canvas.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass

    def _on_wheel(self, event) -> None:
        if not self._bar_visible:
            return
        try:
            self._canvas.yview_scroll(int(-event.delta / 120), "units")
        except tk.TclError:
            pass

    def _on_destroy(self, event) -> None:
        if event.widget is self:
            self._unbind_wheel()
