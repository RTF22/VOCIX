# Settings-Dialog für VOCIX

**Status:** Design  
**Datum:** 2026-04-25  
**Zielversion:** v1.4.0-beta.1

## Ziel

Eine zentrale Bildschirmmaske, in der **alle** Einstellungen erreichbar sind, die heute über `Config`, `.env` oder das Tray-Menü gesetzt werden. Auswahlfelder statt Freitext, wo immer möglich, damit Tippfehler ausgeschlossen sind. Zweisprachig DE/EN über das bestehende i18n-System.

## Reichweite

Drei Tabs (`Basics` / `Erweitert` / `Expert`) decken Endnutzer, Power-User und Spezialfälle ab. Wakeword, Snippets, History bleiben in ihren eigenen UIs (eigene Subsysteme); Profile, Settings-Import/Export sind Out-of-Scope (YAGNI).

## Verhältnis zum Tray-Menü

Das Tray-Menü bleibt **unverändert** und behält alle Schnellzugriffe (Modus, Sprache, Whisper-Modell, Beschleunigung, Translate). Es bekommt einen zusätzlichen Eintrag „Einstellungen… / Settings…", der die Maske öffnet. Beide Pfade ändern dieselben Werte; Tray-Häkchen und Submenü-Marker werden nach `apply()` neu aufgebaut, damit der Zustand synchron bleibt.

## Persistenz

Der Dialog schreibt **alles nach `state.json`** (`%APPDATA%/VOCIX/state.json`) über das bestehende `update_state()`-Context-Manager-API (atomar, lock-geschützt). `.env` wird nicht modifiziert — sie bleibt als Override-/Bootstrap-Mechanismus erhalten. Der Vorrang `state.json > .env > Default` aus `Config.load()` bleibt unverändert; eingelesene `.env`-Werte (z. B. ein bereits dort hinterlegter `ANTHROPIC_API_KEY`) erscheinen damit beim ersten Öffnen automatisch im Dialog. Wird der Key im Dialog gespeichert, gewinnt ab dann der `state.json`-Wert. In einer späteren Version kann die `.env`-Unterstützung für den API-Key entfernt werden.

## Apply-Semantik

Klassisch: **OK / Abbrechen / Übernehmen**.

- Felder sind an Tk-Variablen einer **Kopie** der aktuellen `Config` gebunden (`dataclasses.replace`).
- „Abbrechen" verwirft die Kopie.
- „Übernehmen" und „OK" rufen `VocixApp.apply_settings(new_config)` auf; OK schließt zusätzlich das Fenster.
- `apply_settings` bestimmt den Diff zur alten Config und orchestriert:
  1. `update_state()` — atomar, lock-geschützt.
  2. Whisper-Reload bei geändertem Modell/Beschleunigung über den bestehenden `_reload_stt`-Pfad mit `_stt_reload_lock` (race-frei).
  3. Hotkey-Rebind bei geänderten Hotkeys (`keyboard.unhook_all()` + neu registrieren).
  4. `i18n.set_language()` bei geänderter Sprache.
  5. Tray-Menü neu aufbauen, damit Häkchen synchron sind.

## Architektur & Threading

- Neue Datei `vocix/ui/settings.py` mit Klasse `SettingsDialog`.
- Der Dialog läuft als `tk.Toplevel` im **Overlay-Thread** — derselbe Thread, in dem `StatusOverlay.show_about` und der Statistik-Dialog leben. `tk.Tk()`-Root existiert dort bereits.
- Tray-Klick auf „Einstellungen…" → Callback `on_open_settings` an `VocixApp` → Signal an Overlay-Thread via `queue.Queue` → Overlay öffnet `SettingsDialog`.
- Single-Instance: solange ein Dialog offen ist, hebt erneutes Klicken auf „Einstellungen…" nur das bestehende Fenster nach vorne (`lift()` + `focus_force()`).
- Modal: `transient(root)` + `grab_set()`.

## UI-Toolkit

`tkinter` / `ttk` — kein neues Toolkit, kein Bundle-Wachstum. Konsistent mit Overlay, About- und Statistik-Dialog. Picklisten = `ttk.Combobox(state="readonly")`, Schalter = `ttk.Checkbutton`, Pfade = `Entry + Browse-Button` mit `filedialog.askdirectory`/`askopenfilename`.

## Layout

Fenstergröße ~640 × 540 px. Oben `ttk.Notebook` mit drei Tabs, unten Buttonleiste rechtsbündig: `[Übernehmen] [Abbrechen] [OK]`.

### Tab 1 — Basics

| Feld | Widget | Bemerkung |
|---|---|---|
| Eingabesprache | Radio `Deutsch` / `Englisch` + Pickliste „Andere…" | ISO-Kürzel für weitere Whisper-Sprachen; UI fällt auf EN zurück, wenn ≠ DE/EN |
| Ausgabesprache | Combobox readonly | Werte: „Wie Eingabesprache" / „Englisch"; mappt auf Whisper `task=transcribe`/`task=translate` |
| Whisper-Modell | Combobox readonly | tiny / base / small / medium / large-v3 / large-v3-turbo |
| Beschleunigung | Radio `Auto` / `GPU` / `CPU` | GPU disabled, wenn `cuda_available()` = false |
| Anthropic API-Key | `Entry(show="*")` + Toggle `👁` + Button `Test` + Status-Label | siehe Maskierung unten |
| Standardmodus beim Start | Combobox readonly | nur „Clean" wählbar, solange API-Key nicht validiert |
| Hotkey Aufnahme (PTT) | Pickliste (`Pause`, `Scroll Lock`, `F7`–`F12`, `Insert`, `Apps`) + Button `Andere Taste…` | Einzeltaste, Capture-Modal lehnt Kombos ab |
| Hotkey Modus Clean | Modifier-Pickliste + Tasten-Pickliste + `Andere…` | Kombinationen erlaubt |
| Hotkey Modus Business | dito | disabled, solange API-Key nicht validiert |
| Hotkey Modus Rage | dito | disabled, solange API-Key nicht validiert |

### Tab 2 — Erweitert

| Feld | Widget | Bemerkung |
|---|---|---|
| Modellverzeichnis | `Entry` + Button `Durchsuchen…` | `filedialog.askdirectory` |
| Logfile | `Entry` + Button `Durchsuchen…` | |
| Loglevel | Combobox readonly | DEBUG / INFO / WARNING / ERROR |
| Overlay-Anzeigedauer | `Spinbox` 0.5–10.0 s, Schritt 0.5 | |
| RDP-Modus | `Checkbutton` | aktiv setzt Clipboard/Paste-Delays automatisch |
| Clipboard-Delay | `Spinbox` 0.01–1.0 s | disabled wenn RDP aktiv |
| Paste-Delay | `Spinbox` 0.05–1.0 s | disabled wenn RDP aktiv |
| Audio: Silence-Threshold | `Scale` 0.001–0.1 + Live-Wert-Label | |
| Audio: Min-Aufnahmedauer | `Spinbox` 0.1–5.0 s | |

### Tab 3 — Expert

| Feld | Widget | Bemerkung |
|---|---|---|
| Whisper-Sprach-Override | Combobox | „auto" = an Eingabesprache koppeln, sonst ISO-Kürzel |
| Audio: Sample-Rate | Combobox readonly | 16000 / 22050 / 44100 / 48000 |
| **Anthropic-Bereich** | nur sichtbar wenn API-Key getestet=gültig | sonst Hinweistext „API-Key in Basics setzen, um Claude-Optionen freizuschalten" |
| Anthropic-Modell-ID | Combobox editable | Sonnet 4.6 / Opus 4.7 / Haiku 4.5 / Custom |
| Anthropic-Timeout | `Spinbox` 5–60 s | |
| Konfigurationsverzeichnis öffnen | Button | `os.startfile(STATE_FILE.parent)` |
| Auf Werkseinstellungen zurücksetzen | Button | Bestätigungsdialog → `state.json` leeren, Defaults laden, Felder neu befüllen |

## API-Key-Handling

- **Maskierung:** `Entry(show="*")` als Default. Toggle-Button `👁` deckt temporär auf. Wird ein **bereits gespeicherter** Key angezeigt (also nicht gerade frisch eingetippt), erscheint er auch im aufgedeckten Zustand als `sk-ant-…XXXX` (erste 7 + letzte 4 Zeichen, Mitte durch `…` ersetzt) — damit sind Screenshots im Default screenshot-sicher.
- **Edit-Modus:** sobald der User das Feld fokussiert und tippt, wird der Volltext der Eingabe gezeigt (sonst ließe sich Paste-from-Clipboard nicht prüfen). Nach Verlassen des Felds geht die Maskierung wieder an.
- **Test-Button:** Eine kurze Anthropic-Anfrage (1 Token Output) wird gegen den eingegebenen Key gefahren. Bei Erfolg → Status-Label grün ✓, `state["anthropic_key_validated"] = true`. Bei Fehler → rot ✗ mit kurzer Fehlermeldung. Default ist „nicht getestet" (grau –).
- **Gating:** Felder, die Claude voraussetzen (Modus Business/Rage als Default-Modus, Hotkeys für Business/Rage, Anthropic-Sektion in Tab Expert), werden nur freigeschaltet, wenn `anthropic_key_validated = true`. Status wird in `state.json` persistiert; beim Dialog-Open wird der zuletzt-gültige Status genutzt, der User muss nicht erneut testen.

## Hotkey-Capture-Modal

Wird vom Button `Andere Taste…` geöffnet. `tk.Toplevel` ~360 × 140, Text „Drücke jetzt die gewünschte Taste/Kombo… (Esc = Abbrechen)". Liest via `bind("<KeyPress>")` ein einzelnes Event, mappt `event.keysym` auf den `keyboard`-Library-Namen (z. B. `Pause`, `Scroll_Lock`, `F9`, `ctrl+shift+1`).

- Für PTT (`hotkey_record`): Kombinationen werden abgelehnt, gleiche Validierung wie `Config.__post_init__`.
- Für Modus-Hotkeys: Kombinationen sind erlaubt.
- Doppelte Belegung (PTT = Modus-A) → roter Hinweis im Hauptdialog, „Übernehmen"/„OK" werden geblockt, bis aufgelöst.

## Hilfetexte

Jede Option hat einen **Tooltip** (Mouse-Hover, 600 ms Verzögerung, gelbes Popup). Komplexere Felder (Whisper-Modell, Beschleunigung, RDP-Mode, Silence-Threshold, Sample-Rate, Whisper-Sprach-Override, Anthropic-Modell-ID, API-Key) bekommen zusätzlich einen kleinen `?`-Button, der ein modales Hilfe-Popup mit längerem Erklärtext öffnet.

Alle Texte (Labels, Tooltips, Hilfe-Bodies) liegen im i18n-System unter `settings.*` in `locales/de.json` und `locales/en.json`. Schema:

```
settings.title
settings.tab.basics / tab.advanced / tab.expert
settings.field.<feld>
settings.tooltip.<feld>
settings.help.<feld>.title / .body
settings.button.ok / cancel / apply / test / browse / other_key / reset
settings.status.api_valid / api_invalid / api_unchecked
settings.error.<…>
```

## Validierung & Live-Feedback

- Pfade, die nicht existieren → gelbes Warn-Icon neben dem Feld, kein Apply-Block.
- Doppelte Hotkey-Belegung → roter Hinweis + Apply blockiert.
- API-Key-Test-Status farbcodiert (grün/rot/grau).
- Whisper-Modell-Wechsel auf „large-v3" zeigt im Tooltip oder beim Apply einen Hinweis auf die Download-Größe (~3 GB) — Apply selbst läuft trotzdem durch.

## Tests

`tests/ui/test_settings.py`, headless via `tk` mit `withdraw()` oder Mock:

- `test_dialog_initial_values_match_config`
- `test_dialog_apply_writes_to_state_json` — `.env` bleibt unverändert
- `test_dialog_cancel_discards_changes`
- `test_api_key_test_button_marks_validated` — Anthropic-Call gemockt
- `test_business_disabled_without_valid_api_key` — Default-Modus zeigt nur Clean
- `test_business_enabled_after_valid_api_key`
- `test_ptt_hotkey_rejects_combo` — Capture-Modal verweigert `Ctrl+F9`
- `test_duplicate_hotkey_blocks_apply`
- `test_api_key_masked_display` — gespeicherter Key wird als `sk-ant-…XXXX` gerendert
- `test_factory_reset_clears_state_json` — Bestätigungsdialog gemockt
- `test_singleton_dialog_lifts_existing_window`
- `test_tooltip_text_uses_i18n`

## Out-of-Scope

- `.env`-Schreiben.
- Settings-Import/-Export.
- Profile (Arbeit/Privat).
- Wakeword-, Snippet-, History-Konfiguration (haben eigene UIs).
- Migrationscode für `state.json` — neue Felder bekommen Defaults.

## Rollout

Eigene Beta-Release-Version `v1.4.0-beta.1`. Kein Datenmigrations-Schritt nötig; `Config.load()` liest neue State-Felder automatisch und fällt auf Defaults zurück, wenn sie fehlen.
