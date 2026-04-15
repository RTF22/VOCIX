# DICTUM — DICtation with Text Understanding & Modification

Lokale Sprachdiktion-App für Windows 11 mit globalem Hotkey. Sprache aufnehmen, transkribieren, intelligent transformieren und systemweit an der Cursorposition einfügen — in jeder Anwendung (Browser, Word, Outlook, IDEs, etc.).

## Features

- **Push-to-Talk** per globalem Hotkey (`Ctrl+Shift+Space`)
- **Drei Modi:**
  - **A — Clean:** Saubere Transkription, entfernt Füllwörter (äh, ähm, also, ...), leichte Korrektur
  - **B — Business:** Wandelt Sprache in professionelle Geschäftssprache um (Claude API)
  - **C — Rage:** Deeskaliert aggressive Sprache in höfliche Formulierungen (Claude API)
- **System Tray** mit farbcodiertem Icon und Moduswechsel
- **Status-Overlay** zeigt Aufnahme-/Verarbeitungsstatus
- **Lokale Verarbeitung** — Speech-to-Text läuft vollständig offline (faster-whisper)

## Voraussetzungen

- Windows 10/11
- Python 3.10 oder höher
- Mikrofon
- Optional: [Anthropic API-Key](https://console.anthropic.com/) für Modus B und C

## Installation

### 1. Repository klonen oder herunterladen

```bash
git clone https://github.com/RTF22/DICTUM.git
cd DICTUM
```

### 2. Virtuelle Umgebung erstellen (empfohlen)

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Dependencies installieren

```bash
pip install -r requirements.txt
```

> Beim ersten Start wird das Whisper-Modell automatisch heruntergeladen (~500 MB für `small`). Dies passiert nur einmalig.

### 4. API-Key konfigurieren (optional)

Für Modus B (Business) und C (Rage) wird ein Anthropic API-Key benötigt. Ohne Key fallen beide Modi automatisch auf Modus A (Clean) zurück.

```bash
copy .env.example .env
```

Dann `.env` öffnen und den Key eintragen:

```
ANTHROPIC_API_KEY=sk-ant-dein-key-hier
```

## Starten

```bash
python -m textme.main
```

Die App startet im System Tray (Infobereich der Taskleiste). Ein farbiges Icon zeigt den aktuellen Modus an.

> **Hinweis:** Für Hotkey-Erkennung in Anwendungen mit erhöhten Rechten (z.B. Task-Manager) muss DICTUM ebenfalls als Administrator gestartet werden.

## Bedienung

| Tastenkombination | Aktion |
|---|---|
| `Ctrl+Shift+Space` (halten) | Push-to-Talk — sprechen, loslassen zum Verarbeiten |
| `Ctrl+Shift+1` | Modus A: Clean Transcription |
| `Ctrl+Shift+2` | Modus B: Business Mode |
| `Ctrl+Shift+3` | Modus C: Rage Mode |

**Ablauf:**
1. Cursor in das Zielfeld setzen (z.B. E-Mail, Chat, Texteditor)
2. `Ctrl+Shift+Space` gedrückt halten und sprechen
3. Loslassen — der Text wird transkribiert, transformiert und automatisch eingefügt

## Beenden

Rechtsklick auf das Tray-Icon → **Beenden**

## Fehlerbehebung

| Problem | Lösung |
|---|---|
| Kein Tray-Icon sichtbar | Versteckte Symbole in der Taskleiste prüfen (Pfeil nach oben) |
| Hotkey reagiert nicht | App als Administrator starten |
| „Mikrofon nicht verfügbar" | Mikrofon in Windows-Einstellungen prüfen, Zugriff erlauben |
| Modus B/C liefern nur Clean-Ergebnis | `ANTHROPIC_API_KEY` in `.env` prüfen |
| Whisper-Download schlägt fehl | Internetverbindung prüfen, Proxy/Firewall ggf. konfigurieren |
| Text enthält falsche Zeichen | Sicherstellen, dass die Zielanwendung Ctrl+V / Einfügen unterstützt |

## Projektstruktur

```
textme/
├── main.py              # Entry Point
├── config.py            # Einstellungen
├── audio/recorder.py    # Mikrofon-Aufnahme
├── stt/
│   ├── base.py          # STT-Schnittstelle
│   └── whisper_stt.py   # faster-whisper
├── processing/
│   ├── base.py          # Prozessor-Schnittstelle
│   ├── clean.py         # Modus A (lokal)
│   ├── business.py      # Modus B (Claude API)
│   └── rage.py          # Modus C (Claude API)
├── output/injector.py   # Texteinfügung
└── ui/
    ├── tray.py          # System Tray
    └── overlay.py       # Status-Overlay
```

## Lizenz

Privates Projekt.
