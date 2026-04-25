"""Modales Hilfe-Popup, geoeffnet ueber einen kleinen ?-Button neben einem Feld."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from vocix.i18n import t


def show_help(parent: tk.Misc, title: str, body: str) -> tk.Toplevel:
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent.winfo_toplevel())
    win.geometry("420x240")
    win.resizable(False, False)

    text = tk.Text(win, wrap="word", padx=12, pady=10, height=10, relief="flat")
    text.insert("1.0", body)
    text.configure(state="disabled")
    text.pack(fill="both", expand=True, padx=8, pady=(8, 4))

    ttk.Button(win, text=t("settings.button.ok"), command=win.destroy).pack(pady=(0, 8))
    win.grab_set()
    return win


class HelpButton(ttk.Button):
    def __init__(
        self,
        master: tk.Misc,
        *,
        title_provider: Callable[[], str],
        body_provider: Callable[[], str],
    ):
        super().__init__(master, text="?", width=2, command=self._open)
        self._title = title_provider
        self._body = body_provider

    def _open(self) -> None:
        show_help(self, self._title(), self._body())
