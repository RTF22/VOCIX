# DICTUM — DICtation with Text Understanding & Modification

Lokale Sprachdiktion-App für Windows 11 mit globalem Hotkey. Sprache aufnehmen, transkribieren, intelligent transformieren und systemweit an der Cursorposition einfügen — in jeder Anwendung (Browser, Word, Outlook, IDEs, etc.).

## Features

- **Push-to-Talk** per globalem Hotkey (Standard: `Rechte Strg-Taste`)
- **Drei Modi:**
  - **A — Clean:** Saubere Transkription, entfernt Füllwörter (äh, ähm, also, ...), leichte Korrektur
  - **B — Business:** Wandelt Sprache in professionelle Geschäftssprache um (Claude API)
  - **C — Rage:** Deeskaliert aggressive Sprache in höfliche Formulierungen (Claude API)
- **System Tray** mit farbcodiertem Mikrofon-Icon und Moduswechsel
- **Status-Overlay** zeigt Aufnahme-/Verarbeitungsstatus
- **Lokale Verarbeitung** — Speech-to-Text läuft vollständig offline (faster-whisper)
- **Konfigurierbare Hotkeys** via `.env`
- **RDP-Modus** für Remote-Desktop-Sessions
- **Portable .exe** — kein Python nötig

## Voraussetzungen

- Windows 10/11
- Mikrofon
- Optional: [Anthropic API-Key](https://console.anthropic.com/) für Modus B und C

## Installation

### Option A: Portable .exe (empfohlen)

1. [Release herunterladen](https://github.com/RTF22/DICTUM/releases) oder selbst bauen (siehe unten)
2. Ordner an beliebigen Ort entpacken
3. Optional: `.env.example` zu `.env` umbenennen und API-Key eintragen
4. `DICTUM.exe` starten

Das Whisper-Modell (~500 MB) wird beim ersten Start automatisch in den `models/`-Unterordner heruntergeladen.

### Option B: Aus Quellcode

```bash
git clone https://github.com/RTF22/DICTUM.git
cd DICTUM
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m textme.main
```

### .exe selbst bauen

```bash
pip install pyinstaller
build_exe.bat
```

Ergebnis liegt in `dist\DICTUM\` — der gesamte Ordner ist portabel.

## Konfiguration

Alle Einstellungen werden über die `.env`-Datei im Anwendungsverzeichnis gesteuert:

```ini
# Anthropic API-Key (optional, für Modus B und C)
ANTHROPIC_API_KEY=sk-ant-dein-key-hier

# Hotkeys — Einzeltaste oder Kombination
DICTUM_HOTKEY_RECORD=right ctrl
DICTUM_HOTKEY_MODE_A=ctrl+shift+1
DICTUM_HOTKEY_MODE_B=ctrl+shift+2
DICTUM_HOTKEY_MODE_C=ctrl+shift+3

# RDP-Modus (längere Clipboard-Delays)
DICTUM_RDP_MODE=true
```

Ohne API-Key fallen Modus B und C automatisch auf Modus A (Clean) zurück.

## Bedienung

| Tastenkombination | Aktion |
|---|---|
| `Rechte Strg` (halten) | Push-to-Talk — sprechen, loslassen zum Verarbeiten |
| `Ctrl+Shift+1` | Modus A: Clean Transcription |
| `Ctrl+Shift+2` | Modus B: Business Mode |
| `Ctrl+Shift+3` | Modus C: Rage Mode |

**Ablauf:**
1. Cursor in das Zielfeld setzen (z.B. E-Mail, Chat, Texteditor)
2. Rechte Strg-Taste gedrückt halten und sprechen
3. Loslassen — der Text wird transkribiert, transformiert und automatisch eingefügt

**Beenden:** Rechtsklick auf das Tray-Icon → **Beenden**

## Fehlerbehebung

| Problem | Lösung |
|---|---|
| Kein Tray-Icon sichtbar | Versteckte Symbole in der Taskleiste prüfen (Pfeil nach oben) |
| Hotkey reagiert nicht | App als Administrator starten |
| „Mikrofon nicht verfügbar" | Mikrofon in Windows-Einstellungen prüfen, Zugriff erlauben |
| Modus B/C liefern nur Clean-Ergebnis | `ANTHROPIC_API_KEY` in `.env` prüfen |
| Whisper-Download schlägt fehl | Internetverbindung prüfen, Proxy/Firewall ggf. konfigurieren |
| Text enthält falsche Zeichen | Sicherstellen, dass die Zielanwendung Ctrl+V / Einfügen unterstützt |
| RDP: Text wird nicht eingefügt | `DICTUM_RDP_MODE=true` in `.env` setzen |

## Projektstruktur

```
textme/
├── main.py              # Entry Point, Orchestrierung
├── config.py            # Einstellungen (.env, Pfade, Hotkeys)
├── audio/recorder.py    # Mikrofon-Aufnahme (sounddevice)
├── stt/
│   ├── base.py          # Abstrakte STT-Schnittstelle
│   └── whisper_stt.py   # faster-whisper Implementierung
├── processing/
│   ├── base.py          # Abstrakte Prozessor-Schnittstelle
│   ├── clean.py         # Modus A: Füllwörter + Korrektur (lokal)
│   ├── business.py      # Modus B: Geschäftssprache (Claude API)
│   └── rage.py          # Modus C: Deeskalation (Claude API)
├── output/injector.py   # Clipboard-basierte Texteinfügung
└── ui/
    ├── tray.py          # System Tray mit Mikrofon-Icon
    └── overlay.py       # Status-Overlay (tkinter)
```

## Lizenz

[MIT License](LICENSE) — frei nutzbar, auch kommerziell. Keine Gewährleistung.
