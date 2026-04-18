# Architektur

## Überblick

VOCIX ist eine modulare Sprachdiktion-App für Windows. Die Architektur folgt dem Prinzip austauschbarer Komponenten über abstrakte Basisklassen.

## Datenfluss

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Hotkey     │────>│   Audio     │────>│    STT       │────>│  Processor   │
│  (keyboard)  │     │  Recorder   │     │  (Whisper)   │     │  (A/B/C)     │
└─────────────┘     └─────────────┘     └──────────────┘     └──────┬───────┘
                                                                     │
                    ┌─────────────┐     ┌──────────────┐            │
                    │   Overlay   │<────│  Injector    │<───────────┘
                    │  (Status)   │     │ (Clipboard)  │
                    └─────────────┘     └──────────────┘
```

1. **Hotkey gedrückt** → `AudioRecorder.start()` — Mikrofon-Stream in Buffer
2. **Hotkey losgelassen** → `AudioRecorder.stop()` → numpy float32 array (16kHz mono)
3. **STT** → `WhisperSTT.transcribe(audio)` → Rohtext
4. **Transformation** → `Processor.process(text)` → je nach Modus
5. **Einfügung** → `TextInjector.inject(text)` → Clipboard → Ctrl+V → Clipboard-Restore

Die Pipeline (Schritte 2–5) läuft in einem separaten Thread, damit der Hotkey-Handler nicht blockiert.

## Modulstruktur

### audio/recorder.py
- `sounddevice.InputStream` mit Callback in Buffer
- Stille-Erkennung (RMS-Threshold) und Mindestlänge
- Thread-safe via `threading.Lock`

### stt/base.py + stt/whisper_stt.py
- Abstrakte Basisklasse `STTEngine` mit `transcribe(audio) -> str`
- `WhisperSTT`: CTranslate2-Backend, Modell wird beim Init vorgeladen
- `download_root` zeigt auf portablen `models/`-Ordner
- **VAD (Voice Activity Detection):** faster-whisper nutzt intern Silero VAD (`silero_vad_v6.onnx`), ein kompaktes ONNX-Neuronales-Netz, um Sprachsegmente im Audio zu erkennen. Dies dient zwei Zwecken:
  1. **Stille überspringen:** Pausen und Hintergrundgeräusche werden vor der Transkription herausgefiltert, was die Genauigkeit und Geschwindigkeit deutlich verbessert.
  2. **Segmentierung:** Lange Aufnahmen werden in sinnvolle Abschnitte zerlegt, die Whisper einzeln transkribiert.
  Die VAD-Datei wird im PyInstaller-Build explizit mitgebundelt (`vocix.spec` → `datas`).

### processing/base.py + clean.py / business.py / rage.py
- Abstrakte Basisklasse `TextProcessor` mit `process(text) -> str`
- **Clean (Modus A):** Rein lokal, regex-basiert. Entfernt deutsche Füllwörter, normalisiert Leerzeichen/Satzzeichen.
- **Business (Modus B):** Claude API mit System-Prompt für formelle Geschäftssprache. Fallback auf Clean.
- **Rage (Modus C):** Claude API mit System-Prompt für Deeskalation. Fallback auf Clean.

### output/injector.py
- Clipboard-Methode: Sichern → Kopieren → Ctrl+V → Wiederherstellen
- Konfigurierbare Delays für RDP-Kompatibilität
- Einzige Methode die Umlaute/Sonderzeichen in allen Windows-Apps unterstützt

### ui/tray.py
- pystray mit Pillow-generiertem Mikrofon-Icon
- Farbcodierung: Grün (Clean), Blau (Business), Rot (Rage)
- Menü: Moduswechsel, Info (About-Dialog mit Repo-Link), Beenden

### ui/overlay.py
- tkinter Toplevel in eigenem Thread mit eigener Mainloop
- Thread-safe Updates über `root.after()`
- Always-on-top, halbtransparent, oben rechts

### config.py
- Zentrale Konfiguration als Dataclass
- Lädt `.env` relativ zum Anwendungsverzeichnis
- `APP_DIR` funktioniert als Script und als frozen .exe (PyInstaller)
- RDP-Modus passt Delays automatisch an

### Logging (in main.py konfiguriert)
- Dual-Output: Console (`stdout`) + Logfile (`vocix.log`)
- `RotatingFileHandler`: max 5 MB pro Datei, 3 Backup-Dateien
- Level konfigurierbar via `VOCIX_LOG_LEVEL` in `.env`
- Pipeline-Log zeigt den vollständigen Ablauf: Hotkey → Audiodauer → Rohtext → Ergebnis → Einfügung

## Erweiterbarkeit

### Neuen Modus hinzufügen
1. Neue Klasse in `processing/` erstellen, von `TextProcessor` erben
2. `name` Property und `process()` implementieren
3. In `main.py` → `self._processors` dict registrieren
4. Optional: Hotkey in `config.py` hinzufügen

### Neue STT-Engine
1. Neue Klasse in `stt/` erstellen, von `STTEngine` erben
2. `transcribe()` implementieren
3. In `main.py` statt `WhisperSTT` instanziieren

## Technologie-Entscheidungen

| Entscheidung | Begründung |
|---|---|
| Clipboard + Ctrl+V statt pyautogui.write() | Einzige Methode die Umlaute in allen Apps unterstützt |
| faster-whisper statt OpenAI whisper | 4× schneller durch CTranslate2-Backend |
| Claude API für Modus B/C | Semantische Umformulierung erfordert LLM; lokale Modelle für Deutsch nicht ausreichend |
| keyboard statt pynput | Systemweite Hotkeys, einfache API für Press/Release-Events |
| tkinter statt Qt/wxPython | Keine Zusatzdependency, reicht für ein einfaches Overlay |
