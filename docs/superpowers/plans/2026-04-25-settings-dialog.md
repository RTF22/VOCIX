# Settings-Dialog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine zentrale tkinter/ttk-Maske mit drei Tabs (Basics/Erweitert/Expert), die alle Config-, .env- und Tray-Einstellungen erreichbar macht. Persistenz nach `state.json`, OK/Abbrechen/Übernehmen-Semantik, Tooltips + ?-Hilfe-Popups, sicheres API-Key-Handling.

**Architecture:** Neuer `SettingsDialog` als `tk.Toplevel` im Overlay-Thread (gleicher Thread wie About/Statistik). Bindet Tk-Variablen an eine Config-Kopie; OK/Apply ruft `VocixApp.apply_settings(new_config)`, das den Diff orchestriert: `state.json`-Schreiben, Whisper-Reload, Hotkey-Rebind, i18n-Sprachwechsel, Tray-Rebuild. Tray bleibt unverändert + bekommt einen zusätzlichen Menüeintrag „Einstellungen…".

**Tech Stack:** tkinter/ttk (Bordmittel), faster-whisper, anthropic SDK (Test-Ping), keyboard-Library, bestehende `update_state()`-Lock-API, i18n via `locales/{de,en}.json`.

**Spec:** `docs/superpowers/specs/2026-04-25-settings-dialog-design.md`

---

## File Structure

**Create:**
- `vocix/ui/tooltip.py` — Tooltip-Hilfsklasse (~30 LOC)
- `vocix/ui/help_popup.py` — `?`-Button-Helper + Modal-Popup
- `vocix/ui/hotkey_capture.py` — Hotkey-Capture-Modal
- `vocix/ui/settings.py` — `SettingsDialog` + Tab-Builder
- `tests/ui/test_tooltip.py`
- `tests/ui/test_hotkey_capture.py`
- `tests/ui/test_settings.py`
- `tests/ui/__init__.py` (falls nicht vorhanden)

**Modify:**
- `vocix/config.py` — `Config.load()` erweitern um neue State-Keys, neue Felder
- `vocix/i18n.py` — keine Änderung (key-basiert reicht)
- `locales/de.json` / `locales/en.json` — neuer `settings.*`-Block
- `vocix/ui/overlay.py` — Methode `show_settings(config, on_apply)` analog `show_about`
- `vocix/ui/tray.py` — Menüeintrag „Einstellungen…", neuer Callback
- `vocix/main.py` — `VocixApp.apply_settings()`, Open-Settings-Routing, Tray-Wiring
- `vocix/__init__.py` — Versions-Bump auf `1.4.0-beta.1`

---

## Task 1: Config-Felder & State-Persistenz erweitern

**Files:**
- Modify: `vocix/config.py`
- Test: `tests/test_config.py` (existiert bereits — falls nicht, in `tests/test_settings_state.py` neu)

Heute werden in `state.json` nur `language`, `whisper_model`, `whisper_acceleration`, `translate_to_english`, `skip_update_version` persistiert. Wir erweitern auf alle Felder, die der Dialog setzen kann.

- [ ] **Step 1: Test schreiben — load_state liest neue Felder**

`tests/test_settings_state.py` (neu):

```python
import json
from pathlib import Path
from unittest.mock import patch

from vocix.config import Config


def test_config_load_reads_new_state_fields(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({
        "language": "en",
        "whisper_model": "medium",
        "whisper_acceleration": "cpu",
        "translate_to_english": True,
        "default_mode": "business",
        "hotkey_record": "f9",
        "hotkey_mode_a": "ctrl+shift+1",
        "hotkey_mode_b": "ctrl+shift+2",
        "hotkey_mode_c": "ctrl+shift+3",
        "log_level": "DEBUG",
        "log_file": str(tmp_path / "vocix.log"),
        "whisper_model_dir": str(tmp_path / "models"),
        "overlay_display_seconds": 2.5,
        "rdp_mode": True,
        "silence_threshold": 0.02,
        "min_duration": 0.7,
        "sample_rate": 16000,
        "anthropic_api_key": "sk-ant-test",
        "anthropic_model": "claude-sonnet-4-6",
        "anthropic_timeout": 20.0,
        "whisper_language_override": "fr",
        "anthropic_key_validated": True,
    }))
    monkeypatch.setattr("vocix.config.STATE_FILE", state_file)

    config = Config.load(env_file=tmp_path / ".env-does-not-exist")

    assert config.language == "en"
    assert config.whisper_model == "medium"
    assert config.default_mode == "business"
    assert config.hotkey_record == "f9"
    assert config.log_level == "DEBUG"
    assert config.overlay_display_seconds == 2.5
    assert config.rdp_mode is True
    assert config.silence_threshold == 0.02
    assert config.anthropic_api_key == "sk-ant-test"
    assert config.anthropic_model == "claude-sonnet-4-6"
    assert config.whisper_language_override == "fr"
```

- [ ] **Step 2: Test laufen lassen, FAIL erwarten**

Run: `python -m pytest tests/test_settings_state.py -v`
Expected: FAIL — Felder werden noch nicht aus state.json gelesen.

- [ ] **Step 3: `Config.load()` erweitern**

In `vocix/config.py` am Ende von `Config.load()` (nach den existierenden `state.get(...)`-Blöcken) ergänzen:

```python
        # Hotkeys
        for key in ("hotkey_record", "hotkey_mode_a", "hotkey_mode_b", "hotkey_mode_c"):
            v = state.get(key)
            if isinstance(v, str) and v.strip():
                setattr(config, key, v)

        # Modus
        if state.get("default_mode") in ("clean", "business", "rage"):
            config.default_mode = state["default_mode"]

        # Logging / Pfade
        if isinstance(state.get("log_level"), str):
            config.log_level = state["log_level"].upper()
        for key in ("log_file", "whisper_model_dir"):
            v = state.get(key)
            if isinstance(v, str) and v.strip():
                setattr(config, key, v)

        # UI
        v = state.get("overlay_display_seconds")
        if isinstance(v, (int, float)) and v > 0:
            config.overlay_display_seconds = float(v)

        # RDP / Audio
        if isinstance(state.get("rdp_mode"), bool):
            config.rdp_mode = state["rdp_mode"]
        for key in ("clipboard_delay", "paste_delay", "silence_threshold", "min_duration"):
            v = state.get(key)
            if isinstance(v, (int, float)) and v > 0:
                setattr(config, key, float(v))
        v = state.get("sample_rate")
        if isinstance(v, int) and v > 0:
            config.sample_rate = v

        # Anthropic
        for key in ("anthropic_api_key", "anthropic_model"):
            v = state.get(key)
            if isinstance(v, str) and v.strip():
                setattr(config, key, v)
        v = state.get("anthropic_timeout")
        if isinstance(v, (int, float)) and v > 0:
            config.anthropic_timeout = float(v)

        # Whisper-Sprach-Override (leerer String = an `language` koppeln)
        if isinstance(state.get("whisper_language_override"), str):
            config.whisper_language_override = state["whisper_language_override"]

        # Wiederholt einmal __post_init__ um RDP-Delays neu zu berechnen,
        # falls rdp_mode aus state.json kam.
        config.__post_init__()
```

Achtung: `__post_init__` validiert `hotkey_record` — wenn aus state.json eine ungültige Kombo käme, würde es jetzt raisen. Das ist gewollt (Fail-Fast), aber wir wollen die Hotkey-Validierung erst dort machen, nachdem wir den State-Wert übernommen haben — also ist die Reihenfolge korrekt. Wenn `__post_init__` raised, fängt die `Config.load()`-Exception bis `main.py` durch — dort dann mit native_dialog ein Fehler, den State auf Default zurückzusetzen. Das ist Out-of-Scope dieses Tasks, der existierende Pfad genügt vorerst.

- [ ] **Step 4: Test grün**

Run: `python -m pytest tests/test_settings_state.py -v`
Expected: PASS.

- [ ] **Step 5: Bestehende Tests laufen lassen — keine Regression**

Run: `python -m pytest tests/ -q`
Expected: alle vorher grünen Tests bleiben grün.

- [ ] **Step 6: Commit**

```bash
git add vocix/config.py tests/test_settings_state.py
git commit -m "config: alle Settings-Dialog-Felder aus state.json laden"
```

---

## Task 2: i18n-Keys für Settings-Dialog

**Files:**
- Modify: `locales/de.json`, `locales/en.json`
- Test: `tests/test_i18n_settings.py`

- [ ] **Step 1: Test schreiben — alle Settings-Keys vorhanden in beiden Sprachen**

`tests/test_i18n_settings.py`:

```python
import json
from pathlib import Path

REQUIRED_KEYS = [
    "settings.title",
    "settings.tab.basics", "settings.tab.advanced", "settings.tab.expert",
    "settings.button.ok", "settings.button.cancel", "settings.button.apply",
    "settings.button.test", "settings.button.browse", "settings.button.other_key",
    "settings.button.reset", "settings.button.open_config_dir",
    "settings.field.input_language", "settings.field.output_language",
    "settings.field.whisper_model", "settings.field.acceleration",
    "settings.field.api_key", "settings.field.default_mode",
    "settings.field.hotkey_record", "settings.field.hotkey_mode_a",
    "settings.field.hotkey_mode_b", "settings.field.hotkey_mode_c",
    "settings.field.model_dir", "settings.field.log_file", "settings.field.log_level",
    "settings.field.overlay_seconds", "settings.field.rdp_mode",
    "settings.field.clipboard_delay", "settings.field.paste_delay",
    "settings.field.silence_threshold", "settings.field.min_duration",
    "settings.field.whisper_language_override", "settings.field.sample_rate",
    "settings.field.anthropic_model", "settings.field.anthropic_timeout",
    "settings.tooltip.input_language", "settings.tooltip.output_language",
    "settings.tooltip.whisper_model", "settings.tooltip.acceleration",
    "settings.tooltip.api_key", "settings.tooltip.default_mode",
    "settings.tooltip.hotkey_record", "settings.tooltip.rdp_mode",
    "settings.tooltip.silence_threshold", "settings.tooltip.sample_rate",
    "settings.help.whisper_model.title", "settings.help.whisper_model.body",
    "settings.help.acceleration.title", "settings.help.acceleration.body",
    "settings.help.api_key.title", "settings.help.api_key.body",
    "settings.help.rdp_mode.title", "settings.help.rdp_mode.body",
    "settings.help.silence_threshold.title", "settings.help.silence_threshold.body",
    "settings.help.sample_rate.title", "settings.help.sample_rate.body",
    "settings.help.whisper_language_override.title",
    "settings.help.whisper_language_override.body",
    "settings.help.anthropic_model.title", "settings.help.anthropic_model.body",
    "settings.status.api_valid", "settings.status.api_invalid", "settings.status.api_unchecked",
    "settings.status.api_locked",
    "settings.error.duplicate_hotkey", "settings.error.ptt_combo_not_allowed",
    "settings.error.path_missing", "settings.confirm.factory_reset",
    "settings.lang.de", "settings.lang.en", "settings.lang.other",
    "settings.output.input_lang", "settings.output.english",
    "settings.modifier.none", "settings.modifier.ctrl", "settings.modifier.ctrl_shift",
    "settings.modifier.ctrl_alt", "settings.modifier.alt_shift",
    "settings.capture.prompt", "settings.capture.cancel_hint",
]


def _flatten(d, prefix=""):
    for k, v in d.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            yield from _flatten(v, path)
        else:
            yield path


def _load(name):
    p = Path(__file__).resolve().parent.parent / "locales" / name
    return set(_flatten(json.loads(p.read_text(encoding="utf-8"))))


def test_de_has_all_settings_keys():
    keys = _load("de.json")
    missing = [k for k in REQUIRED_KEYS if k not in keys]
    assert not missing, f"Missing in de.json: {missing}"


def test_en_has_all_settings_keys():
    keys = _load("en.json")
    missing = [k for k in REQUIRED_KEYS if k not in keys]
    assert not missing, f"Missing in en.json: {missing}"
```

- [ ] **Step 2: Test laufen, FAIL erwarten**

Run: `python -m pytest tests/test_i18n_settings.py -v`
Expected: FAIL — alle Keys fehlen.

- [ ] **Step 3: `locales/de.json` erweitern**

Falls die JSON heute flach ist, füge eine neue Top-Level-Sektion `"settings"` hinzu (i18n.py macht dotted-key-Lookup, das funktioniert sowohl flach als auch verschachtelt — siehe `_get_translation`). Hier verschachtelt:

```json
"settings": {
  "title": "VOCIX — Einstellungen",
  "tab": { "basics": "Basics", "advanced": "Erweitert", "expert": "Expert" },
  "button": {
    "ok": "OK", "cancel": "Abbrechen", "apply": "Übernehmen",
    "test": "Test", "browse": "Durchsuchen…", "other_key": "Andere Taste…",
    "reset": "Auf Werkseinstellungen zurücksetzen",
    "open_config_dir": "Konfigurationsverzeichnis öffnen"
  },
  "field": {
    "input_language": "Eingabesprache",
    "output_language": "Ausgabesprache",
    "whisper_model": "Whisper-Modell",
    "acceleration": "Beschleunigung",
    "api_key": "Anthropic API-Key",
    "default_mode": "Standardmodus beim Start",
    "hotkey_record": "Aufnahme-Hotkey (Push-to-Talk)",
    "hotkey_mode_a": "Hotkey Modus Clean",
    "hotkey_mode_b": "Hotkey Modus Business",
    "hotkey_mode_c": "Hotkey Modus Rage",
    "model_dir": "Modellverzeichnis",
    "log_file": "Logfile",
    "log_level": "Loglevel",
    "overlay_seconds": "Overlay-Anzeigedauer (s)",
    "rdp_mode": "Remote-Desktop-Modus",
    "clipboard_delay": "Clipboard-Delay (s)",
    "paste_delay": "Paste-Delay (s)",
    "silence_threshold": "Stille-Schwelle",
    "min_duration": "Mindestaufnahmedauer (s)",
    "whisper_language_override": "Whisper-Sprach-Override",
    "sample_rate": "Sample-Rate",
    "anthropic_model": "Anthropic-Modell-ID",
    "anthropic_timeout": "Anthropic-Timeout (s)"
  },
  "tooltip": {
    "input_language": "Sprache, in der du sprichst — wird an Whisper übergeben.",
    "output_language": "Was am Cursor eingefügt wird: Originalsprache oder ins Englische übersetzt.",
    "whisper_model": "Größeres Modell = bessere Qualität, mehr RAM, langsamer.",
    "acceleration": "GPU benötigt CUDA-Bibliotheken (nur Source-Setup).",
    "api_key": "Wird benötigt für Modus Business und Rage. Test öffnet einen kurzen Ping.",
    "default_mode": "Modus, mit dem VOCIX startet. Business/Rage setzen einen gültigen API-Key voraus.",
    "hotkey_record": "Einzeltaste — Push-to-Talk benötigt Hold-fähige Tasten (z. B. Pause, F9).",
    "rdp_mode": "Verlängert Clipboard-/Paste-Delays für Remote-Desktop-Sitzungen.",
    "silence_threshold": "RMS-Wert, unter dem Audio als Stille gilt. Höher = aggressiver schneiden.",
    "sample_rate": "Whisper erwartet 16000 Hz — andere Werte sind experimentell."
  },
  "help": {
    "whisper_model": {
      "title": "Whisper-Modelle im Vergleich",
      "body": "tiny ~75 MB, sehr schnell, niedrige Genauigkeit\nbase ~150 MB, schnell\nsmall ~500 MB, ausgewogen (Default)\nmedium ~1.5 GB, hohe Genauigkeit\nlarge-v3 ~3 GB, höchste Genauigkeit, langsam\nlarge-v3-turbo ~1.6 GB, fast wie large-v3 bei halber Latenz"
    },
    "acceleration": {
      "title": "Hardware-Beschleunigung",
      "body": "Auto: nutzt GPU, wenn verfügbar; sonst CPU.\nGPU: erzwingt CUDA — benötigt nvidia-cublas + nvidia-cudnn (nur Source-Setup, nicht im ZIP).\nCPU: erzwingt CPU. Funktioniert immer, langsamer."
    },
    "api_key": {
      "title": "Anthropic API-Key",
      "body": "Erforderlich für Business- und Rage-Modus. Du erhältst einen Key unter https://console.anthropic.com. Der Key wird verschlüsselt gespeichert ist nicht erforderlich, wenn du nur Clean-Modus nutzt."
    },
    "rdp_mode": {
      "title": "Remote-Desktop-Modus",
      "body": "Aktiviert verlängerte Clipboard- und Paste-Delays, weil RDP die Zwischenablage zwischen Host und Client synchronisieren muss. Empfehlung: an, wenn du VOCIX über RDP nutzt."
    },
    "silence_threshold": {
      "title": "Stille-Schwelle",
      "body": "Bestimmt, ab welchem RMS-Pegel Audio als Stille gilt. Höhere Werte schneiden aggressiver. Standard 0.01 funktioniert in den meisten Umgebungen; in lauten Räumen ggf. erhöhen."
    },
    "sample_rate": {
      "title": "Sample-Rate",
      "body": "Whisper-Modelle wurden auf 16 kHz trainiert. Andere Sample-Rates werden intern resampled — nur ändern, wenn du genau weißt was du tust."
    },
    "whisper_language_override": {
      "title": "Whisper-Sprach-Override",
      "body": "Normalerweise nutzt Whisper deine Eingabesprache. Hier kannst du eine andere Sprache erzwingen (z. B. wenn du auf Deutsch sprichst, aber Whisper soll als Französisch transkribieren). \"auto\" = an Eingabesprache koppeln."
    },
    "anthropic_model": {
      "title": "Anthropic-Modell-ID",
      "body": "claude-sonnet-4-6 — schnell, gut für Business/Rage (Default).\nclaude-opus-4-7 — höchste Qualität, langsamer, teurer.\nclaude-haiku-4-5-20251001 — sehr schnell, günstig, einfache Umformulierungen."
    }
  },
  "status": {
    "api_valid": "✓ API-Key gültig",
    "api_invalid": "✗ Ungültig",
    "api_unchecked": "– Nicht geprüft",
    "api_locked": "API-Key in Basics setzen, um Claude-Optionen freizuschalten."
  },
  "error": {
    "duplicate_hotkey": "Dieser Hotkey ist bereits belegt.",
    "ptt_combo_not_allowed": "Push-to-Talk benötigt eine Einzeltaste.",
    "path_missing": "Pfad existiert nicht."
  },
  "confirm": {
    "factory_reset": "Wirklich alle Einstellungen auf Werkszustand zurücksetzen?"
  },
  "lang": { "de": "Deutsch", "en": "Englisch", "other": "Andere…" },
  "output": { "input_lang": "Wie Eingabesprache", "english": "Englisch" },
  "modifier": {
    "none": "(kein)", "ctrl": "Ctrl", "ctrl_shift": "Ctrl+Shift",
    "ctrl_alt": "Ctrl+Alt", "alt_shift": "Alt+Shift"
  },
  "capture": {
    "prompt": "Drücke jetzt die gewünschte Taste/Kombo…",
    "cancel_hint": "(Esc = Abbrechen)"
  }
}
```

- [ ] **Step 4: `locales/en.json` analog erweitern**

Gleiche Struktur, übersetzte Texte:

```json
"settings": {
  "title": "VOCIX — Settings",
  "tab": { "basics": "Basics", "advanced": "Advanced", "expert": "Expert" },
  "button": {
    "ok": "OK", "cancel": "Cancel", "apply": "Apply",
    "test": "Test", "browse": "Browse…", "other_key": "Other key…",
    "reset": "Reset to factory defaults",
    "open_config_dir": "Open config directory"
  },
  "field": {
    "input_language": "Input language",
    "output_language": "Output language",
    "whisper_model": "Whisper model",
    "acceleration": "Acceleration",
    "api_key": "Anthropic API key",
    "default_mode": "Default startup mode",
    "hotkey_record": "Record hotkey (push-to-talk)",
    "hotkey_mode_a": "Hotkey Clean mode",
    "hotkey_mode_b": "Hotkey Business mode",
    "hotkey_mode_c": "Hotkey Rage mode",
    "model_dir": "Model directory",
    "log_file": "Log file",
    "log_level": "Log level",
    "overlay_seconds": "Overlay display time (s)",
    "rdp_mode": "Remote desktop mode",
    "clipboard_delay": "Clipboard delay (s)",
    "paste_delay": "Paste delay (s)",
    "silence_threshold": "Silence threshold",
    "min_duration": "Minimum recording duration (s)",
    "whisper_language_override": "Whisper language override",
    "sample_rate": "Sample rate",
    "anthropic_model": "Anthropic model ID",
    "anthropic_timeout": "Anthropic timeout (s)"
  },
  "tooltip": {
    "input_language": "Language you speak in — passed to Whisper.",
    "output_language": "What gets pasted: original language or translated to English.",
    "whisper_model": "Larger model = better quality, more RAM, slower.",
    "acceleration": "GPU requires CUDA libraries (source setup only).",
    "api_key": "Required for Business and Rage modes. Test sends a short ping.",
    "default_mode": "Mode VOCIX starts with. Business/Rage require a valid API key.",
    "hotkey_record": "Single key — push-to-talk needs hold-capable keys (e.g. Pause, F9).",
    "rdp_mode": "Extends clipboard and paste delays for remote desktop sessions.",
    "silence_threshold": "RMS value below which audio counts as silence. Higher = trim more aggressively.",
    "sample_rate": "Whisper expects 16000 Hz — other values are experimental."
  },
  "help": {
    "whisper_model": {
      "title": "Whisper models compared",
      "body": "tiny ~75 MB, very fast, low accuracy\nbase ~150 MB, fast\nsmall ~500 MB, balanced (default)\nmedium ~1.5 GB, high accuracy\nlarge-v3 ~3 GB, highest accuracy, slow\nlarge-v3-turbo ~1.6 GB, near large-v3 quality at half the latency"
    },
    "acceleration": {
      "title": "Hardware acceleration",
      "body": "Auto: uses GPU when available, otherwise CPU.\nGPU: forces CUDA — requires nvidia-cublas + nvidia-cudnn (source setup only, not bundled in the ZIP).\nCPU: forces CPU. Always works, slower."
    },
    "api_key": {
      "title": "Anthropic API key",
      "body": "Required for Business and Rage modes. Get a key at https://console.anthropic.com. Not required if you only use Clean mode."
    },
    "rdp_mode": {
      "title": "Remote desktop mode",
      "body": "Enables extended clipboard and paste delays because RDP must sync the clipboard between host and client. Recommended: on when using VOCIX over RDP."
    },
    "silence_threshold": {
      "title": "Silence threshold",
      "body": "Determines the RMS level at which audio counts as silence. Higher values trim more aggressively. Default 0.01 works in most environments; raise it in noisy rooms."
    },
    "sample_rate": {
      "title": "Sample rate",
      "body": "Whisper models are trained at 16 kHz. Other sample rates get resampled internally — only change this if you know exactly what you're doing."
    },
    "whisper_language_override": {
      "title": "Whisper language override",
      "body": "Normally Whisper uses your input language. You can force a different language here (e.g. speak German but transcribe as French). \"auto\" = follow input language."
    },
    "anthropic_model": {
      "title": "Anthropic model ID",
      "body": "claude-sonnet-4-6 — fast, good for Business/Rage (default).\nclaude-opus-4-7 — highest quality, slower, more expensive.\nclaude-haiku-4-5-20251001 — very fast, cheap, simple rephrasing."
    }
  },
  "status": {
    "api_valid": "✓ API key valid",
    "api_invalid": "✗ Invalid",
    "api_unchecked": "– Not tested",
    "api_locked": "Set API key in Basics to unlock Claude options."
  },
  "error": {
    "duplicate_hotkey": "This hotkey is already in use.",
    "ptt_combo_not_allowed": "Push-to-talk requires a single key.",
    "path_missing": "Path does not exist."
  },
  "confirm": {
    "factory_reset": "Really reset all settings to factory defaults?"
  },
  "lang": { "de": "German", "en": "English", "other": "Other…" },
  "output": { "input_lang": "Same as input", "english": "English" },
  "modifier": {
    "none": "(none)", "ctrl": "Ctrl", "ctrl_shift": "Ctrl+Shift",
    "ctrl_alt": "Ctrl+Alt", "alt_shift": "Alt+Shift"
  },
  "capture": {
    "prompt": "Press the desired key/combo now…",
    "cancel_hint": "(Esc = cancel)"
  }
}
```

- [ ] **Step 5: Tests grün**

Run: `python -m pytest tests/test_i18n_settings.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add locales/de.json locales/en.json tests/test_i18n_settings.py
git commit -m "i18n: settings.* keys für DE/EN"
```

---

## Task 3: Tooltip-Helper

**Files:**
- Create: `vocix/ui/tooltip.py`
- Test: `tests/ui/test_tooltip.py`, `tests/ui/__init__.py`

- [ ] **Step 1: Test schreiben**

`tests/ui/__init__.py` (leer).

`tests/ui/test_tooltip.py`:

```python
import tkinter as tk

import pytest

from vocix.ui.tooltip import Tooltip


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("Kein Display verfügbar")
    r.withdraw()
    yield r
    r.destroy()


def test_tooltip_shows_after_delay(root):
    label = tk.Label(root, text="hover me")
    label.pack()
    tip = Tooltip(label, text_provider=lambda: "Hilfetext")
    tip._show()  # Delay umgehen
    assert tip._tip_window is not None
    assert tip._tip_window.winfo_exists()
    tip._hide()
    assert tip._tip_window is None


def test_tooltip_hide_destroys_window(root):
    label = tk.Label(root)
    tip = Tooltip(label, text_provider=lambda: "x")
    tip._show()
    tw = tip._tip_window
    tip._hide()
    assert not tw.winfo_exists()


def test_tooltip_uses_provider_each_time(root):
    label = tk.Label(root)
    calls = {"n": 0}

    def provider():
        calls["n"] += 1
        return f"call {calls['n']}"

    tip = Tooltip(label, text_provider=provider)
    tip._show()
    text1 = tip._label.cget("text")
    tip._hide()
    tip._show()
    text2 = tip._label.cget("text")
    assert text1 == "call 1"
    assert text2 == "call 2"
```

- [ ] **Step 2: Test laufen, FAIL erwarten**

Run: `python -m pytest tests/ui/test_tooltip.py -v`
Expected: FAIL — `vocix.ui.tooltip` existiert nicht.

- [ ] **Step 3: Implementation**

`vocix/ui/tooltip.py`:

```python
"""Tooltip-Helper für tkinter-Widgets.

Zeigt nach 600 ms Maus-Stillstand ein Toplevel ohne Border mit gelbem
Hintergrund neben dem Cursor. Verschwindet bei <Leave> oder <ButtonPress>.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

_DELAY_MS = 600
_BG = "#ffffe0"
_FG = "#000000"
_BORDER = "#888888"


class Tooltip:
    def __init__(self, widget: tk.Widget, text_provider: Callable[[], str]):
        self._widget = widget
        self._provider = text_provider
        self._after_id: str | None = None
        self._tip_window: tk.Toplevel | None = None
        self._label: tk.Label | None = None

        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self._after_id = self._widget.after(_DELAY_MS, self._show)

    def _cancel(self) -> None:
        if self._after_id is not None:
            try:
                self._widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _show(self) -> None:
        if self._tip_window is not None:
            return
        text = self._provider()
        if not text:
            return
        x = self._widget.winfo_rootx() + 16
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(bg=_BORDER)
        self._label = tk.Label(
            tw, text=text, justify="left", background=_BG, foreground=_FG,
            relief="flat", borderwidth=0, padx=8, pady=4, wraplength=360,
        )
        self._label.pack(padx=1, pady=1)
        self._tip_window = tw

    def _hide(self) -> None:
        if self._tip_window is not None:
            try:
                self._tip_window.destroy()
            except tk.TclError:
                pass
            self._tip_window = None
            self._label = None

    def _on_leave(self, _event=None) -> None:
        self._cancel()
        self._hide()
```

- [ ] **Step 4: Test grün**

Run: `python -m pytest tests/ui/test_tooltip.py -v`
Expected: PASS (oder SKIPPED, wenn Display fehlt — auf CI Linux ohne Xvfb).

- [ ] **Step 5: Commit**

```bash
git add vocix/ui/tooltip.py tests/ui/test_tooltip.py tests/ui/__init__.py
git commit -m "ui: Tooltip-Helper mit verzögerter Anzeige"
```

---

## Task 4: Hilfe-Popup mit ?-Button

**Files:**
- Create: `vocix/ui/help_popup.py`
- Test: `tests/ui/test_help_popup.py`

- [ ] **Step 1: Test schreiben**

`tests/ui/test_help_popup.py`:

```python
import tkinter as tk

import pytest

from vocix.ui.help_popup import HelpButton, show_help


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("Kein Display verfügbar")
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
```

- [ ] **Step 2: Test laufen, FAIL erwarten**

Run: `python -m pytest tests/ui/test_help_popup.py -v`

- [ ] **Step 3: Implementation**

`vocix/ui/help_popup.py`:

```python
"""Modales Hilfe-Popup, geöffnet über einen kleinen ?-Button neben einem Feld."""

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
    """?-Button rechts neben einem Feld."""

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
```

- [ ] **Step 4: Test grün**

Run: `python -m pytest tests/ui/test_help_popup.py -v`

- [ ] **Step 5: Commit**

```bash
git add vocix/ui/help_popup.py tests/ui/test_help_popup.py
git commit -m "ui: HelpButton mit modalem ?-Popup"
```

---

## Task 5: Hotkey-Capture-Modal

**Files:**
- Create: `vocix/ui/hotkey_capture.py`
- Test: `tests/ui/test_hotkey_capture.py`

- [ ] **Step 1: Test schreiben**

`tests/ui/test_hotkey_capture.py`:

```python
import tkinter as tk

import pytest

from vocix.ui.hotkey_capture import keysym_to_hotkey, format_hotkey


def test_keysym_to_hotkey_single_key():
    assert keysym_to_hotkey("Pause", set()) == "pause"
    assert keysym_to_hotkey("F9", set()) == "f9"
    assert keysym_to_hotkey("Scroll_Lock", set()) == "scroll lock"


def test_keysym_to_hotkey_with_modifiers():
    assert keysym_to_hotkey("1", {"ctrl", "shift"}) == "ctrl+shift+1"
    assert keysym_to_hotkey("F4", {"alt"}) == "alt+f4"


def test_keysym_to_hotkey_ignores_pure_modifier():
    assert keysym_to_hotkey("Control_L", set()) is None
    assert keysym_to_hotkey("Shift_R", set()) is None


def test_format_hotkey_human_readable():
    assert format_hotkey("ctrl+shift+1") == "Ctrl+Shift+1"
    assert format_hotkey("pause") == "Pause"
    assert format_hotkey("scroll lock") == "Scroll Lock"
```

- [ ] **Step 2: Test FAIL**

Run: `python -m pytest tests/ui/test_hotkey_capture.py -v`

- [ ] **Step 3: Implementation**

`vocix/ui/hotkey_capture.py`:

```python
"""Modal zum Erfassen eines Hotkeys per Tastendruck.

Gibt einen Hotkey-String im Format der `keyboard`-Library zurück
("pause", "f9", "ctrl+shift+1"). Modifier-only-Tasten werden
ignoriert (warten bis eine echte Taste folgt).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from vocix.i18n import t


_MODIFIER_KEYSYMS = {
    "Control_L", "Control_R", "Shift_L", "Shift_R",
    "Alt_L", "Alt_R", "Meta_L", "Meta_R", "Super_L", "Super_R",
}

# tk-keysym → keyboard-library-name (wo es abweicht)
_KEYSYM_MAP = {
    "Pause": "pause",
    "Scroll_Lock": "scroll lock",
    "Caps_Lock": "caps lock",
    "Insert": "insert", "Delete": "delete",
    "Home": "home", "End": "end",
    "Prior": "page up", "Next": "page down",
    "Up": "up", "Down": "down", "Left": "left", "Right": "right",
    "Return": "enter", "BackSpace": "backspace", "Tab": "tab",
    "space": "space",
    "App": "apps",
}


def keysym_to_hotkey(keysym: str, modifiers: set[str]) -> str | None:
    if keysym in _MODIFIER_KEYSYMS:
        return None
    if keysym.startswith("F") and keysym[1:].isdigit():
        key = keysym.lower()
    elif keysym in _KEYSYM_MAP:
        key = _KEYSYM_MAP[keysym]
    elif len(keysym) == 1:
        key = keysym.lower()
    else:
        key = keysym.lower()

    parts: list[str] = []
    for mod in ("ctrl", "alt", "shift"):
        if mod in modifiers:
            parts.append(mod)
    parts.append(key)
    return "+".join(parts)


def format_hotkey(hk: str) -> str:
    return "+".join(p.capitalize() if p not in ("scroll lock", "caps lock", "page up", "page down") else p.title()
                    for p in hk.split("+"))


class HotkeyCaptureDialog:
    def __init__(self, parent: tk.Misc, *, allow_combos: bool, on_result: Callable[[str | None], None]):
        self._on_result = on_result
        self._allow_combos = allow_combos

        self._win = tk.Toplevel(parent)
        self._win.title(t("settings.button.other_key"))
        self._win.transient(parent.winfo_toplevel())
        self._win.geometry("360x140")
        self._win.resizable(False, False)
        self._win.grab_set()
        self._win.focus_force()

        ttk.Label(self._win, text=t("settings.capture.prompt"),
                  font=("", 11)).pack(pady=(20, 4))
        ttk.Label(self._win, text=t("settings.capture.cancel_hint"),
                  foreground="#666").pack()

        self._error_var = tk.StringVar()
        ttk.Label(self._win, textvariable=self._error_var,
                  foreground="#c0392b").pack(pady=(8, 0))

        self._win.bind("<Key>", self._on_key)
        self._win.bind("<Escape>", lambda _e: self._finish(None))
        self._win.protocol("WM_DELETE_WINDOW", lambda: self._finish(None))

    def _on_key(self, event) -> None:
        if event.keysym == "Escape":
            return
        modifiers: set[str] = set()
        if event.state & 0x0004:
            modifiers.add("ctrl")
        if event.state & 0x0001:
            modifiers.add("shift")
        if event.state & 0x0008 or event.state & 0x0080:
            modifiers.add("alt")

        hk = keysym_to_hotkey(event.keysym, modifiers)
        if hk is None:
            return  # warte auf nicht-Modifier-Taste

        if not self._allow_combos and "+" in hk:
            self._error_var.set(t("settings.error.ptt_combo_not_allowed"))
            return

        self._finish(hk)

    def _finish(self, result: str | None) -> None:
        self._on_result(result)
        try:
            self._win.grab_release()
            self._win.destroy()
        except tk.TclError:
            pass
```

- [ ] **Step 4: Test grün**

Run: `python -m pytest tests/ui/test_hotkey_capture.py -v`

- [ ] **Step 5: Commit**

```bash
git add vocix/ui/hotkey_capture.py tests/ui/test_hotkey_capture.py
git commit -m "ui: Hotkey-Capture-Modal mit PTT-Kombo-Validierung"
```

---

## Task 6: SettingsDialog-Skeleton (Toplevel + Notebook + Buttons)

**Files:**
- Create: `vocix/ui/settings.py`
- Test: `tests/ui/test_settings.py`

In dieser Task baue nur die äußere Hülle: Toplevel, drei leere Tabs, OK/Cancel/Apply-Buttons. Tab-Inhalte folgen in Tasks 7–9.

- [ ] **Step 1: Test schreiben**

`tests/ui/test_settings.py`:

```python
import tkinter as tk
from dataclasses import replace

import pytest

from vocix.config import Config
from vocix.ui.settings import SettingsDialog


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("Kein Display verfügbar")
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def base_config():
    return Config(language="de", whisper_model="small", whisper_acceleration="auto")


def test_dialog_opens_with_three_tabs(root, base_config):
    dlg = SettingsDialog(root, config=base_config, on_apply=lambda c: None)
    assert dlg.notebook is not None
    assert len(dlg.notebook.tabs()) == 3
    dlg.destroy()


def test_dialog_cancel_calls_no_apply(root, base_config):
    called = {"n": 0}
    dlg = SettingsDialog(root, config=base_config, on_apply=lambda c: called.update(n=called["n"] + 1))
    dlg._on_cancel()
    assert called["n"] == 0


def test_dialog_apply_calls_callback_with_config_copy(root, base_config):
    received = []
    dlg = SettingsDialog(root, config=base_config, on_apply=lambda c: received.append(c))
    dlg._on_apply()
    assert len(received) == 1
    assert received[0] is not base_config  # Kopie, nicht Original
    assert received[0].language == "de"
```

- [ ] **Step 2: Test FAIL**

- [ ] **Step 3: Implementation (Skeleton)**

`vocix/ui/settings.py`:

```python
"""Zentraler Einstellungsdialog für VOCIX.

Drei Tabs (Basics/Erweitert/Expert) mit allen Config-Feldern. Schreibt
nach state.json über VocixApp.apply_settings, das die Reload-Schritte
(Whisper, Hotkeys, i18n, Tray) orchestriert.
"""

from __future__ import annotations

import logging
import tkinter as tk
from dataclasses import replace
from tkinter import ttk
from typing import Callable

from vocix.config import Config
from vocix.i18n import t

logger = logging.getLogger(__name__)


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
        self._win.transient(parent.winfo_toplevel())
        self._win.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self._win.grab_set()

        self.notebook = ttk.Notebook(self._win)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        self._tab_basics = ttk.Frame(self.notebook, padding=12)
        self._tab_advanced = ttk.Frame(self.notebook, padding=12)
        self._tab_expert = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self._tab_basics, text=t("settings.tab.basics"))
        self.notebook.add(self._tab_advanced, text=t("settings.tab.advanced"))
        self.notebook.add(self._tab_expert, text=t("settings.tab.expert"))

        self._build_basics(self._tab_basics)
        self._build_advanced(self._tab_advanced)
        self._build_expert(self._tab_expert)

        self._error_var = tk.StringVar()
        ttk.Label(self._win, textvariable=self._error_var, foreground="#c0392b").pack(
            anchor="w", padx=12
        )

        btn_bar = ttk.Frame(self._win)
        btn_bar.pack(fill="x", padx=10, pady=10)
        ttk.Button(btn_bar, text=t("settings.button.ok"), command=self._on_ok).pack(side="right", padx=4)
        ttk.Button(btn_bar, text=t("settings.button.cancel"), command=self._on_cancel).pack(side="right", padx=4)
        self._apply_btn = ttk.Button(btn_bar, text=t("settings.button.apply"), command=self._on_apply)
        self._apply_btn.pack(side="right", padx=4)

    # Tab-Builder — werden in den nächsten Tasks gefüllt
    def _build_basics(self, frame: ttk.Frame) -> None:
        pass

    def _build_advanced(self, frame: ttk.Frame) -> None:
        pass

    def _build_expert(self, frame: ttk.Frame) -> None:
        pass

    def _validate(self) -> bool:
        """Hooks für Hotkey-Konflikte etc. — befüllt in Task 13."""
        self._error_var.set("")
        return True

    def _on_apply(self) -> None:
        if not self._validate():
            return
        self._on_apply_cb(replace(self._draft))

    def _on_ok(self) -> None:
        if not self._validate():
            return
        self._on_apply_cb(replace(self._draft))
        self.destroy()

    def _on_cancel(self) -> None:
        self.destroy()

    def destroy(self) -> None:
        try:
            self._win.grab_release()
            self._win.destroy()
        except tk.TclError:
            pass
```

- [ ] **Step 4: Test grün**

Run: `python -m pytest tests/ui/test_settings.py -v`

- [ ] **Step 5: Commit**

```bash
git add vocix/ui/settings.py tests/ui/test_settings.py
git commit -m "ui(settings): Skeleton mit Notebook und OK/Cancel/Apply-Buttons"
```

---

## Task 7: Tab Basics

**Files:**
- Modify: `vocix/ui/settings.py`
- Modify: `tests/ui/test_settings.py`

Befülle `_build_basics` mit allen Feldern aus dem Spec.

- [ ] **Step 1: Tests schreiben**

In `tests/ui/test_settings.py` ergänzen:

```python
def test_basics_initial_values_match_config(root):
    cfg = Config(language="en", whisper_model="medium", whisper_acceleration="cpu",
                 default_mode="clean", anthropic_api_key="")
    dlg = SettingsDialog(root, config=cfg, on_apply=lambda c: None)
    assert dlg._var_input_lang.get() == "en"
    assert dlg._var_whisper_model.get() == "medium"
    assert dlg._var_acceleration.get() == "cpu"
    dlg.destroy()


def test_basics_default_mode_only_clean_when_no_valid_key(root):
    cfg = Config(anthropic_api_key="")
    dlg = SettingsDialog(root, config=cfg, on_apply=lambda c: None)
    values = dlg._mode_combo["values"]
    assert tuple(values) == ("clean",)
    dlg.destroy()


def test_basics_changing_input_lang_updates_draft(root, base_config):
    dlg = SettingsDialog(root, config=base_config, on_apply=lambda c: None)
    dlg._var_input_lang.set("en")
    dlg._on_input_lang_changed()
    assert dlg._draft.language == "en"
    dlg.destroy()
```

- [ ] **Step 2: Test FAIL**

- [ ] **Step 3: Implementation**

In `vocix/ui/settings.py` `_build_basics` ersetzen:

```python
    def _build_basics(self, frame: ttk.Frame) -> None:
        from vocix.ui.tooltip import Tooltip
        from vocix.ui.help_popup import HelpButton
        from vocix.ui.hotkey_capture import HotkeyCaptureDialog, format_hotkey
        from vocix.stt.whisper_stt import cuda_available

        for col, weight in ((0, 0), (1, 1), (2, 0), (3, 0)):
            frame.columnconfigure(col, weight=weight)

        row = 0

        # Eingabesprache
        ttk.Label(frame, text=t("settings.field.input_language")).grid(row=row, column=0, sticky="w", pady=4)
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
        Tooltip(frame.grid_slaves(row=row, column=0)[0],
                lambda: t("settings.tooltip.input_language"))
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
                       lambda _e: self._draft.__setattr__("translate_to_english",
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
                lambda _e: self._draft.__setattr__("whisper_model", self._var_whisper_model.get()))
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
                                  command=lambda: self._draft.__setattr__(
                                      "whisper_acceleration", self._var_acceleration.get()))
            rb.pack(side="left", padx=4)
            if value == "gpu" and not gpu_ok:
                rb.state(["disabled"])
        Tooltip(accel_frame, lambda: t("settings.tooltip.acceleration"))
        HelpButton(frame,
                   title_provider=lambda: t("settings.help.acceleration.title"),
                   body_provider=lambda: t("settings.help.acceleration.body")
                   ).grid(row=row, column=2, padx=4)
        row += 1

        # API-Key (Maskierung & Test in Task 10)
        ttk.Label(frame, text=t("settings.field.api_key")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_api_key = tk.StringVar(value=self._draft.anthropic_api_key)
        self._api_entry = ttk.Entry(frame, textvariable=self._var_api_key, show="*", width=30)
        self._api_entry.grid(row=row, column=1, sticky="ew")
        ttk.Button(frame, text=t("settings.button.test"), command=self._on_test_api).grid(
            row=row, column=2, padx=4)
        self._var_api_status = tk.StringVar(value=t("settings.status.api_unchecked"))
        ttk.Label(frame, textvariable=self._var_api_status).grid(row=row, column=3, sticky="w")
        Tooltip(self._api_entry, lambda: t("settings.tooltip.api_key"))
        row += 1

        # Default Mode
        ttk.Label(frame, text=t("settings.field.default_mode")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_default_mode = tk.StringVar(value=self._draft.default_mode)
        self._mode_combo = ttk.Combobox(frame, state="readonly", width=24, textvariable=self._var_default_mode)
        self._update_mode_combo_values()
        self._mode_combo.grid(row=row, column=1, sticky="w")
        self._mode_combo.bind("<<ComboboxSelected>>",
                              lambda _e: self._draft.__setattr__("default_mode", self._var_default_mode.get()))
        Tooltip(self._mode_combo, lambda: t("settings.tooltip.default_mode"))
        row += 1

        # Hotkeys
        self._hotkey_vars: dict[str, tk.StringVar] = {}
        self._hotkey_widgets: dict[str, tuple[ttk.Combobox, ttk.Button]] = {}
        for attr, label_key, allow_combo, gated in (
            ("hotkey_record", "settings.field.hotkey_record", False, False),
            ("hotkey_mode_a", "settings.field.hotkey_mode_a", True, False),
            ("hotkey_mode_b", "settings.field.hotkey_mode_b", True, True),
            ("hotkey_mode_c", "settings.field.hotkey_mode_c", True, True),
        ):
            ttk.Label(frame, text=t(label_key)).grid(row=row, column=0, sticky="w", pady=4)
            var = tk.StringVar(value=getattr(self._draft, attr))
            self._hotkey_vars[attr] = var
            picks = ("pause", "scroll lock", "f7", "f8", "f9", "f10", "f11", "f12", "insert", "apps") \
                if not allow_combo else ("ctrl+shift+1", "ctrl+shift+2", "ctrl+shift+3",
                                          "ctrl+alt+1", "ctrl+alt+2", "ctrl+alt+3")
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
            if attr == "hotkey_record":
                Tooltip(cb, lambda: t("settings.tooltip.hotkey_record"))
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
            self._var_input_lang.set("")  # Radios deselektieren

    def _update_mode_combo_values(self) -> None:
        valid = bool(self._draft.anthropic_api_key) and self._key_validated()
        self._mode_combo["values"] = ("clean", "business", "rage") if valid else ("clean",)
        if not valid and self._var_default_mode.get() != "clean":
            self._var_default_mode.set("clean")
            self._draft.default_mode = "clean"

    def _key_validated(self) -> bool:
        from vocix.config import load_state
        return bool(load_state().get("anthropic_key_validated"))

    def _refresh_api_gated_widgets(self) -> None:
        valid = bool(self._draft.anthropic_api_key) and self._key_validated()
        for attr in ("hotkey_mode_b", "hotkey_mode_c"):
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

    def _on_test_api(self) -> None:
        # In Task 10 implementiert
        pass
```

- [ ] **Step 4: Tests grün**

Run: `python -m pytest tests/ui/test_settings.py -v`

- [ ] **Step 5: Commit**

```bash
git add vocix/ui/settings.py tests/ui/test_settings.py
git commit -m "ui(settings): Tab Basics — Sprachen, Modell, Beschleunigung, API-Key, Modus, Hotkeys"
```

---

## Task 8: Tab Erweitert

**Files:**
- Modify: `vocix/ui/settings.py`
- Modify: `tests/ui/test_settings.py`

- [ ] **Step 1: Test schreiben**

```python
def test_advanced_rdp_toggle_disables_delays(root, base_config):
    dlg = SettingsDialog(root, config=base_config, on_apply=lambda c: None)
    dlg._var_rdp.set(True)
    dlg._on_rdp_changed()
    assert "disabled" in dlg._clipboard_spin.state()
    dlg.destroy()


def test_advanced_silence_threshold_round_trip(root, base_config):
    dlg = SettingsDialog(root, config=base_config, on_apply=lambda c: None)
    dlg._var_silence.set(0.05)
    dlg._on_advanced_changed()
    assert dlg._draft.silence_threshold == pytest.approx(0.05)
    dlg.destroy()
```

- [ ] **Step 2: Test FAIL**

- [ ] **Step 3: Implementation**

In `_build_advanced` ergänzen:

```python
    def _build_advanced(self, frame: ttk.Frame) -> None:
        from tkinter import filedialog
        from vocix.ui.tooltip import Tooltip
        from vocix.ui.help_popup import HelpButton

        for col in (1,):
            frame.columnconfigure(col, weight=1)

        row = 0

        def _path_row(label_key, attr, askdir=True):
            nonlocal row
            ttk.Label(frame, text=t(label_key)).grid(row=row, column=0, sticky="w", pady=4)
            var = tk.StringVar(value=getattr(self._draft, attr))
            entry = ttk.Entry(frame, textvariable=var)
            entry.grid(row=row, column=1, sticky="ew")
            entry.bind("<FocusOut>", lambda _e: setattr(self._draft, attr, var.get()))

            def browse():
                if askdir:
                    p = filedialog.askdirectory(initialdir=var.get() or None)
                else:
                    p = filedialog.asksaveasfilename(initialdir=str(getattr(self._draft, attr) or ""))
                if p:
                    var.set(p)
                    setattr(self._draft, attr, p)

            ttk.Button(frame, text=t("settings.button.browse"), command=browse).grid(row=row, column=2, padx=4)
            row += 1
            return var

        self._var_model_dir = _path_row("settings.field.model_dir", "whisper_model_dir", askdir=True)
        self._var_log_file = _path_row("settings.field.log_file", "log_file", askdir=False)

        # Loglevel
        ttk.Label(frame, text=t("settings.field.log_level")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_log_level = tk.StringVar(value=self._draft.log_level)
        cb = ttk.Combobox(frame, state="readonly", width=12, textvariable=self._var_log_level,
                          values=("DEBUG", "INFO", "WARNING", "ERROR"))
        cb.grid(row=row, column=1, sticky="w")
        cb.bind("<<ComboboxSelected>>", lambda _e: setattr(self._draft, "log_level", self._var_log_level.get()))
        row += 1

        # Overlay-Anzeigedauer
        ttk.Label(frame, text=t("settings.field.overlay_seconds")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_overlay = tk.DoubleVar(value=self._draft.overlay_display_seconds)
        sp = ttk.Spinbox(frame, from_=0.5, to=10.0, increment=0.5, width=8,
                         textvariable=self._var_overlay,
                         command=lambda: setattr(self._draft, "overlay_display_seconds", float(self._var_overlay.get())))
        sp.grid(row=row, column=1, sticky="w")
        row += 1

        # RDP-Mode + Delays
        ttk.Label(frame, text=t("settings.field.rdp_mode")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_rdp = tk.BooleanVar(value=self._draft.rdp_mode)
        ttk.Checkbutton(frame, variable=self._var_rdp, command=self._on_rdp_changed).grid(row=row, column=1, sticky="w")
        HelpButton(frame,
                   title_provider=lambda: t("settings.help.rdp_mode.title"),
                   body_provider=lambda: t("settings.help.rdp_mode.body")
                   ).grid(row=row, column=2)
        row += 1

        ttk.Label(frame, text=t("settings.field.clipboard_delay")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_clipboard = tk.DoubleVar(value=self._draft.clipboard_delay)
        self._clipboard_spin = ttk.Spinbox(frame, from_=0.01, to=1.0, increment=0.05, width=8,
                                           textvariable=self._var_clipboard,
                                           command=lambda: setattr(self._draft, "clipboard_delay", float(self._var_clipboard.get())))
        self._clipboard_spin.grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(frame, text=t("settings.field.paste_delay")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_paste = tk.DoubleVar(value=self._draft.paste_delay)
        self._paste_spin = ttk.Spinbox(frame, from_=0.05, to=1.0, increment=0.05, width=8,
                                       textvariable=self._var_paste,
                                       command=lambda: setattr(self._draft, "paste_delay", float(self._var_paste.get())))
        self._paste_spin.grid(row=row, column=1, sticky="w")
        row += 1

        # Audio
        ttk.Label(frame, text=t("settings.field.silence_threshold")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_silence = tk.DoubleVar(value=self._draft.silence_threshold)
        scale = ttk.Scale(frame, from_=0.001, to=0.1, variable=self._var_silence,
                          command=lambda _v: setattr(self._draft, "silence_threshold", float(self._var_silence.get())))
        scale.grid(row=row, column=1, sticky="ew")
        ttk.Label(frame, textvariable=self._var_silence, width=8).grid(row=row, column=2)
        HelpButton(frame,
                   title_provider=lambda: t("settings.help.silence_threshold.title"),
                   body_provider=lambda: t("settings.help.silence_threshold.body")
                   ).grid(row=row, column=3, padx=4)
        row += 1

        ttk.Label(frame, text=t("settings.field.min_duration")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_min_dur = tk.DoubleVar(value=self._draft.min_duration)
        ttk.Spinbox(frame, from_=0.1, to=5.0, increment=0.1, width=8,
                    textvariable=self._var_min_dur,
                    command=lambda: setattr(self._draft, "min_duration", float(self._var_min_dur.get()))
                    ).grid(row=row, column=1, sticky="w")
        row += 1

        self._on_rdp_changed()  # initial-State setzen

    def _on_rdp_changed(self) -> None:
        self._draft.rdp_mode = self._var_rdp.get()
        if self._draft.rdp_mode:
            self._clipboard_spin.state(["disabled"])
            self._paste_spin.state(["disabled"])
        else:
            self._clipboard_spin.state(["!disabled"])
            self._paste_spin.state(["!disabled"])

    def _on_advanced_changed(self) -> None:
        # Sammelhandler für Tests
        self._draft.silence_threshold = float(self._var_silence.get())
```

- [ ] **Step 4: Test grün**

- [ ] **Step 5: Commit**

```bash
git add vocix/ui/settings.py tests/ui/test_settings.py
git commit -m "ui(settings): Tab Erweitert — Pfade, Logging, RDP, Audio"
```

---

## Task 9: Tab Expert

**Files:**
- Modify: `vocix/ui/settings.py`
- Modify: `tests/ui/test_settings.py`

- [ ] **Step 1: Test schreiben**

```python
def test_expert_anthropic_section_hidden_when_key_invalid(root):
    cfg = Config(anthropic_api_key="")
    dlg = SettingsDialog(root, config=cfg, on_apply=lambda c: None)
    assert dlg._anthropic_frame.winfo_ismapped() is False or \
           "disabled" in str(dlg._anthropic_frame.cget("style") or "")
    # Konkreter: das frame sollte nicht im Layout sein
    dlg.destroy()


def test_expert_factory_reset_clears_state(root, base_config, tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text('{"language": "en"}')
    monkeypatch.setattr("vocix.config.STATE_FILE", state_file)
    dlg = SettingsDialog(root, config=base_config, on_apply=lambda c: None)
    monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **k: True)
    dlg._on_factory_reset()
    assert state_file.read_text().strip() in ("{}", '{\n}')
    dlg.destroy()
```

- [ ] **Step 2: Test FAIL**

- [ ] **Step 3: Implementation**

In `_build_expert` ergänzen:

```python
    def _build_expert(self, frame: ttk.Frame) -> None:
        import os
        from tkinter import messagebox
        from vocix.ui.tooltip import Tooltip
        from vocix.ui.help_popup import HelpButton

        for col in (1,):
            frame.columnconfigure(col, weight=1)
        row = 0

        # Whisper-Sprach-Override
        ttk.Label(frame, text=t("settings.field.whisper_language_override")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_whisper_lang = tk.StringVar(value=self._draft.whisper_language_override or "auto")
        cb = ttk.Combobox(frame, state="readonly", width=14, textvariable=self._var_whisper_lang,
                          values=("auto", "de", "en", "fr", "es", "it", "nl", "pl", "pt", "tr", "ru", "ja", "zh"))
        cb.grid(row=row, column=1, sticky="w")
        cb.bind("<<ComboboxSelected>>",
                lambda _e: setattr(self._draft, "whisper_language_override",
                                   "" if self._var_whisper_lang.get() == "auto" else self._var_whisper_lang.get()))
        HelpButton(frame,
                   title_provider=lambda: t("settings.help.whisper_language_override.title"),
                   body_provider=lambda: t("settings.help.whisper_language_override.body")
                   ).grid(row=row, column=2, padx=4)
        row += 1

        # Sample-Rate
        ttk.Label(frame, text=t("settings.field.sample_rate")).grid(row=row, column=0, sticky="w", pady=4)
        self._var_sample_rate = tk.IntVar(value=self._draft.sample_rate)
        cb = ttk.Combobox(frame, state="readonly", width=10, textvariable=self._var_sample_rate,
                          values=(16000, 22050, 44100, 48000))
        cb.grid(row=row, column=1, sticky="w")
        cb.bind("<<ComboboxSelected>>",
                lambda _e: setattr(self._draft, "sample_rate", int(self._var_sample_rate.get())))
        HelpButton(frame,
                   title_provider=lambda: t("settings.help.sample_rate.title"),
                   body_provider=lambda: t("settings.help.sample_rate.body")
                   ).grid(row=row, column=2, padx=4)
        row += 1

        # Anthropic-Bereich
        self._anthropic_frame = ttk.LabelFrame(frame, text="Anthropic", padding=8)
        self._anthropic_locked_label = ttk.Label(frame, text=t("settings.status.api_locked"),
                                                  foreground="#888")

        ttk.Label(self._anthropic_frame, text=t("settings.field.anthropic_model")).grid(row=0, column=0, sticky="w", pady=4)
        self._var_anth_model = tk.StringVar(value=self._draft.anthropic_model)
        cb = ttk.Combobox(self._anthropic_frame, textvariable=self._var_anth_model, width=36,
                          values=("claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5-20251001"))
        cb.grid(row=0, column=1, sticky="w")
        cb.bind("<FocusOut>", lambda _e: setattr(self._draft, "anthropic_model", self._var_anth_model.get().strip()))
        HelpButton(self._anthropic_frame,
                   title_provider=lambda: t("settings.help.anthropic_model.title"),
                   body_provider=lambda: t("settings.help.anthropic_model.body")
                   ).grid(row=0, column=2, padx=4)

        ttk.Label(self._anthropic_frame, text=t("settings.field.anthropic_timeout")).grid(row=1, column=0, sticky="w", pady=4)
        self._var_anth_timeout = tk.DoubleVar(value=self._draft.anthropic_timeout)
        ttk.Spinbox(self._anthropic_frame, from_=5, to=60, increment=1, width=8,
                    textvariable=self._var_anth_timeout,
                    command=lambda: setattr(self._draft, "anthropic_timeout", float(self._var_anth_timeout.get()))
                    ).grid(row=1, column=1, sticky="w")

        self._show_anthropic_section(self._key_validated())
        row += 1

        # Buttons
        ttk.Button(frame, text=t("settings.button.open_config_dir"),
                   command=lambda: os.startfile(self._config_dir())  # type: ignore[attr-defined]
                   ).grid(row=row+2, column=0, sticky="w", pady=(20, 4))
        ttk.Button(frame, text=t("settings.button.reset"), command=self._on_factory_reset).grid(
            row=row+2, column=1, sticky="w", pady=(20, 4))

    def _config_dir(self):
        from vocix.config import STATE_FILE
        return str(STATE_FILE.parent)

    def _show_anthropic_section(self, valid: bool) -> None:
        if valid:
            self._anthropic_locked_label.grid_forget()
            self._anthropic_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(20, 4))
        else:
            self._anthropic_frame.grid_forget()
            self._anthropic_locked_label.grid(row=2, column=0, columnspan=3, sticky="w", pady=(20, 4))

    def _on_factory_reset(self) -> None:
        from tkinter import messagebox
        from vocix.config import save_state
        if not messagebox.askyesno(t("settings.title"), t("settings.confirm.factory_reset")):
            return
        save_state({})
        # Felder neu befüllen
        self._draft = replace(Config())
        # Vereinfachung: Dialog schließen, User soll neu öffnen
        messagebox.showinfo(t("settings.title"), "Bitte Dialog neu öffnen.")
        self._on_cancel()
```

Aufruf von `_show_anthropic_section` und `_refresh_api_gated_widgets` muss nach jedem API-Test auch hier nachziehen — das geschieht in Task 10.

- [ ] **Step 4: Test grün**

- [ ] **Step 5: Commit**

```bash
git add vocix/ui/settings.py tests/ui/test_settings.py
git commit -m "ui(settings): Tab Expert — Whisper-Override, Sample-Rate, Anthropic-Bereich, Reset"
```

---

## Task 10: API-Key-Maskierung & Test-Button

**Files:**
- Modify: `vocix/ui/settings.py`
- Modify: `tests/ui/test_settings.py`

- [ ] **Step 1: Tests schreiben**

```python
def test_api_key_masked_display_for_saved_key(root):
    cfg = Config(anthropic_api_key="sk-ant-abcdefghijklmnopqrstuvwxyz1234")
    dlg = SettingsDialog(root, config=cfg, on_apply=lambda c: None)
    assert dlg._displayed_api_key() == "sk-ant-…1234"
    dlg.destroy()


def test_api_key_test_marks_validated(root, base_config, monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}")
    monkeypatch.setattr("vocix.config.STATE_FILE", state_file)
    dlg = SettingsDialog(root, config=base_config, on_apply=lambda c: None)
    dlg._var_api_key.set("sk-ant-test-XYZ")
    monkeypatch.setattr("vocix.ui.settings._ping_anthropic", lambda key, model, timeout: True)
    dlg._on_test_api()
    import json
    assert json.loads(state_file.read_text())["anthropic_key_validated"] is True
    assert dlg._draft.anthropic_api_key == "sk-ant-test-XYZ"
    dlg.destroy()
```

- [ ] **Step 2: Test FAIL**

- [ ] **Step 3: Implementation**

Oben in `vocix/ui/settings.py` ergänzen:

```python
def _ping_anthropic(api_key: str, model: str, timeout: float) -> bool:
    """Versucht eine kurze Anthropic-Anfrage. True = Key + Modell akzeptiert."""
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key, timeout=timeout)
        client.messages.create(
            model=model, max_tokens=1,
            messages=[{"role": "user", "content": "ok"}],
        )
        return True
    except Exception as e:
        logger.info("Anthropic-Ping fehlgeschlagen: %s", e)
        return False
```

In `SettingsDialog` ergänzen:

```python
    def _displayed_api_key(self) -> str:
        key = self._draft.anthropic_api_key or ""
        if len(key) <= 12:
            return key
        return f"{key[:7]}…{key[-4:]}"

    def _on_test_api(self) -> None:
        from vocix.config import update_state
        key = self._var_api_key.get().strip()
        if not key:
            self._var_api_status.set(t("settings.status.api_invalid"))
            return
        self._var_api_status.set("…")
        self._win.update_idletasks()
        ok = _ping_anthropic(key, self._draft.anthropic_model, self._draft.anthropic_timeout)
        self._draft.anthropic_api_key = key
        with update_state() as s:
            s["anthropic_key_validated"] = ok
        if ok:
            self._var_api_status.set(t("settings.status.api_valid"))
        else:
            self._var_api_status.set(t("settings.status.api_invalid"))
        self._refresh_api_gated_widgets()
        self._show_anthropic_section(ok)
```

Im API-Entry den Display-Wert beim Build setzen (statt direkt `_var_api_key`):

In `_build_basics` an der Stelle des API-Entry den Code ersetzen durch:

```python
        self._var_api_key = tk.StringVar(value=self._displayed_api_key())
        self._api_entry = ttk.Entry(frame, textvariable=self._var_api_key, show="*", width=30)
        self._api_entry.grid(row=row, column=1, sticky="ew")

        def _on_focus_in(_e):
            # Bei Fokus: Volltext zeigen, damit Paste sichtbar ist
            self._var_api_key.set(self._draft.anthropic_api_key or "")
            self._api_entry.config(show="")

        def _on_focus_out(_e):
            new = self._var_api_key.get().strip()
            self._draft.anthropic_api_key = new
            self._var_api_key.set(self._displayed_api_key())
            self._api_entry.config(show="*")

        self._api_entry.bind("<FocusIn>", _on_focus_in)
        self._api_entry.bind("<FocusOut>", _on_focus_out)
```

- [ ] **Step 4: Test grün**

- [ ] **Step 5: Commit**

```bash
git add vocix/ui/settings.py tests/ui/test_settings.py
git commit -m "ui(settings): API-Key-Maskierung sk-ant-…XXXX und Test-Button"
```

---

## Task 11: Validation (Hotkey-Konflikte, leere PTT-Tasten)

**Files:**
- Modify: `vocix/ui/settings.py`
- Modify: `tests/ui/test_settings.py`

- [ ] **Step 1: Tests schreiben**

```python
def test_duplicate_hotkey_blocks_apply(root, base_config):
    received = []
    dlg = SettingsDialog(root, config=base_config, on_apply=lambda c: received.append(c))
    dlg._draft.hotkey_record = "f9"
    dlg._draft.hotkey_mode_a = "f9"
    dlg._on_apply()
    assert received == []
    assert "duplicate" in dlg._error_var.get().lower() or \
           t("settings.error.duplicate_hotkey") in dlg._error_var.get()
    dlg.destroy()


def test_ptt_combo_blocks_apply(root, base_config):
    received = []
    dlg = SettingsDialog(root, config=base_config, on_apply=lambda c: received.append(c))
    dlg._draft.hotkey_record = "ctrl+f9"
    dlg._on_apply()
    assert received == []
    dlg.destroy()
```

- [ ] **Step 2: Test FAIL**

- [ ] **Step 3: `_validate` ausbauen**

```python
    def _validate(self) -> bool:
        self._error_var.set("")
        # PTT keine Kombo
        if "+" in (self._draft.hotkey_record or ""):
            self._error_var.set(t("settings.error.ptt_combo_not_allowed"))
            return False
        # Duplikate
        keys = [
            self._draft.hotkey_record,
            self._draft.hotkey_mode_a,
            self._draft.hotkey_mode_b,
            self._draft.hotkey_mode_c,
        ]
        non_empty = [k for k in keys if k]
        if len(set(non_empty)) != len(non_empty):
            self._error_var.set(t("settings.error.duplicate_hotkey"))
            return False
        return True
```

- [ ] **Step 4: Test grün**

- [ ] **Step 5: Commit**

```bash
git add vocix/ui/settings.py tests/ui/test_settings.py
git commit -m "ui(settings): Validierung — PTT-Kombos und Hotkey-Duplikate blockieren Apply"
```

---

## Task 12: VocixApp.apply_settings + Open-Routing

**Files:**
- Modify: `vocix/main.py`
- Modify: `vocix/ui/overlay.py`
- Test: `tests/test_apply_settings.py`

`apply_settings` soll den Diff orchestrieren. Die Whisper-Reload- und Hotkey-Re-Bind-Pfade existieren bereits in `main.py` — wir bauen sie in eine wiederverwendbare Methode um.

- [ ] **Step 1: Test schreiben**

`tests/test_apply_settings.py`:

```python
import json
from dataclasses import replace
from unittest.mock import MagicMock, patch

from vocix.config import Config
from vocix.main import VocixApp


def test_apply_settings_writes_state(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}")
    monkeypatch.setattr("vocix.config.STATE_FILE", state_file)
    monkeypatch.setattr("vocix.main.WhisperSTT", MagicMock())
    monkeypatch.setattr("vocix.main.keyboard", MagicMock())

    app = VocixApp.__new__(VocixApp)  # ohne __init__ — wir testen nur apply_settings
    app._config = Config(language="de", whisper_model="small")
    app._stt = MagicMock()
    app._stt_reload_lock = MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
    app._tray = MagicMock()
    app._overlay = MagicMock()
    app._rebind_hotkeys = MagicMock()
    app._reload_stt = MagicMock()

    new_cfg = replace(app._config, language="en", whisper_model="medium")
    app.apply_settings(new_cfg)

    saved = json.loads(state_file.read_text())
    assert saved["language"] == "en"
    assert saved["whisper_model"] == "medium"
    app._reload_stt.assert_called_once()
    app._rebind_hotkeys.assert_called_once()
    app._tray.refresh.assert_called_once()
```

- [ ] **Step 2: Test FAIL** (noch keine `apply_settings`-Methode)

- [ ] **Step 3: `apply_settings` in `VocixApp` ergänzen**

In `vocix/main.py` in der Klasse `VocixApp`:

```python
    _STATE_PERSISTED_FIELDS = (
        "language", "whisper_model", "whisper_acceleration", "translate_to_english",
        "default_mode", "hotkey_record", "hotkey_mode_a", "hotkey_mode_b", "hotkey_mode_c",
        "log_level", "log_file", "whisper_model_dir",
        "overlay_display_seconds",
        "rdp_mode", "clipboard_delay", "paste_delay",
        "silence_threshold", "min_duration", "sample_rate",
        "anthropic_api_key", "anthropic_model", "anthropic_timeout",
        "whisper_language_override",
    )

    def apply_settings(self, new_config: "Config") -> None:
        """Übernimmt Änderungen aus dem Settings-Dialog: Persistenz + Reloads."""
        from vocix.config import update_state

        old = self._config

        with update_state() as s:
            for field_name in self._STATE_PERSISTED_FIELDS:
                s[field_name] = getattr(new_config, field_name)

        self._config = new_config

        # i18n
        if old.language != new_config.language:
            i18n.set_language(new_config.language)

        # Whisper-Reload
        if (old.whisper_model != new_config.whisper_model
            or old.whisper_acceleration != new_config.whisper_acceleration
            or old.whisper_model_dir != new_config.whisper_model_dir):
            self._reload_stt()

        # Hotkey-Rebind
        hotkey_fields = ("hotkey_record", "hotkey_mode_a", "hotkey_mode_b", "hotkey_mode_c")
        if any(getattr(old, f) != getattr(new_config, f) for f in hotkey_fields):
            self._rebind_hotkeys()

        # Tray-Refresh (Häkchen)
        if self._tray is not None:
            self._tray.refresh()

        # Overlay-Display-Dauer wirkt automatisch beim nächsten show_temporary

    def open_settings(self) -> None:
        """Wird vom Tray aufgerufen — öffnet den Dialog im Overlay-Thread."""
        if self._overlay is not None:
            self._overlay.show_settings(self._config, self.apply_settings)
```

`_rebind_hotkeys` extrahiert den vorhandenen Hotkey-Setup-Code aus `run()`:

```python
    def _rebind_hotkeys(self) -> None:
        keyboard.unhook_all()
        keyboard.add_hotkey(self._config.hotkey_mode_a, lambda: self._set_mode("clean"))
        keyboard.add_hotkey(self._config.hotkey_mode_b, lambda: self._set_mode("business"))
        keyboard.add_hotkey(self._config.hotkey_mode_c, lambda: self._set_mode("rage"))
        keyboard.on_press_key(self._config.hotkey_record, self._on_record_press, suppress=False)
        keyboard.on_release_key(self._config.hotkey_record, self._on_record_release, suppress=False)
```

(Falls die existierende Logik im `run()`-Block heute anders aussieht, denselben Block aufrufen.)

`TrayApp.refresh()` muss als Methode existieren — falls nicht, einen Stub mit Rebuild des Menüs bauen (siehe Task 13).

- [ ] **Step 4: `StatusOverlay.show_settings` ergänzen**

In `vocix/ui/overlay.py` analog `show_about`:

```python
    def show_settings(self, config, on_apply) -> None:
        self._tk_queue.put(("settings", config, on_apply))

    # In _process_queue dann:
        elif kind == "settings":
            from vocix.ui.settings import SettingsDialog
            _, cfg, cb = item
            if self._settings_dialog and self._settings_dialog._win.winfo_exists():
                self._settings_dialog._win.lift()
                self._settings_dialog._win.focus_force()
            else:
                self._settings_dialog = SettingsDialog(self._root, config=cfg, on_apply=cb)
```

`self._settings_dialog = None` im `__init__` initialisieren.

- [ ] **Step 5: Test grün**

Run: `python -m pytest tests/test_apply_settings.py -v`

- [ ] **Step 6: Commit**

```bash
git add vocix/main.py vocix/ui/overlay.py tests/test_apply_settings.py
git commit -m "main: VocixApp.apply_settings + Settings-Dialog-Routing über Overlay"
```

---

## Task 13: Tray-Menüeintrag „Einstellungen…" + Refresh

**Files:**
- Modify: `vocix/ui/tray.py`
- Modify: `vocix/main.py`
- Test: `tests/ui/test_tray_settings_entry.py`

- [ ] **Step 1: Test**

```python
from unittest.mock import MagicMock

from vocix.ui.tray import TrayApp


def test_tray_calls_open_settings_on_click():
    on_open_settings = MagicMock()
    tray = TrayApp.__new__(TrayApp)
    tray._on_open_settings = on_open_settings
    tray._invoke_open_settings()
    on_open_settings.assert_called_once()
```

- [ ] **Step 2: Test FAIL**

- [ ] **Step 3: TrayApp erweitern**

In `TrayApp.__init__` Parameter `on_open_settings: Callable[[], None]` hinzufügen, im Menü ergänzen:

```python
MenuItem(t("tray.settings"), self._invoke_open_settings),
```

(neuer i18n-Key `tray.settings` = „Einstellungen…" / „Settings…" — in Task 2 mit aufnehmen, oder hier nachziehen).

```python
    def _invoke_open_settings(self) -> None:
        if self._on_open_settings:
            self._on_open_settings()

    def refresh(self) -> None:
        """Baut das Menü neu auf, damit Häkchen den aktuellen State spiegeln."""
        self._icon.menu = self._build_menu()
        self._icon.update_menu()
```

(`_build_menu` aus dem existierenden Konstruktor-Code extrahieren.)

In `VocixApp.__init__` beim TrayApp-Construct den neuen Callback übergeben:

```python
self._tray = TrayApp(..., on_open_settings=self.open_settings)
```

- [ ] **Step 4: Test grün**

- [ ] **Step 5: Commit**

```bash
git add vocix/ui/tray.py vocix/main.py tests/ui/test_tray_settings_entry.py
git commit -m "tray: Menüeintrag Einstellungen… öffnet SettingsDialog"
```

---

## Task 14: Manueller Smoke-Test + README/Changelog

**Files:**
- Modify: `vocix/__init__.py` (Versions-Bump)
- Modify: `README.md`
- Create: `.docs/release-v1.4.0-beta.1.md`

- [ ] **Step 1: Versions-Bump auf `1.4.0-beta.1`**

`vocix/__init__.py`:

```python
__version__ = "1.4.0-beta.1"
```

- [ ] **Step 2: `python -m vocix.main` starten und manuell prüfen**

Checkliste:
- Tray-Menü zeigt „Einstellungen…"
- Klick öffnet Dialog mit drei Tabs
- Eingabesprache umschalten → bei OK zeigt UI sofort die andere Sprache
- Whisper-Modell ändern → Reload-Toast erscheint, Modell wird geladen
- API-Key eingeben + Test → Status grün, Anthropic-Sektion in Expert wird sichtbar, Modus-Picker zeigt Business/Rage
- Hotkey-Capture „Andere Taste…" funktioniert für PTT (lehnt Kombo ab) und Modus-Hotkeys (akzeptiert Kombo)
- OK schließt Dialog, zweiter Klick auf „Einstellungen…" öffnet frischen Dialog
- Cancel verwirft Änderungen
- Factory-Reset löscht state.json, fordert Re-Open

- [ ] **Step 3: Release-Body anlegen** (`.docs/release-v1.4.0-beta.1.md`, zweisprachig EN/DE — Template `release-v1.1.0.md` als Vorlage)

- [ ] **Step 4: README ergänzen**

Im Konfigurationsteil hinzufügen: „Ab v1.4.0 lassen sich alle Einstellungen über das Tray-Menü → Einstellungen… (alternativ Settings…) bearbeiten. `.env` bleibt als Override-Mechanismus erhalten."

- [ ] **Step 5: Tests gesamt grün**

Run: `python -m pytest tests/ -q`

- [ ] **Step 6: Commit**

```bash
git add vocix/__init__.py README.md .docs/release-v1.4.0-beta.1.md
git commit -m "release: v1.4.0-beta.1 — Settings-Dialog"
```

- [ ] **Step 7: Pre-Release auf GitHub** (manuell, **nicht** Manifeste anfassen)

```bash
git tag v1.4.0-beta.1 && git push origin main --tags
rm -rf build dist
pyinstaller vocix.spec --noconfirm
cp .env.example dist/VOCIX/.env.example
cd dist && python -c "import shutil; shutil.make_archive('VOCIX-v1.4.0-beta.1-win-x64', 'zip', '.', 'VOCIX')" && cd ..
gh release create v1.4.0-beta.1 dist/VOCIX-v1.4.0-beta.1-win-x64.zip \
  --repo RTF22/VOCIX \
  --prerelease \
  --title "VOCIX v1.4.0-beta.1" \
  --notes-file .docs/release-v1.4.0-beta.1.md
```

**Wichtig:** Beta-Release, daher `--prerelease`. `packaging/winget/*` und `packaging/scoop/*` werden **nicht** angefasst, damit der laufende winget-Review von v1.3.5 nicht gefährdet ist.

---

## Done

Settings-Dialog vollständig: drei Tabs, alle Felder, Persistenz nach `state.json`, Tooltips, ?-Hilfe, Hotkey-Capture, API-Key-Maskierung + Test, Tray-Integration, Apply-Orchestrierung, Validierung, Tests. Pre-Release v1.4.0-beta.1 auf GitHub, ohne winget/Scoop zu berühren.
