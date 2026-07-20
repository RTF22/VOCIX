# Settings: Draft + Speichern/Abbrechen + gezielter Neustart

**Datum:** 2026-07-20
**Ziel:** Einstellungsänderungen werden erst durch „Speichern" wirksam und persistiert;
„Abbrechen" verwirft alles. Nicht-live-fähige Änderungen lösen einen kontrollierten
Neustart aus. Beta `1.5.0-beta.2`.

## Problemanalyse

1. **Stale-Config-Bug (Ursache):** `VocixApp.apply_settings` ersetzt die App-Referenz
   (`self._config = new_config`). Sub-Komponenten (`_recorder`, `_injector`, `_overlay`,
   Prozessoren, `_stt`) halten aber ihre **eigene** Referenz aus dem Konstruktor. Live-
   Änderungen an deren Feldern erreichen sie nie. Dasselbe latente Muster in
   `_reload_stt` (`main.py:249`).
2. **Draft-Leaks:** Der Provider-„Test"-Button schreibt `validated` sofort nach
   `state.json` (`settings.py:_on_llm_test`) — am Draft vorbei, überlebt „Abbrechen".
3. **Kein Neustart-Pfad:** Log-Level/Log-Datei greifen nur beim Start (Handler werden
   einmalig angehängt), es gibt keinen Mechanismus, das wirksam zu machen.

## Design

### 1. Config-Weitergabe (Fundament)
- Neue Methode `Config.update_from(other)`: überschreibt alle persistierten Felder der
  bestehenden Instanz in-place (inkl. `llm`), ruft `__post_init__` erneut.
- `apply_settings` mutiert die gemeinsame Instanz via `update_from` statt sie zu
  ersetzen. Danach sehen alle Komponenten, die Config per-Call lesen, den neuen Stand.
- `_injector` cached im Konstruktor → in `apply_settings` neu erzeugen (`TextInjector(cfg)`).
- `_reload_stt` ebenfalls auf `update_from` umstellen (Konsistenz, latenter Bug).

### 2. Dialog = reiner Draft (`settings.py`)
- Button-Leiste: nur **Speichern** (`_on_save`) und **Abbrechen** (`_on_cancel`).
  „Übernehmen"/Apply entfällt (`_apply_btn`, `_on_apply` raus).
- `WM_DELETE_WINDOW` = Abbrechen (bereits so).
- Provider-„Test": Ergebnis wandert in `self._draft` (in-memory Feld
  `providers[slot]["validated"]`), **nicht** nach `state.json`. Gating (`_any_llm_validated`,
  `_key_validated`) liest aus Draft statt `load_state()`.
- `_on_save` = bisheriges `_on_ok` (validate → `_persist_llm_draft` → Callback → close),
  erweitert um Neustart-Klassifizierung (siehe 3).

### 3. Neustart-Klassifizierung
- **Restart-required Felder:** `log_level`, `log_file` (nur beim Start konsumiert).
- Alle übrigen Felder greifen live über `update_from` + vorhandene Reload-Hooks.
- Ablauf `apply_settings(new_config)`:
  1. Persistieren nach `state.json` (wie bisher).
  2. Diff alt→neu berechnen.
  3. `update_from`, Reload-Hooks (i18n/STT/Hotkeys/Injector/Tray) selektiv.
  4. Rückgabe/Signal, ob `log_level`/`log_file` im Diff → Dialog fragt Neustart an.
- Dialog: bei Restart-Diff `messagebox.askyesno(...)` →
  - Ja: `VocixApp.restart()` (Relaunch `sys.executable` mit Ursprungs-Argv bzw. bei
    frozen die EXE, dann `_quit()` + `os._exit(0)`).
  - Nein: nichts weiter (Live-Teil ist schon angewandt, Log greift beim nächsten Start).
- Bei reinem Live-Save: Dialog schließt, `overlay.show_temporary("Gespeichert", "done")`.

### 4. Neustart-Mechanismus
- `VocixApp.restart()`: `subprocess.Popen` auf `[sys.executable]` (frozen) bzw.
  `[sys.executable, "-m", "vocix.main"]` (Source), detached; danach regulärer `_quit()`
  und Sicherheitsnetz `os._exit(0)` nach kurzer Frist (analog Updater).

### 5. i18n
Neue Keys DE/EN: `settings.button.save`, `settings.confirm.restart_needed.{title,body}`,
`settings.notice.saved`. Alte `settings.button.ok`/`apply` bleiben ungenutzt/entfernt.

## Tests
- `Config.update_from` überträgt alle persistierten Felder + `llm`, respektiert
  `__post_init__` (RDP-Delays).
- Persistenz-Roundtrip Hotkey (Draft → state.json → reload) — Regression.
- Diff-Klassifizierung: nur `log_level`/`log_file` markieren „restart".
- Provider-Test schreibt nicht nach `state.json` vor Save (validated nur im Draft).

## Out of Scope
- Kein Umbau der Tray-Schnellumschalter (Modell/Beschleunigung) — die persistieren
  bewusst sofort und sind kein Dialog.
