"""Zentraler Einstellungsdialog fuer VOCIX.

Drei Tabs (Basics/Erweitert/Expert) mit allen Config-Feldern. Schreibt
nach state.json ueber VocixApp.apply_settings, das die Reload-Schritte
(Whisper, Hotkeys, i18n, Tray) orchestriert.
"""

from __future__ import annotations

import logging
import tkinter as tk
from dataclasses import replace
from tkinter import ttk
from typing import Callable

from vocix.config import Config
from vocix import i18n
from vocix.i18n import t

logger = logging.getLogger(__name__)


def _ping_anthropic(api_key: str, model: str, timeout: float) -> tuple[bool, str]:
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key, timeout=timeout)
        client.messages.create(
            model=model, max_tokens=1,
            messages=[{"role": "user", "content": "ok"}],
        )
        return True, ""
    except Exception as e:
        logger.info("Anthropic ping failed: %s", e)
        return False, str(e)


def _ping_openai(api_key: str, base_url: str, model: str, timeout: float) -> tuple[bool, str]:
    try:
        from vocix.processing.providers import ProviderConfig
        from vocix.processing.providers.openai_provider import OpenAICompatibleProvider
        cfg = ProviderConfig(kind="openai", api_key=api_key, base_url=base_url,
                             model=model or "gpt-4o-mini", timeout=timeout)
        p = OpenAICompatibleProvider(cfg)
        p.complete(system="ping", user="ok", max_tokens=1)
        return True, ""
    except Exception as e:
        return False, str(e)


def _ping_ollama(base_url: str, model: str, timeout: float) -> tuple[bool, str]:
    try:
        from vocix.processing.providers import ProviderConfig
        from vocix.processing.providers.ollama_provider import OllamaProvider
        cfg = ProviderConfig(kind="ollama", base_url=base_url, model=model, timeout=timeout)
        p = OllamaProvider(cfg)
        p.complete(system="ping", user="ok", max_tokens=1)
        return True, ""
    except Exception as e:
        return False, str(e)


class SettingsDialog:
    def __init__(
        self,
        parent: tk.Misc,
        *,
        config: Config,
        on_apply: Callable[[Config], None],
    ):
        self._original = config
        self._draft = replace(config)
        self._on_apply_cb = on_apply

        self._win = tk.Toplevel(parent)
        self._win.title(t("settings.title"))
        self._win.geometry("640x540")
        # transient() nur, wenn der Parent ein sichtbares Toplevel ist —
        # sonst (Overlay-Root mit overrideredirect+withdraw) bleibt das
        # Toplevel ungemappt/unsichtbar.
        try:
            top = parent.winfo_toplevel()
            if top.winfo_viewable():
                self._win.transient(top)
        except tk.TclError:
            pass
        self._win.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self.notebook = ttk.Notebook(self._win)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        self._tab_basics = ttk.Frame(self.notebook, padding=12)
        self._tab_llm = ttk.Frame(self.notebook, padding=12)
        self._tab_advanced = ttk.Frame(self.notebook, padding=12)
        self._tab_expert = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self._tab_basics, text=t("settings.tab.basics"))
        self.notebook.add(self._tab_llm, text=t("settings.tab.llm"))
        self.notebook.add(self._tab_advanced, text=t("settings.tab.advanced"))
        self.notebook.add(self._tab_expert, text=t("settings.tab.expert"))

        self._build_basics(self._tab_basics)
        self._build_llm(self._tab_llm)
        self._build_advanced(self._tab_advanced)
        self._build_expert(self._tab_expert)

        self._error_var = tk.StringVar()
        ttk.Label(self._win, textvariable=self._error_var, foreground="#c0392b").pack(
            anchor="w", padx=12
        )

        btn_bar = ttk.Frame(self._win)
        btn_bar.pack(fill="x", padx=10, pady=10)
        self._ok_btn = ttk.Button(btn_bar, text=t("settings.button.ok"), command=self._on_ok)
        self._ok_btn.pack(side="right", padx=4)
        ttk.Button(btn_bar, text=t("settings.button.cancel"), command=self._on_cancel).pack(side="right", padx=4)
        self._apply_btn = ttk.Button(btn_bar, text=t("settings.button.apply"), command=self._on_apply)
        self._apply_btn.pack(side="right", padx=4)

        # Sichtbarkeit + Fokus erzwingen (Parent kann ein versteckter
        # overrideredirect-Root sein); grab_set() erst NACH dem Mappen,
        # sonst läuft ein Geist-Grab auf einem unsichtbaren Fenster.
        self._win.update_idletasks()
        self._win.deiconify()
        self._win.lift()
        self._win.attributes("-topmost", True)
        self._win.after(100, lambda: self._win.attributes("-topmost", False))
        self._win.focus_force()
        try:
            self._win.grab_set()
        except tk.TclError:
            pass

        # If the user switches the UI language via the tray while this dialog
        # is open, we don't rebuild every label live — we just disable the
        # save buttons and surface a notice telling them to reopen the dialog.
        i18n.register_language_listener(self._on_external_language_change)

    def _build_basics(self, frame: ttk.Frame) -> None:
        from vocix.ui.tooltip import Tooltip
        from vocix.ui.help_popup import HelpButton
        from vocix.stt.whisper_stt import cuda_available

        for col, weight in ((0, 0), (1, 1), (2, 0), (3, 0)):
            frame.columnconfigure(col, weight=weight)

        row = 0

        # Eingabesprache
        lbl = ttk.Label(frame, text=t("settings.field.input_language"))
        lbl.grid(row=row, column=0, sticky="w", pady=4)
        self._var_input_lang = tk.StringVar(value=self._draft.language)
        sub = ttk.Frame(frame)
        sub.grid(row=row, column=1, sticky="w")
        ttk.Radiobutton(sub, text=t("settings.lang.de"), value="de",
                        variable=self._var_input_lang,
                        command=self._on_input_lang_changed).pack(side="left")
        ttk.Radiobutton(sub, text=t("settings.lang.en"), value="en",
                        variable=self._var_input_lang,
                        command=self._on_input_lang_changed).pack(side="left", padx=(8, 0))
        self._other_lang_combo = ttk.Combobox(
            sub, state="readonly", width=10,
            values=("fr", "es", "it", "nl", "pl", "pt", "tr", "ru", "ja", "zh"),
        )
        self._other_lang_combo.pack(side="left", padx=(8, 0))
        self._other_lang_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_other_lang_picked())
        Tooltip(lbl, lambda: t("settings.tooltip.input_language"))
        row += 1

        # Ausgabesprache
        ttk.Label(frame, text=t("settings.field.output_language")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_output_lang = tk.StringVar(
            value="english" if self._draft.translate_to_english else "input"
        )
        out_combo = ttk.Combobox(frame, state="readonly", width=24, textvariable=self._var_output_lang,
                                 values=("input", "english"))
        out_combo.grid(row=row, column=1, sticky="w")
        out_combo.bind("<<ComboboxSelected>>",
                       lambda _e: setattr(self._draft, "translate_to_english",
                                          self._var_output_lang.get() == "english"))
        Tooltip(out_combo, lambda: t("settings.tooltip.output_language"))
        row += 1

        # Whisper-Modell
        ttk.Label(frame, text=t("settings.field.whisper_model")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_whisper_model = tk.StringVar(value=self._draft.whisper_model)
        wm = ttk.Combobox(frame, state="readonly", width=24, textvariable=self._var_whisper_model,
                          values=("tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"))
        wm.grid(row=row, column=1, sticky="w")
        wm.bind("<<ComboboxSelected>>",
                lambda _e: setattr(self._draft, "whisper_model", self._var_whisper_model.get()))
        Tooltip(wm, lambda: t("settings.tooltip.whisper_model"))
        HelpButton(frame,
                   title_provider=lambda: t("settings.help.whisper_model.title"),
                   body_provider=lambda: t("settings.help.whisper_model.body")
                   ).grid(row=row, column=2, padx=4)
        row += 1

        # Beschleunigung
        ttk.Label(frame, text=t("settings.field.acceleration")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_acceleration = tk.StringVar(value=self._draft.whisper_acceleration)
        accel_frame = ttk.Frame(frame)
        accel_frame.grid(row=row, column=1, sticky="w")
        gpu_ok = cuda_available()
        for value, label in (("auto", "Auto"), ("gpu", "GPU"), ("cpu", "CPU")):
            rb = ttk.Radiobutton(accel_frame, text=label, value=value,
                                 variable=self._var_acceleration,
                                 command=lambda: setattr(self._draft,
                                                         "whisper_acceleration",
                                                         self._var_acceleration.get()))
            rb.pack(side="left", padx=4)
            if value == "gpu" and not gpu_ok:
                rb.state(["disabled"])
        Tooltip(accel_frame, lambda: t("settings.tooltip.acceleration"))
        HelpButton(frame,
                   title_provider=lambda: t("settings.help.acceleration.title"),
                   body_provider=lambda: t("settings.help.acceleration.body")
                   ).grid(row=row, column=2, padx=4)
        row += 1

        # Default Mode
        ttk.Label(frame, text=t("settings.field.default_mode")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_default_mode = tk.StringVar(value=self._draft.default_mode)
        self._mode_combo = ttk.Combobox(frame, state="readonly", width=24, textvariable=self._var_default_mode)
        self._update_mode_combo_values()
        self._mode_combo.grid(row=row, column=1, sticky="w")
        self._mode_combo.bind("<<ComboboxSelected>>",
                              lambda _e: setattr(self._draft, "default_mode", self._var_default_mode.get()))
        Tooltip(self._mode_combo, lambda: t("settings.tooltip.default_mode"))
        row += 1

        # Hotkeys
        self._hotkey_vars: dict[str, tk.StringVar] = {}
        self._hotkey_widgets: dict[str, tuple] = {}
        for attr, label_key, allow_combo in (
            ("hotkey_record", "settings.field.hotkey_record", False),
            ("hotkey_mode_a", "settings.field.hotkey_mode_a", True),
            ("hotkey_mode_b", "settings.field.hotkey_mode_b", True),
            ("hotkey_mode_c", "settings.field.hotkey_mode_c", True),
            ("hotkey_mode_d", "settings.field.hotkey_mode_d", True),
        ):
            ttk.Label(frame, text=t(label_key)).grid(row=row, column=0, sticky="w", pady=4)
            var = tk.StringVar(value=getattr(self._draft, attr))
            self._hotkey_vars[attr] = var
            picks = (("pause", "scroll lock", "f7", "f8", "f9", "f10", "f11", "f12", "insert", "apps")
                     if not allow_combo else
                     ("ctrl+shift+1", "ctrl+shift+2", "ctrl+shift+3",
                      "ctrl+alt+1", "ctrl+alt+2", "ctrl+alt+3"))
            cb = ttk.Combobox(frame, textvariable=var, values=picks, width=24)
            cb.grid(row=row, column=1, sticky="w")
            cb.bind("<<ComboboxSelected>>",
                    lambda _e, a=attr, v=var: self._on_hotkey_changed(a, v.get()))
            cb.bind("<FocusOut>",
                    lambda _e, a=attr, v=var: self._on_hotkey_changed(a, v.get()))
            btn = ttk.Button(frame, text=t("settings.button.other_key"),
                             command=lambda a=attr, c=allow_combo: self._capture_hotkey(a, c))
            btn.grid(row=row, column=2, padx=4)
            self._hotkey_widgets[attr] = (cb, btn)
            tooltip_key = f"settings.tooltip.{attr}"
            Tooltip(cb, lambda k=tooltip_key: t(k))
            Tooltip(btn, lambda: t("settings.tooltip.other_key_button"))
            row += 1

        self._refresh_api_gated_widgets()

    def _on_input_lang_changed(self) -> None:
        v = self._var_input_lang.get()
        if v in ("de", "en"):
            self._draft.language = v
            self._other_lang_combo.set("")

    def _on_other_lang_picked(self) -> None:
        v = self._other_lang_combo.get()
        if v:
            self._draft.language = v
            self._var_input_lang.set("")

    def _update_mode_combo_values(self) -> None:
        valid = self._any_llm_validated()
        self._mode_combo["values"] = ("clean", "business", "rage", "latex") if valid else ("clean",)
        if not valid and self._var_default_mode.get() != "clean":
            self._var_default_mode.set("clean")
            self._draft.default_mode = "clean"

    def _key_validated(self) -> bool:
        from vocix.config import load_state
        return bool(load_state().get("anthropic_key_validated"))

    def _any_llm_validated(self) -> bool:
        """B/C/L nur freischalten, wenn der für sie gewählte Provider validiert ist."""
        for m in ("business", "rage", "latex"):
            slot = self._draft.llm_mode_slot(m)
            if not self._draft.llm_validated(slot):
                return False
        return True

    def _refresh_api_gated_widgets(self) -> None:
        valid = self._any_llm_validated()
        for attr in ("hotkey_mode_b", "hotkey_mode_c", "hotkey_mode_d"):
            cb, btn = self._hotkey_widgets[attr]
            state = ["!disabled"] if valid else ["disabled"]
            cb.state(state)
            btn.state(state)
        self._update_mode_combo_values()

    def _on_hotkey_changed(self, attr: str, value: str) -> None:
        setattr(self._draft, attr, value.strip())
        self._validate()

    def _capture_hotkey(self, attr: str, allow_combos: bool) -> None:
        from vocix.ui.hotkey_capture import HotkeyCaptureDialog

        def done(hk):
            if hk:
                self._hotkey_vars[attr].set(hk)
                self._on_hotkey_changed(attr, hk)

        HotkeyCaptureDialog(self._win, allow_combos=allow_combos, on_result=done)

    def _displayed_api_key(self) -> str:
        key = self._draft.anthropic_api_key or ""
        if len(key) <= 12:
            return key
        return f"{key[:7]}…{key[-4:]}"

    def _build_advanced(self, frame: ttk.Frame) -> None:
        from tkinter import filedialog
        from vocix.ui.tooltip import Tooltip
        from vocix.ui.help_popup import HelpButton

        for col in (1,):
            frame.columnconfigure(col, weight=1)

        row = 0

        def _path_row(label_key, attr, askdir, tooltip_key=None):
            nonlocal row
            ttk.Label(frame, text=t(label_key)).grid(row=row, column=0, sticky="w", pady=4)
            var = tk.StringVar(value=getattr(self._draft, attr))
            entry = ttk.Entry(frame, textvariable=var)
            entry.grid(row=row, column=1, sticky="ew")
            entry.bind("<FocusOut>", lambda _e: setattr(self._draft, attr, var.get()))
            if tooltip_key:
                Tooltip(entry, lambda k=tooltip_key: t(k))

            def browse():
                import os
                current = var.get() or str(getattr(self._draft, attr) or "")
                if askdir:
                    p = filedialog.askdirectory(initialdir=current or None)
                else:
                    init_dir = os.path.dirname(current) if current else ""
                    init_file = os.path.basename(current) if current else ""
                    # Datei auswählen — vorhandene wird gewählt, nicht
                    # überschrieben (confirmoverwrite=False), neuer Pfad
                    # ist auch erlaubt.
                    p = filedialog.asksaveasfilename(
                        initialdir=init_dir or None,
                        initialfile=init_file or None,
                        defaultextension=".log",
                        filetypes=[
                            (t("settings.filter.log_file"), "*.log"),
                            (t("settings.filter.all_files"), "*.*"),
                        ],
                        confirmoverwrite=False,
                    )
                if p:
                    var.set(p)
                    setattr(self._draft, attr, p)

            browse_btn = ttk.Button(frame, text=t("settings.button.browse"), command=browse)
            browse_btn.grid(row=row, column=2, padx=4)
            Tooltip(browse_btn, lambda: t("settings.tooltip.browse_button"))
            row += 1
            return var

        self._var_model_dir = _path_row("settings.field.model_dir", "whisper_model_dir", askdir=True,
                                        tooltip_key="settings.tooltip.model_dir")
        self._var_log_file = _path_row("settings.field.log_file", "log_file", askdir=False,
                                       tooltip_key="settings.tooltip.log_file")

        ttk.Label(frame, text=t("settings.field.log_level")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_log_level = tk.StringVar(value=self._draft.log_level)
        cb = ttk.Combobox(frame, state="readonly", width=12, textvariable=self._var_log_level,
                          values=("DEBUG", "INFO", "WARNING", "ERROR"))
        cb.grid(row=row, column=1, sticky="w")
        cb.bind("<<ComboboxSelected>>",
                lambda _e: setattr(self._draft, "log_level", self._var_log_level.get()))
        Tooltip(cb, lambda: t("settings.tooltip.log_level"))
        row += 1

        ttk.Label(frame, text=t("settings.field.overlay_seconds")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_overlay = tk.DoubleVar(value=self._draft.overlay_display_seconds)
        sp = ttk.Spinbox(frame, from_=0.5, to=10.0, increment=0.5, width=8,
                        textvariable=self._var_overlay,
                        command=lambda: setattr(self._draft, "overlay_display_seconds",
                                               float(self._var_overlay.get())))
        sp.grid(row=row, column=1, sticky="w")
        Tooltip(sp, lambda: t("settings.tooltip.overlay_seconds"))
        row += 1

        ttk.Label(frame, text=t("settings.field.rdp_mode")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_rdp = tk.BooleanVar(value=self._draft.rdp_mode)
        rdp_check = ttk.Checkbutton(frame, variable=self._var_rdp, command=self._on_rdp_changed)
        rdp_check.grid(row=row, column=1, sticky="w")
        Tooltip(rdp_check, lambda: t("settings.tooltip.rdp_mode"))
        HelpButton(frame,
                   title_provider=lambda: t("settings.help.rdp_mode.title"),
                   body_provider=lambda: t("settings.help.rdp_mode.body")
                   ).grid(row=row, column=2)
        row += 1

        ttk.Label(frame, text=t("settings.field.clipboard_delay")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_clipboard = tk.DoubleVar(value=self._draft.clipboard_delay)
        self._clipboard_spin = ttk.Spinbox(frame, from_=0.01, to=1.0, increment=0.05, width=8,
                                          textvariable=self._var_clipboard,
                                          command=lambda: setattr(self._draft, "clipboard_delay",
                                                                 float(self._var_clipboard.get())))
        self._clipboard_spin.grid(row=row, column=1, sticky="w")
        Tooltip(self._clipboard_spin, lambda: t("settings.tooltip.clipboard_delay"))
        row += 1

        ttk.Label(frame, text=t("settings.field.paste_delay")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_paste = tk.DoubleVar(value=self._draft.paste_delay)
        self._paste_spin = ttk.Spinbox(frame, from_=0.05, to=1.0, increment=0.05, width=8,
                                       textvariable=self._var_paste,
                                       command=lambda: setattr(self._draft, "paste_delay",
                                                              float(self._var_paste.get())))
        self._paste_spin.grid(row=row, column=1, sticky="w")
        Tooltip(self._paste_spin, lambda: t("settings.tooltip.paste_delay"))
        row += 1

        ttk.Label(frame, text=t("settings.field.silence_threshold")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_silence = tk.DoubleVar(value=self._draft.silence_threshold)
        scale = ttk.Scale(frame, from_=0.001, to=0.1, variable=self._var_silence,
                         command=lambda _v: setattr(self._draft, "silence_threshold",
                                                   float(self._var_silence.get())))
        scale.grid(row=row, column=1, sticky="ew")
        ttk.Label(frame, textvariable=self._var_silence, width=8).grid(row=row, column=2)
        HelpButton(frame,
                   title_provider=lambda: t("settings.help.silence_threshold.title"),
                   body_provider=lambda: t("settings.help.silence_threshold.body")
                   ).grid(row=row, column=3, padx=4)
        row += 1

        ttk.Label(frame, text=t("settings.field.min_duration")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_min_dur = tk.DoubleVar(value=self._draft.min_duration)
        min_dur_spin = ttk.Spinbox(frame, from_=0.1, to=5.0, increment=0.1, width=8,
                                   textvariable=self._var_min_dur,
                                   command=lambda: setattr(self._draft, "min_duration",
                                                          float(self._var_min_dur.get())))
        min_dur_spin.grid(row=row, column=1, sticky="w")
        Tooltip(min_dur_spin, lambda: t("settings.tooltip.min_duration"))
        row += 1

        self._on_rdp_changed()

    def _on_rdp_changed(self) -> None:
        self._draft.rdp_mode = self._var_rdp.get()
        if self._draft.rdp_mode:
            self._clipboard_spin.state(["disabled"])
            self._paste_spin.state(["disabled"])
        else:
            self._clipboard_spin.state(["!disabled"])
            self._paste_spin.state(["!disabled"])

    def _build_expert(self, frame: ttk.Frame) -> None:
        import os
        from vocix.ui.help_popup import HelpButton
        from vocix.ui.tooltip import Tooltip

        for col in (1,):
            frame.columnconfigure(col, weight=1)
        row = 0

        ttk.Label(frame, text=t("settings.field.whisper_language_override")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_whisper_lang = tk.StringVar(value=self._draft.whisper_language_override or "auto")
        cb = ttk.Combobox(frame, state="readonly", width=14, textvariable=self._var_whisper_lang,
                          values=("auto", "de", "en", "fr", "es", "it", "nl", "pl", "pt", "tr", "ru", "ja", "zh"))
        cb.grid(row=row, column=1, sticky="w")
        cb.bind("<<ComboboxSelected>>",
                lambda _e: setattr(self._draft, "whisper_language_override",
                                  "" if self._var_whisper_lang.get() == "auto" else self._var_whisper_lang.get()))
        Tooltip(cb, lambda: t("settings.tooltip.whisper_language_override"))
        HelpButton(frame,
                   title_provider=lambda: t("settings.help.whisper_language_override.title"),
                   body_provider=lambda: t("settings.help.whisper_language_override.body")
                   ).grid(row=row, column=2, padx=4)
        row += 1

        ttk.Label(frame, text=t("settings.field.sample_rate")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_sample_rate = tk.IntVar(value=self._draft.sample_rate)
        cb = ttk.Combobox(frame, state="readonly", width=10, textvariable=self._var_sample_rate,
                          values=(16000, 22050, 44100, 48000))
        cb.grid(row=row, column=1, sticky="w")
        cb.bind("<<ComboboxSelected>>",
                lambda _e: setattr(self._draft, "sample_rate", int(self._var_sample_rate.get())))
        Tooltip(cb, lambda: t("settings.tooltip.sample_rate"))
        HelpButton(frame,
                   title_provider=lambda: t("settings.help.sample_rate.title"),
                   body_provider=lambda: t("settings.help.sample_rate.body")
                   ).grid(row=row, column=2, padx=4)
        row += 1

        # Buttons (Reihe 4 vorgeschoben damit Anthropic darüber Platz hat)
        cfg_btn = ttk.Button(frame, text=t("settings.button.open_config_dir"),
                             command=lambda: os.startfile(self._config_dir()))
        cfg_btn.grid(row=row + 2, column=0, sticky="w", pady=(20, 4))
        Tooltip(cfg_btn, lambda: t("settings.tooltip.open_config_dir_button"))
        reset_btn = ttk.Button(frame, text=t("settings.button.reset"),
                               command=self._on_factory_reset)
        reset_btn.grid(row=row + 2, column=1, sticky="w", pady=(20, 4))
        Tooltip(reset_btn, lambda: t("settings.tooltip.reset_button"))

    def _config_dir(self) -> str:
        from vocix.config import STATE_FILE
        return str(STATE_FILE.parent)

    def _on_factory_reset(self) -> None:
        from tkinter import messagebox
        from vocix.config import save_state
        if not messagebox.askyesno(t("settings.title"), t("settings.confirm.factory_reset")):
            return
        save_state({})
        self._draft = replace(Config())
        messagebox.showinfo(t("settings.title"), t("settings.confirm.factory_reset_done"))
        self._on_cancel()

    def _validate(self) -> bool:
        self._error_var.set("")
        if "+" in (self._draft.hotkey_record or ""):
            self._error_var.set(t("settings.error.ptt_combo_not_allowed"))
            return False
        keys = [
            self._draft.hotkey_record,
            self._draft.hotkey_mode_a,
            self._draft.hotkey_mode_b,
            self._draft.hotkey_mode_c,
            self._draft.hotkey_mode_d,
        ]
        non_empty = [k for k in keys if k]
        if len(set(non_empty)) != len(non_empty):
            self._error_var.set(t("settings.error.duplicate_hotkey"))
            return False
        return True

    def _on_apply(self) -> None:
        if not self._validate():
            return
        self._persist_llm_draft()
        self._on_apply_cb(replace(self._draft))

    def _on_ok(self) -> None:
        if not self._validate():
            return
        self._persist_llm_draft()
        self._on_apply_cb(replace(self._draft))
        self.destroy()

    def _on_cancel(self) -> None:
        self.destroy()

    def destroy(self) -> None:
        try:
            i18n.unregister_language_listener(self._on_external_language_change)
        except Exception:
            pass
        try:
            self._win.grab_release()
            self._win.destroy()
        except tk.TclError:
            pass

    def _build_llm(self, frame: ttk.Frame) -> None:
        for col in (0, 1, 2):
            frame.columnconfigure(col, weight=1 if col == 1 else 0)

        # ---- Routing-Sektion (oben) -----------------------------------
        routing = ttk.LabelFrame(frame, text=t("settings.llm.section.routing"), padding=8)
        routing.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        for col in (0, 1):
            routing.columnconfigure(col, weight=0)
        routing.columnconfigure(2, weight=1)

        slot_labels = (
            ("anthropic", t("provider.anthropic.name")),
            ("openai", t("provider.openai.name")),
            ("ollama", t("provider.ollama.name")),
        )
        slot_values = [k for k, _ in slot_labels]

        # Default
        ttk.Label(routing, text=t("settings.llm.default")).grid(row=0, column=0, sticky="w", pady=2)
        self._var_llm_default = tk.StringVar(value=self._draft.llm_default_slot())
        cb_default = ttk.Combobox(routing, state="readonly", width=22, textvariable=self._var_llm_default,
                                  values=tuple(slot_values))
        cb_default.grid(row=0, column=1, sticky="w")
        cb_default.bind("<<ComboboxSelected>>", lambda _e: self._on_routing_changed())

        # Business override
        ttk.Label(routing, text=t("settings.llm.business_override")).grid(row=1, column=0, sticky="w", pady=2)
        self._var_llm_business = tk.StringVar(value=(self._draft.llm.get("business") or "__default__"))
        cb_b = ttk.Combobox(routing, state="readonly", width=22, textvariable=self._var_llm_business,
                            values=("__default__", *slot_values))
        cb_b.grid(row=1, column=1, sticky="w")
        cb_b.bind("<<ComboboxSelected>>", lambda _e: self._on_routing_changed())

        # Rage override
        ttk.Label(routing, text=t("settings.llm.rage_override")).grid(row=2, column=0, sticky="w", pady=2)
        self._var_llm_rage = tk.StringVar(value=(self._draft.llm.get("rage") or "__default__"))
        cb_r = ttk.Combobox(routing, state="readonly", width=22, textvariable=self._var_llm_rage,
                            values=("__default__", *slot_values))
        cb_r.grid(row=2, column=1, sticky="w")
        cb_r.bind("<<ComboboxSelected>>", lambda _e: self._on_routing_changed())

        # LaTeX override
        ttk.Label(routing, text=t("settings.llm.latex_override")).grid(row=3, column=0, sticky="w", pady=2)
        self._var_llm_latex = tk.StringVar(value=(self._draft.llm.get("latex") or "__default__"))
        cb_l = ttk.Combobox(routing, state="readonly", width=22, textvariable=self._var_llm_latex,
                            values=("__default__", *slot_values))
        cb_l.grid(row=3, column=1, sticky="w")
        cb_l.bind("<<ComboboxSelected>>", lambda _e: self._on_routing_changed())

        # ---- Provider-Karten -----------------------------------------
        self._llm_status_vars: dict[str, tk.StringVar] = {}

        # Anthropic
        anth = ttk.LabelFrame(frame, text=t("settings.llm.section.anthropic"), padding=8)
        anth.grid(row=1, column=0, columnspan=3, sticky="ew", pady=4)
        anth.columnconfigure(1, weight=1)
        self._var_llm_anth_key = tk.StringVar(value=self._draft.anthropic_api_key or "")
        self._var_llm_anth_model = tk.StringVar(value=self._draft.anthropic_model)
        self._var_llm_anth_timeout = tk.DoubleVar(value=self._draft.anthropic_timeout)
        self._llm_status_vars["anthropic"] = tk.StringVar(value="")
        self._build_provider_card(
            anth, slot_id="anthropic",
            fields=[
                ("api_key", self._var_llm_anth_key, "password"),
                ("model", self._var_llm_anth_model, "text"),
                ("timeout", self._var_llm_anth_timeout, "spin"),
            ],
        )

        # OpenAI-kompatibel
        oai = ttk.LabelFrame(frame, text=t("settings.llm.section.openai"), padding=8)
        oai.grid(row=2, column=0, columnspan=3, sticky="ew", pady=4)
        oai.columnconfigure(1, weight=1)
        slot_oai = (self._draft.llm.get("providers") or {}).get("openai") or {}
        self._var_llm_oai_key = tk.StringVar(value=slot_oai.get("api_key", ""))
        self._var_llm_oai_url = tk.StringVar(value=slot_oai.get("base_url", ""))
        self._var_llm_oai_model = tk.StringVar(value=slot_oai.get("model", "gpt-4o-mini"))
        self._var_llm_oai_timeout = tk.DoubleVar(value=slot_oai.get("timeout", 15.0))
        self._llm_status_vars["openai"] = tk.StringVar(value="")
        self._build_provider_card(
            oai, slot_id="openai",
            fields=[
                ("base_url", self._var_llm_oai_url, "text"),
                ("api_key", self._var_llm_oai_key, "password"),
                ("model", self._var_llm_oai_model, "text"),
                ("timeout", self._var_llm_oai_timeout, "spin"),
            ],
            help_key="settings.llm.help.openai_base_url",
        )

        # Ollama
        oll = ttk.LabelFrame(frame, text=t("settings.llm.section.ollama"), padding=8)
        oll.grid(row=3, column=0, columnspan=3, sticky="ew", pady=4)
        oll.columnconfigure(1, weight=1)
        slot_oll = (self._draft.llm.get("providers") or {}).get("ollama") or {}
        self._var_llm_oll_url = tk.StringVar(value=slot_oll.get("base_url", "http://localhost:11434"))
        self._var_llm_oll_model = tk.StringVar(value=slot_oll.get("model", "llama3.1:8b"))
        self._var_llm_oll_timeout = tk.DoubleVar(value=slot_oll.get("timeout", 30.0))
        self._llm_status_vars["ollama"] = tk.StringVar(value="")
        self._build_provider_card(
            oll, slot_id="ollama",
            fields=[
                ("base_url", self._var_llm_oll_url, "text"),
                ("model", self._var_llm_oll_model, "text"),
                ("timeout", self._var_llm_oll_timeout, "spin"),
            ],
            help_key="settings.llm.help.ollama_base_url",
        )

    def _build_provider_card(
        self,
        parent: ttk.LabelFrame,
        *,
        slot_id: str,
        fields: list[tuple[str, tk.Variable, str]],
        help_key: str | None = None,
    ) -> None:
        row = 0
        for fname, var, kind in fields:
            ttk.Label(parent, text=t(f"settings.llm.field.{fname}")).grid(row=row, column=0, sticky="w", pady=2)
            if kind == "password":
                e = ttk.Entry(parent, textvariable=var, show="*", width=36)
            elif kind == "spin":
                e = ttk.Spinbox(parent, from_=1, to=120, increment=1, width=8, textvariable=var)
            else:
                e = ttk.Entry(parent, textvariable=var, width=36)
            e.grid(row=row, column=1, sticky="ew")
            row += 1

        if help_key:
            ttk.Label(parent, text=t(help_key), foreground="#666", wraplength=560).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(2, 4)
            )
            row += 1

        btn = ttk.Button(parent, text=t("settings.button.test"),
                         command=lambda s=slot_id: self._on_llm_test(s))
        btn.grid(row=row, column=0, sticky="w", pady=(4, 0))
        ttk.Label(parent, textvariable=self._llm_status_vars[slot_id]).grid(
            row=row, column=1, sticky="w", padx=(8, 0), pady=(4, 0)
        )

    def _on_routing_changed(self) -> None:
        self._draft.llm.setdefault("providers", {})
        self._draft.llm["default"] = self._var_llm_default.get()
        b = self._var_llm_business.get()
        r = self._var_llm_rage.get()
        l = self._var_llm_latex.get()
        self._draft.llm["business"] = None if b == "__default__" else b
        self._draft.llm["rage"] = None if r == "__default__" else r
        self._draft.llm["latex"] = None if l == "__default__" else l
        self._refresh_api_gated_widgets()

    def _on_llm_test(self, slot_id: str) -> None:
        from vocix.config import update_state
        status_var = self._llm_status_vars[slot_id]
        status_var.set(t("provider.test.in_progress"))
        self._win.update_idletasks()

        if slot_id == "anthropic":
            ok, err = _ping_anthropic(
                self._var_llm_anth_key.get().strip(),
                self._var_llm_anth_model.get().strip(),
                float(self._var_llm_anth_timeout.get()),
            )
        elif slot_id == "openai":
            ok, err = _ping_openai(
                self._var_llm_oai_key.get().strip(),
                self._var_llm_oai_url.get().strip(),
                self._var_llm_oai_model.get().strip(),
                float(self._var_llm_oai_timeout.get()),
            )
        elif slot_id == "ollama":
            ok, err = _ping_ollama(
                self._var_llm_oll_url.get().strip(),
                self._var_llm_oll_model.get().strip(),
                float(self._var_llm_oll_timeout.get()),
            )
        else:
            ok, err = False, f"unknown slot {slot_id}"

        with update_state() as s:
            s.setdefault("llm", {}).setdefault("providers", {}).setdefault(slot_id, {})
            s["llm"]["providers"][slot_id]["validated"] = ok

        if ok:
            status_var.set(t("provider.test.success"))
        else:
            short = (err or "")[:80]
            status_var.set(t("provider.test.error", detail=short))

        self._refresh_api_gated_widgets()

    def _persist_llm_draft(self) -> None:
        """Schreibt die UI-Variablen ins draft.llm-Schema und entfernt Legacy-Felder."""
        providers = self._draft.llm.setdefault("providers", {})
        providers["anthropic"] = {
            "api_key": self._var_llm_anth_key.get().strip(),
            "model": self._var_llm_anth_model.get().strip(),
            "timeout": float(self._var_llm_anth_timeout.get()),
            "validated": providers.get("anthropic", {}).get("validated", False),
        }
        providers["openai"] = {
            "api_key": self._var_llm_oai_key.get().strip(),
            "base_url": self._var_llm_oai_url.get().strip(),
            "model": self._var_llm_oai_model.get().strip(),
            "timeout": float(self._var_llm_oai_timeout.get()),
            "validated": providers.get("openai", {}).get("validated", False),
        }
        providers["ollama"] = {
            "base_url": self._var_llm_oll_url.get().strip(),
            "model": self._var_llm_oll_model.get().strip(),
            "timeout": float(self._var_llm_oll_timeout.get()),
        }
        self._draft.anthropic_api_key = providers["anthropic"]["api_key"]
        self._draft.anthropic_model = providers["anthropic"]["model"]
        self._draft.anthropic_timeout = providers["anthropic"]["timeout"]

    def _on_external_language_change(self, _code: str) -> None:
        """Tray switched the UI language while this dialog is open. We can't
        cheaply rebuild every label, so we lock saving and show a notice
        telling the user to reopen the dialog."""
        try:
            if not self._win.winfo_exists():
                return
        except tk.TclError:
            return

        def _apply():
            try:
                self._error_var.set(t("settings.notice.language_changed"))
                self._apply_btn.state(["disabled"])
                self._ok_btn.state(["disabled"])
            except tk.TclError:
                pass

        try:
            self._win.after(0, _apply)
        except tk.TclError:
            pass
