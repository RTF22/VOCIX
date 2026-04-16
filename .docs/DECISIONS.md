# Technische Entscheidungen

Dokumentation der wichtigsten Design- und Technologieentscheidungen mit Begründung.

---

## 001 — Clipboard-basierte Texteinfügung (2026-04-15)

**Kontext:** Text muss systemweit an der Cursorposition eingefügt werden — in beliebigen Anwendungen (Browser, Office, IDEs, Terminal).

**Entscheidung:** Clipboard-Methode (Zwischenablage sichern → Text kopieren → Ctrl+V senden → Zwischenablage wiederherstellen).

**Alternativen verworfen:**
- `pyautogui.write()` — Scheitert an Umlauten (ä, ö, ü, ß) und Sonderzeichen. Sendet einzelne Tastenanschläge, extrem langsam bei langen Texten.
- Windows `SendInput` API direkt — Gleiche Unicode-Probleme, höhere Komplexität.

**Tradeoff:** Kurzzeitige Unterbrechung der Zwischenablage des Nutzers (wird nach ~200ms wiederhergestellt).

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

## 004 — Rechte Strg-Taste als Standard-Hotkey (2026-04-16)

**Kontext:** Der Hotkey muss ergonomisch, nicht-invasiv und in möglichst wenigen Anwendungen belegt sein.

**Entscheidung:** Rechte Strg-Taste als Standard. Konfigurierbar via `DICTUM_HOTKEY_RECORD` in `.env`.

**Begründung:** Die rechte Strg-Taste wird in kaum einer Anwendung eigenständig verwendet. Einzeltaste ist ergonomisch besser als Drei-Tasten-Kombination. Konfigurierbarkeit deckt Sonderfälle ab.

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

**Entscheidung:** `DICTUM_RDP_MODE=true` setzt automatisch längere Delays (200ms/400ms). Delays sind auch einzeln konfigurierbar.

**Tradeoff:** Höhere Latenz bei der Texteinfügung in RDP-Sessions (~400ms statt ~150ms).
