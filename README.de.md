**🌐 [English](README.md) · [Deutsch](README.de.md)**

<p align="center">
  <a href="https://vocix.de/">
    <img src="https://img.shields.io/badge/%F0%9F%8C%90_Landing_Page-vocix.de-1a3d8f?style=for-the-badge" alt="VOCIX Landing Page">
  </a>
</p>

# VOCIX — Voice Capture & Intelligent eXpression

![Release](https://img.shields.io/github/v/release/RTF22/VOCIX)
![Downloads](https://img.shields.io/github/downloads/RTF22/VOCIX/total)
![License](https://img.shields.io/github/license/RTF22/VOCIX)
![Platform](https://img.shields.io/badge/platform-Windows-blue)

Lokale Sprachdiktion-App für Windows 11 mit globalem Hotkey. Sprache aufnehmen, transkribieren, intelligent transformieren und systemweit an der Cursorposition einfügen — in jeder Anwendung (Browser, Word, Outlook, IDEs, etc.).

## Features

- **Push-to-Talk** per globalem Hotkey (Standard: `Pause`)
- **Drei Modi:**
  - **A — Clean:** Saubere Transkription, entfernt Füllwörter (äh, ähm, also, ...), leichte Korrektur
  - **B — Business:** Wandelt Sprache in professionelle Geschäftssprache um (LLM-gestützt)
  - **C — Rage:** Deeskaliert aggressive Sprache in höfliche Formulierungen (LLM-gestützt)
- **Multi-Provider-LLM für Modi B und C** — Backend frei wählbar im Einstellungsdialog: Anthropic Claude, jede OpenAI-kompatible API (OpenAI, Groq, OpenRouter, LM Studio, llama.cpp-Server, vLLM via `base_url`) oder lokale Ollama-Modelle. Per-Mode-Override (z. B. Business über Cloud-Claude, Rage über lokales Llama). Provider-Fehler fallen auf Clean-Modus zurück und zeigen einen orangenen Toast — kein stiller Fallback mehr.
- **Einstellungsdialog** im Tray-Menü — vier Tabs (Basics / Erweitert / Expert / KI-Provider) mit Test-Buttons, Hotkey-Capture und Validierung pro Modus. Änderungen folgen einem strikten Entwurfsmodell: nichts wird wirksam, bevor du **Speichern** drückst, **Abbrechen** verwirft alles. Fast jede Einstellung greift sofort; nur Log-Level / Log-Datei erfordern einen Neustart (es wird nachgefragt, und VOCIX startet sich bei Bestätigung selbst neu)
- **System Tray** mit farbcodiertem Mikrofon-Icon und Moduswechsel
- **Status-Overlay** mit Live-VU-Meter während der Aufnahme — sofortiges visuelles Feedback, dass das Mikrofon Pegel sieht
- **Verlauf der letzten 20 Diktate** im Tray — Klick auf einen Eintrag fügt ihn erneut ein (rettet Text, wenn das Zielfenster gewechselt wurde)
- **Nutzungsstatistik** — Wörter pro Tag/Woche/Gesamt, geschätzte gesparte Tippzeit (200 Anschläge/Min), Verteilung über die Modi
- **Snippet-Expansion** — eigene Kürzel (`/sig`, `/adr`, …) im Diktat werden vor dem Einfügen durch Volltext ersetzt; Whisper-Transkripte wie „Schrägstrich Sig" werden automatisch normalisiert
- **Auto-Update aus dem Tray** — neue Releases werden im Hintergrund erkannt; ein Klick lädt das Win-x64-ZIP, prüft den SHA256 und tauscht die Dateien automatisch aus
- **Lokale Verarbeitung** — Speech-to-Text läuft vollständig offline (faster-whisper)
- **Konfigurierbares Whisper-Modell** — `tiny` / `base` / `small` (Standard) / `medium` / `large-v3` / `large-v3-turbo` zur Laufzeit über das Tray-Menü umschaltbar (größer = genauer, langsamer)
- **Optionale NVIDIA-GPU-Beschleunigung** — erkennt CUDA automatisch, fällt sonst auf CPU zurück; im Tray-Menü umschaltbar (`Auto` / `GPU` / `CPU`). Nur in der Source-Installation verfügbar (das gepackte ZIP bleibt CPU-only)
- **Optionale Offline-Übersetzung ins Englische** — Tray-Toggle: in einer der ~50 von Whisper unterstützten Sprachen sprechen und VOCIX fügt sauberen englischen Text an der Cursorposition ein, komplett offline (kein API-Key nötig)
- **Konfigurierbare Hotkeys** via `.env`
- **RDP-Modus** für Remote-Desktop-Sessions
- **Logfile** mit konfigurierbarem Log-Level
- **Portable .exe** — kein Python nötig

## Voraussetzungen

- Windows 10/11
- Mikrofon
- Optional für Modus B und C: einer von
  - [Anthropic API-Key](https://console.anthropic.com/), oder
  - OpenAI-kompatibler Endpoint (OpenAI, Groq, OpenRouter, LM Studio, llama.cpp-Server, vLLM …), oder
  - lokales [Ollama](https://ollama.com/) — kein API-Key nötig

## Installation

### Option A: winget

```powershell
winget install RTF22.VOCIX
```

### Option B: Scoop

```powershell
scoop bucket add vocix https://github.com/RTF22/scoop-vocix
scoop install vocix
```

### Option C: Portable .exe

1. [Release herunterladen](https://github.com/RTF22/VOCIX/releases)
2. Ordner an beliebigen Ort entpacken
3. Optional: `.env.example` zu `.env` umbenennen und API-Key eintragen
4. `VOCIX.exe` starten

Das Whisper-Modell (~500 MB) wird beim ersten Start automatisch in den `models/`-Unterordner heruntergeladen.

### Option D: Aus Quellcode

```bash
git clone https://github.com/RTF22/VOCIX.git
cd VOCIX
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m vocix.main
```

### GPU-Beschleunigung (optional, nur NVIDIA)

```bash
pip install -r requirements-gpu.txt
```

Lädt cuBLAS + cuDNN (~600 MB) und ermöglicht `ctranslate2` die GPU-Nutzung.
Anschließend im Tray-Menü **Beschleunigung → GPU (CUDA)** wählen (oder
`VOCIX_WHISPER_ACCELERATION=gpu` setzen). Das gepackte Win-x64-ZIP enthält
diese Bibliotheken **nicht** — GPU ist opt-in für Source-Installationen.

### .exe selbst bauen

```bash
pip install pyinstaller
build_exe.bat
```

Ergebnis liegt in `dist\VOCIX\` — der gesamte Ordner ist portabel.

## Konfiguration

Empfohlener Weg: **Einstellungsdialog** (Tray-Icon → Einstellungen…). Der Tab `KI-Provider` hat drei Slots — Anthropic, OpenAI-kompatibel und Ollama — jeweils mit eigenem Test-Button. Default wählen und optional pro Modus (Business / Rage) überschreiben. Nichts wird geschrieben, bevor du **Speichern** drückst — **Abbrechen** verwirft jede Änderung, auch Provider-Test-Ergebnisse.

Für Headless-Setups stehen alle Werte zusätzlich in der `.env` zur Verfügung:

```ini
# --- LLM-Provider (Modus B und C) ----------------------------------------
# Default-Provider und optionaler Per-Mode-Override.
VOCIX_LLM_DEFAULT=anthropic            # anthropic | openai | ollama
VOCIX_LLM_BUSINESS=                    # leer = Default verwenden
VOCIX_LLM_RAGE=

# Anthropic Claude
VOCIX_LLM_ANTHROPIC_API_KEY=sk-ant-dein-key-hier
VOCIX_LLM_ANTHROPIC_MODEL=claude-sonnet-4-6
VOCIX_LLM_ANTHROPIC_TIMEOUT=15

# OpenAI-kompatibel (OpenAI, Groq, OpenRouter, LM Studio, llama.cpp, vLLM …)
VOCIX_LLM_OPENAI_API_KEY=
VOCIX_LLM_OPENAI_BASE_URL=https://api.openai.com/v1
VOCIX_LLM_OPENAI_MODEL=gpt-4o-mini
VOCIX_LLM_OPENAI_TIMEOUT=15

# Ollama (lokal, kein API-Key)
VOCIX_LLM_OLLAMA_BASE_URL=http://localhost:11434
VOCIX_LLM_OLLAMA_MODEL=llama3.1
VOCIX_LLM_OLLAMA_TIMEOUT=30

# --- App ------------------------------------------------------------------
# Sprache — steuert UI, LLM-Prompts und Whisper-STT (de, en)
# Tray-Auswahl (in state.json) überschreibt diesen Wert.
VOCIX_LANGUAGE=de

# Whisper-Modell — tiny | base | small (Standard) | medium | large-v3 | large-v3-turbo
# Tray-Auswahl (state.json) überschreibt diesen Wert.
VOCIX_WHISPER_MODEL=small

# Beschleunigung — auto (GPU wenn verfügbar) | gpu (CUDA erzwingen) | cpu (CPU erzwingen)
# GPU-Modus erfordert `pip install -r requirements-gpu.txt` (nur Source-Install).
VOCIX_WHISPER_ACCELERATION=auto

# Hotkeys — Push-to-Talk benötigt eine Einzeltaste, Moduswechsel dürfen Kombos sein
VOCIX_HOTKEY_RECORD=pause
VOCIX_HOTKEY_MODE_A=ctrl+shift+1
VOCIX_HOTKEY_MODE_B=ctrl+shift+2
VOCIX_HOTKEY_MODE_C=ctrl+shift+3

# Logging (DEBUG, INFO, WARNING, ERROR)
VOCIX_LOG_LEVEL=INFO
VOCIX_LOG_FILE=vocix.log

# RDP-Modus (längere Clipboard-Delays)
VOCIX_RDP_MODE=true
```

Ohne konfigurierten Provider fallen Modus B und C automatisch auf Modus A (Clean) zurück. Konfigurationen aus VOCIX 1.3.x (`ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_TIMEOUT`) laufen unverändert weiter — einmal im neuen Tab speichern migriert sie.

**Env-Priorität:** Variablen, die bereits in der Prozess-Umgebung gesetzt sind, überschreiben Werte aus der `.env` nicht (Standard-Verhalten von `python-dotenv`). Wer einen Wert temporär überschreiben möchte, exportiert ihn vor dem Start der App.

## Bedienung

| Tastenkombination | Aktion |
|---|---|
| `Pause` (halten) | Push-to-Talk — sprechen, loslassen zum Verarbeiten |
| `Ctrl+Shift+1` | Modus A: Clean Transcription |
| `Ctrl+Shift+2` | Modus B: Business Mode |
| `Ctrl+Shift+3` | Modus C: Rage Mode |

**Ablauf:**
1. Cursor in das Zielfeld setzen (z.B. E-Mail, Chat, Texteditor)
2. `Pause` gedrückt halten und sprechen
3. Loslassen — der Text wird transkribiert, transformiert und automatisch eingefügt

**Tray-Menü:** Rechtsklick auf das Tray-Icon → Moduswechsel, **Sprache / Language** (Deutsch / English — schaltet UI, Claude-Prompts und Whisper-STT), **Whisper-Modell** (`tiny` … `large-v3-turbo` zur Laufzeit), **Beschleunigung** (Auto / GPU / CPU — GPU ist ausgegraut, wenn kein CUDA erkannt wird), **Info** (About + Repo-Link), **Beenden**

> Hinweis: Tray-Auswahlen (Modus, Sprache, Whisper-Modell, Beschleunigung) werden in `state.json` persistiert und überschreiben die entsprechenden `.env`-Werte beim nächsten Start.

## Fehlerbehebung

| Problem | Lösung |
|---|---|
| SmartScreen: „Windows hat Ihren PC geschützt" beim ersten Start | Auf **Weitere Informationen → Trotzdem ausführen** klicken. VOCIX ist Open Source, das Release-ZIP ist aus `main` per `build_exe.bat` reproduzierbar. Code-Signatur wird in [#12](https://github.com/RTF22/VOCIX/issues/12) verfolgt. |
| Kein Tray-Icon sichtbar | Versteckte Symbole in der Taskleiste prüfen (Pfeil nach oben) |
| „VOCIX erfordert eine CPU mit AVX-Unterstützung" beim Start | CPU ist älter als ~2012 und kann CTranslate2 nicht ausführen. VOCIX läuft auf dieser Maschine nicht. |
| Hotkey reagiert nicht | App als Administrator starten |
| Laptop ohne `Pause`-Taste | `VOCIX_HOTKEY_RECORD=scroll lock` (oder `f7`) in `.env` setzen |
| „Mikrofon nicht verfügbar" | Mikrofon in Windows-Einstellungen prüfen, Zugriff erlauben |
| Modus B/C liefern nur Clean-Ergebnis | Einstellungen → KI-Provider öffnen, mindestens einen Slot konfigurieren und „Test" drücken |
| Whisper-Download schlägt fehl | Internetverbindung prüfen, Proxy/Firewall ggf. konfigurieren |
| Text enthält falsche Zeichen | Sicherstellen, dass die Zielanwendung Ctrl+V / Einfügen unterstützt |
| RDP: Text wird nicht eingefügt | `VOCIX_RDP_MODE=true` in `.env` setzen |

## Projektstruktur

```
vocix/
├── main.py              # Entry Point, Orchestrierung
├── config.py            # Einstellungen (.env, Pfade, Hotkeys)
├── audio/recorder.py    # Mikrofon-Aufnahme (sounddevice)
├── stt/
│   ├── base.py          # Abstrakte STT-Schnittstelle
│   └── whisper_stt.py   # faster-whisper Implementierung
├── processing/
│   ├── base.py          # Abstrakte Prozessor-Schnittstelle
│   ├── clean.py         # Modus A: Füllwörter + Korrektur (lokal)
│   ├── llm_backed.py    # Gemeinsamer LLM-gestützter Prozessor (B/C)
│   ├── business.py      # Modus B: Geschäftssprache
│   ├── rage.py          # Modus C: Deeskalation
│   └── providers/       # Anthropic / OpenAI-kompatibel / Ollama Backends
├── output/injector.py   # Clipboard-basierte Texteinfügung
└── ui/
    ├── tray.py          # System Tray mit Mikrofon-Icon
    ├── overlay.py       # Status-Overlay (tkinter)
    └── settings.py      # Einstellungsdialog (Basics / Erweitert / Expert / KI-Provider)
```

## Lizenz

[MIT License](LICENSE) — frei nutzbar, auch kommerziell. Keine Gewährleistung.

VOCIX bündelt in der portablen Distribution Python-Bibliotheken von Drittanbietern.
Die erforderlichen Copyright- und Lizenzhinweise (MIT / BSD / HPND / LGPL-3.0) stehen
in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
