# Changelog

Alle wesentlichen Änderungen an DICTUM werden in dieser Datei dokumentiert.

## [0.4.0] — 2026-04-16

### Hinzugefügt
- **Portable .exe Build** via PyInstaller (`build_exe.bat`)
- PyInstaller Spec-Datei (`dictum.spec`) mit allen Dependencies
- Whisper-Modelle werden im portablen `models/`-Ordner gespeichert
- `APP_DIR`-Erkennung: funktioniert als Script und als frozen .exe

## [0.3.0] — 2026-04-16

### Geändert
- **Standard-Hotkey** für Push-to-Talk auf `Rechte Strg-Taste` geändert

### Hinzugefügt
- **Konfigurierbare Hotkeys** via `.env`-Variablen (`DICTUM_HOTKEY_RECORD`, `DICTUM_HOTKEY_MODE_A/B/C`)
- Unterstützung für Einzeltasten (`right ctrl`, `f9`) und Kombinationen (`ctrl+shift+space`)
- Automatische Erkennung ob Einzeltaste oder Kombination

## [0.2.0] — 2026-04-15

### Hinzugefügt
- **RDP-Modus** (`DICTUM_RDP_MODE=true`) mit konfigurierbaren Clipboard-Delays
- Automatische Delay-Anpassung für Remote-Desktop-Sessions (0.2s/0.4s statt 0.05s/0.1s)

## [0.1.0] — 2026-04-15

### Initiales Release
- **Speech-to-Text** mit faster-whisper (Modell "small", offline, deutsch)
- **Drei Textmodi:**
  - Modus A (Clean): Füllwörter entfernen, Grammatik-/Rechtschreibkorrektur (lokal, regex-basiert)
  - Modus B (Business): Professionelle Geschäftssprache (Claude API)
  - Modus C (Rage): Deeskalation aggressiver Sprache (Claude API)
- **Push-to-Talk** per globalem Hotkey
- **Systemweite Texteinfügung** via Clipboard + Ctrl+V (funktioniert in allen Windows-Apps)
- **System Tray** mit farbcodiertem Mikrofon-Icon (Grün/Blau/Rot)
- **Status-Overlay** (tkinter): Aufnahme → Verarbeitung → Eingefügt
- **Moduswechsel** per Hotkey (Ctrl+Shift+1/2/3) oder Tray-Menü
- **Automatischer Fallback** von Modus B/C auf A wenn kein API-Key vorhanden
- Stille-Erkennung und Mindestaufnahmelänge
- Fehlerbehandlung bei fehlendem Mikrofon
