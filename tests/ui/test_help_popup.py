import tkinter as tk

import pytest

from vocix.ui.help_popup import HelpButton, show_help


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("Kein Display verfuegbar")
    r.withdraw()
    yield r
    r.destroy()


def test_help_button_creates_question_mark(root):
    btn = HelpButton(root, title_provider=lambda: "T", body_provider=lambda: "B")
    btn.pack()
    assert btn.cget("text") == "?"


def test_show_help_opens_toplevel_with_text(root):
    win = show_help(root, title="Titel", body="Body-Text")
    assert win.winfo_exists()
    assert win.title() == "Titel"
    win.destroy()
