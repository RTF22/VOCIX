# Changelog

Alle wesentlichen Änderungen an DICTUM werden in dieser Datei dokumentiert.

## [0.8.1] — 2026-04-18

### Geändert
- **Package umbenannt** von `textme/` zu `dictum/` — Arbeitstitel ist vollständig durch das finale Akronym DICTUM ersetzt. Entry-Point ist jetzt `python -m dictum.main`. Siehe ADR 008.

### Behoben
- **Race-Condition im Push-to-Talk-Flow** — `_processing`-Flag wird jetzt thread-safe über ein `threading.Lock` geschützt, außerdem direkt im Stop-Handler gesetzt (Issue #1)
- **Moduswechsel während laufender Pipeline** — der aktive Modus wird beim Aufnahme-Ende eingefroren und an den Worker-Thread übergeben (Issue #2)
- **Key-Repeat flutete Logs und Overlay** — Windows' kontinuierliches `on_press_key` wird jetzt verworfen, solange der Recorder bereits läuft (Issue #3)
- **Tray-Icon blieb nach dem Beenden sichtbar** — `os._exit(0)` durch regulären `sys.exit(0)` ersetzt, Tray und tkinter-Thread bekommen Zeit zum Aufräumen (Issue #6)
- **Audio-Stream-Ressourcen bei Fehler** — Stream wird jetzt in `try/finally` geschlossen, der Sounddevice-Callback ignoriert Events nach Stop (Issue #7)
- **Pipeline hing bei Netzwerkausfall** — Anthropic-Client nutzt jetzt einen konfigurierbaren Timeout (`anthropic_timeout`, Default 15 s) und fällt auf Clean zurück (Issue #8)
- **Clean-Prozessor hinterließ führende Kommas** — Regex-Pass für stray Punctuation und doppelte Kommas; Mehrwort-Phrasen werden vor Einzelwörtern gematcht (Issue #9)

## [0.8.0] — 2026-04-16

### Geändert
- **Standard-Hotkey auf `F9`** — "right ctrl" funktionierte unter Windows nicht zuverlässig
- **Hotkey-Logik vereinfacht** — komplexen `keyboard.hook()`-Workaround entfernt, zurück auf einfaches `on_press_key`/`on_release_key`

### Behoben
- **Whisper-Modell nicht mehr im Release-ZIP** — wird wie vorgesehen beim ersten Start heruntergeladen (ZIP: 110 MB statt 536 MB)

## [0.6.0] — 2026-04-16

### Behoben
- **App beendet sich jetzt korrekt** über Tray → Beenden (Prozess lief zuvor im Hintergrund weiter)
- **VAD-Modell** (`silero_vad_v6.onnx`) wird in der .exe mitgeliefert — behebt ONNXRuntimeError beim Transkribieren

### Hinzugefügt
- **Logfile** (`dictum.log`) mit Rotation (5 MB, 3 Backups) — parallel zur Konsolenausgabe
- **Konfigurierbares Log-Level** via `DICTUM_LOG_LEVEL` in `.env` (DEBUG, INFO, WARNING, ERROR)
- **Detaillierte Pipeline-Logs:** Hotkey-Events, Audiodauer, Rohtext, Ergebnistext
- **Startup-Banner** zeigt beim Start die aktive Konfiguration (Hotkey, Modus, API-Key-Status, RDP)
- **Info-Dialog** im Tray-Menü mit Versionsnummer und Link zum GitHub-Repository

## [0.5.0] — 2026-04-16

### Hinzugefügt
- **MIT License** — Open-Source-Lizenz mit Haftungsausschluss

## [0.4.0] — 2026-04-16

### Hinzugefügt
- **Portable .exe Build** via PyInstaller (`build_exe.bat`)
- PyInstaller Spec-Datei (`dictum.spec`) mit allen Dependencies
- Whisper-Modelle werden im portablen `models/`-Ordner gespeichert
- `APP_DIR`-Erkennung: funktioniert als Script und als frozen .exe

## [0.3.0] — 2026-04-16

### Hinzugefügt
- **Konfigurierbare Hotkeys** via `.env`-Variablen (`DICTUM_HOTKEY_RECORD`, `DICTUM_HOTKEY_MODE_A/B/C`)
- Unterstützung für Einzeltasten (`f9`, `pause`, `scroll lock`) und Kombinationen (`ctrl+shift+space`)
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
