# Technische Entscheidungen

Dokumentation der wichtigsten Design- und Technologieentscheidungen mit Begründung.

---

## 001 — Clipboard-basierte Texteinfügung (2026-04-15)

**Kontext:** Text muss systemweit an der Cursorposition eingefügt werden — in beliebigen Anwendungen (Browser, Office, IDEs, Terminal).

**Entscheidung:** Clipboard-Methode (Zwischenablage sichern → Text kopieren → Ctrl+V senden → Zwischenablage wiederherstellen).

**Alternativen verworfen:**
- `pyautogui.write()` — Scheitert an Umlauten (ä, ö, ü, ß) und Sonderzeichen. Sendet einzelne Tastenanschläge, extrem langsam bei langen Texten.
- Windows `SendInput` API direkt — siehe Recherche-Update 2026-04-18 unten für detaillierte Begründung.

**Tradeoff:** Kurzzeitige Unterbrechung der Zwischenablage des Nutzers (wird nach ~200ms wiederhergestellt). **Grenze:** Nur Text-Inhalte werden wiederhergestellt. Liegt beim Aufnahmestart ein Bild, eine Datei oder ein anderes Nicht-Text-Format in der Zwischenablage, erkennt `TextInjector` das per `IsClipboardFormatAvailable(CF_UNICODETEXT)`, loggt eine Warnung und überspringt den Restore. Der eingefügte Text bleibt in der Zwischenablage — besser, als den ursprünglichen Nicht-Text-Inhalt durch einen leeren String aktiv zu zerstören (Issue #5). Eine vollständige Multi-Format-Sicherung via `OpenClipboard`/`EnumClipboardFormats` wurde gegen den Implementierungsaufwand verworfen.

### Recherche-Update 2026-04-18

Erneute Prüfung, ob die Clipboard-Methode durch eine direkte Schreibmethode ersetzt werden sollte, die weder die Zwischenablage berührt noch Ctrl+V simuliert. Ergebnis: **Keine Alternative ist universell besser** — die Clipboard-Methode bleibt.

| Methode | Unicode/Umlaute | App-Kompatibilität | Geschwindigkeit | Hauptproblem |
|---------|-----------------|--------------------|-----------------| -------------|
| Clipboard + Ctrl+V (aktuell) | alle | nahezu alle | schnell (1 Paste) | berührt Zwischenablage kurzzeitig |
| `SendInput` + `KEYEVENTF_UNICODE` | alle | nicht in DirectX-Games, nicht in UAC-elevated Fenstern | zeichenweise, spürbar langsamer bei langen Texten | OS-Buffering-Bug, 5000-Zeichen-Limit |
| `WM_CHAR` via `SendMessage` | alle | stark appabhängig | schnell | moderne TSF-basierte Eingabefelder ignorieren WM_CHAR |
| UI Automation `TextPattern` | alle | nur wenn App TextPattern vollständig implementiert | langsam (Element-Lookup pro Insert) | Electron/Web-Apps oft unvollständig |

**`SendInput` mit `KEYEVENTF_UNICODE`:** Kann Umlaute — der alte Hinweis "gleiche Unicode-Probleme" war fachlich ungenau. Echte Einschränkungen: (a) scheitert in DirectX-Spielen, die Input auf Scancode-Ebene erwarten, (b) scheitert in UAC-elevated Fenstern, wenn VOCIX selbst nicht elevated läuft, (c) sendet Zeichen einzeln → bei 2000 Zeichen deutlich langsamer als ein Clipboard-Paste, (d) dokumentierter OS-Buffering-Bug: bei Unicode-Eingaben wird u.U. nur das erste Zeichen verarbeitet bis Tastatur/Maus bewegt wird, (e) harter 5000-Zeichen-Limit der API.

**`WM_CHAR` via `SendMessage`:** Offiziell durch das Text Services Framework (TSF) ersetzt. Chrome, Electron-Apps, moderne Office-Versionen und alles, was TSF-Eingabefelder nutzt, ignorieren `WM_CHAR` teilweise oder vollständig. Zusätzlich: benötigt Focus-Tracking und Handle-Auflösung pro Insert.

**UI Automation `TextPattern`:** Offizielle moderne API, theoretisch der sauberste Weg. In der Praxis müssen Anwendungen das `TextPattern`-Interface vollständig implementieren — Electron-Apps, Browser-Textfelder und viele Non-Standard-Controls tun das unvollständig oder gar nicht. Zusätzlich erfordert jede Einfügung ein Element-Lookup über den UIA-Tree, was die Latenz gegenüber einem Clipboard-Paste deutlich erhöht.

**Fazit:** Die Clipboard-Berührung ist der einzige Nachteil der aktuellen Lösung und wird durch Sicherung + Wiederherstellung innerhalb ~200ms abgefedert. Alle Alternativen tauschen diesen einen Nachteil gegen schlechtere App-Kompatibilität und/oder schlechtere Performance bei langen Texten ein. Entscheidung: unverändert beibehalten.

---

## 002 — Claude API für Modus B und C (2026-04-15)

**Kontext:** Modus B (Business) und C (Rage) erfordern semantisches Sprachverständnis — Umgangssprache → Geschäftssprache bzw. aggressive → höfliche Formulierung.

**Entscheidung:** Anthropic Claude API (Sonnet) mit spezifischen System-Prompts.

**Alternativen verworfen:**
- Lokale LLMs (GGUF via llama.cpp) — Für Deutsch nicht die nötige Qualität, hoher RAM-Bedarf, lange Ladezeiten.
- Regelbasiert — Für Modus A (Füllwörter) ausreichend, für semantische Umformulierung unmöglich.

**Tradeoff:** Erfordert API-Key und Internetverbindung. Mitigation: Automatischer Fallback auf Modus A (Clean) wenn kein Key vorhanden.

---

## 003 — Push-to-Talk statt Toggle (2026-04-15)

**Kontext:** Nutzer muss Aufnahmestart und -ende signalisieren.

**Entscheidung:** Push-to-Talk (Taste halten = aufnehmen, loslassen = verarbeiten).

**Alternativen verworfen:**
- Toggle (einmal drücken = Start, nochmal drücken = Stop) — Risiko versehentlicher Endlos-Aufnahmen, zusätzlicher State nötig.
- Voice Activity Detection (VAD) allein — Unzuverlässig bei Hintergrundgeräuschen, schwer zu steuern wann die Aufnahme endet.

---

## 004 — F9 als Standard-Hotkey (2026-04-16)

**Kontext:** Der Hotkey muss ergonomisch, nicht-invasiv und in möglichst wenigen Anwendungen belegt sein.

**Entscheidung:** `F9` als Standard. Konfigurierbar via `VOCIX_HOTKEY_RECORD` in `.env`.

**Begründung:** Funktionstasten werden von wenigen Anwendungen belegt. `F9` ist eine Einzeltaste — ergonomisch besser als Drei-Tasten-Kombination. Die `keyboard`-Library erkennt Funktionstasten zuverlässig unter Windows.

**Verworfene Alternative:** `right ctrl` — die `keyboard`-Library konnte Press/Release-Events für Modifier-Tasten (Ctrl, Shift, Alt) unter Windows nicht zuverlässig erkennen. Trotz korrekter Scan-Code-Auflösung (57373) wurden Events nicht konsistent ausgelöst.

---

## 005 — Portable .exe via PyInstaller (2026-04-16)

**Kontext:** App soll ohne Python-Installation lauffähig sein, portabel auf USB-Stick/Netzlaufwerk.

**Entscheidung:** PyInstaller im Ordner-Modus (nicht One-File). Whisper-Modell wird nicht gebundelt, sondern beim ersten Start in `models/` heruntergeladen.

**Alternativen verworfen:**
- One-File .exe — Entpackt bei jedem Start in Temp-Verzeichnis, langsamer Startvorgang, Virenscanner-Probleme.
- Nuitka — Bessere Performance, aber komplexeres Build-Setup und längere Build-Zeiten.
- Whisper-Modell in .exe bundlen — Würde die .exe um ~500 MB aufblähen; Download-on-Demand ist praktikabler.

---

## 006 — RDP-Modus mit konfigurierbaren Delays (2026-04-15)

**Kontext:** In Remote-Desktop-Sessions wird die Zwischenablage zwischen lokalem und Remote-Rechner synchronisiert. Die Standard-Delays (50ms/100ms) sind dafür zu kurz.

**Entscheidung:** `VOCIX_RDP_MODE=true` setzt automatisch längere Delays (200ms/400ms). Delays sind auch einzeln konfigurierbar.

**Tradeoff:** Höhere Latenz bei der Texteinfügung in RDP-Sessions (~400ms statt ~150ms).

---

## 007 — VAD-Filter bei Transkription (2026-04-16)

**Kontext:** Aufnahmen enthalten oft Stille am Anfang/Ende (Verzögerung beim Drücken/Loslassen des Hotkeys) und Hintergrundgeräusche. Ohne Vorfilterung versucht Whisper, auch diese Abschnitte zu transkribieren — das erzeugt Halluzinationen (erfundener Text bei Stille) und erhöht die Latenz.

**Entscheidung:** `vad_filter=True` in der Whisper-Transkription aktivieren. faster-whisper nutzt dafür Silero VAD v6, ein ~2 MB großes ONNX-Modell, das Sprache von Nicht-Sprache unterscheidet.

**Funktion:** Silero VAD analysiert das Audio in kurzen Frames (~30ms) und klassifiziert jeden als Sprache/Stille. Nur als Sprache erkannte Segmente werden an Whisper übergeben. Dies:
- Reduziert die zu transkribierende Audiomenge (schnellere Verarbeitung)
- Verhindert Halluzinationen in stillen Abschnitten
- Ermöglicht saubere Segmentierung bei längeren Aufnahmen

**PyInstaller-Besonderheit:** Die Datei `silero_vad_v6.onnx` liegt im `faster_whisper/assets/`-Verzeichnis und wird von PyInstaller nicht automatisch erkannt. Sie muss explizit in `vocix.spec` als `datas`-Eintrag aufgenommen werden.

---

## 008 — Package-Name `vocix` (2026-04-18)

**Kontext:** Das Projekt startete unter dem Arbeitstitel *VOCIX*. Das Python-Package hieß entsprechend `textme/`, die Haupt-App-Klasse `VOCIXApp`. Parallel dazu setzte sich im User-Interface, im Log-Header, in den Env-Variablen (`VOCIX_*`), in der `.exe`-Spec und in der Repo-URL bereits das Akronym **VOCIX** (DICtation with Text Understanding & Modification) durch. Das Ergebnis war ein inkonsistenter Zustand: User sahen "VOCIX", Entwickler lasen "textme" in jeder Import-Zeile.

**Entscheidung:** Voller Cutover auf `vocix` als einzigen Projektnamen. Python-Package `vocix/`, Klasse `VocixApp`, alle Imports `from vocix...`.

**Alternativen verworfen:**
- *Package bleibt `textme/`, nur UI-Strings werden geändert* — Entwickler- und User-Sicht bleiben dauerhaft getrennt. Jeder neue Beitragende muss die Abbildung intern lernen.
- *Alles zurück auf `VOCIX`* — widerspricht dem bereits etablierten User-facing Namen und bedeutet breaking Changes für alle `VOCIX_*`-Env-Vars, die Nutzer in ihren `.env`-Dateien haben.

**Tradeoff:** Ein einzelner großer Rename-Commit ist nicht vermeidbar (21 Dateien, alle Imports). Rückwärts-Kompatibilität für eine alte `textme.*`-Import-API wäre unnötig — das Package wird nicht als Library konsumiert, sondern ausschließlich als Standalone-App gestartet (`python -m vocix.main` oder `VOCIX.exe`).

**Migrationspfad:** Keiner für Endnutzer — Env-Vars hießen bereits `VOCIX_*`, der Logfile-Pfad war bereits `vocix.log`. Für Entwickler: Klon neu ziehen oder `git pull` + einmal `__pycache__/` aufräumen.
