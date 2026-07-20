# Interaktives Onboarding-Tutorial — Design

**Datum:** 2026-07-20
**Status:** Entwurf (User-approved, vor Implementierungsplanung)

## Ziel

Ein geführtes, hands-on Tutorial, das neuen VOCIX-Nutzer:innen den Kern-Loop
beibringt (aufnehmen → sprechen → Text landet am Cursor), alle vier Modi zeigt,
die wichtigsten Design-Eigenheiten erklärt (Clipboard-Rettung, wo der Text
landet) und anschließend durch alle Einstellungen führt. Es passt sich dem
lokalen System an (welche Modi freigeschaltet sind, GPU verfügbar etc.).

Motiviert durch Nutzer:innen-Feedback (Systemtesterin): „ich weiß nicht wo das
überhaupt reingeschrieben wird", „schön ist wenn man ne Anweisung kriegt"
(Dark-Souls-1→3-Onboarding-Bogen: geführt, dann frei), „mich nervt dass die
Einstellungen kein Speicher-Button hatten" (inzwischen in 1.5.0 gefixt — das
Tutorial macht das sichtbar), „warum kann man die Hotkeys für Business/Rage
nicht ändern" (inzwischen freischaltbar, sobald ein Provider validiert ist).

## Grundentscheidungen (aus Brainstorming)

1. **Grundform:** Geführtes eigenes Fenster mit Schritten und Erfolgserkennung
   (nicht passiver Info-Dialog, nicht Overlay-Coach).
2. **Textziel:** Fokussiertes Übungs-Textfeld im Tutorial-Fenster. VOCIX fügt
   real per Ctrl+V ein; das Feld garantiert nur den Fokus, sodass der Text
   sichtbar dort landet.
3. **Umfang:** Zweistufig — Kernpfad (hands-on) + volle Settings-Tour durch alle
   vier Tabs.
4. **Gesperrte Modi:** Alle vier Modi werden gezeigt. Freigeschaltete Modi
   laufen echt; gesperrte LLM-Modi (kein validierter Provider) zeigen ein
   statisches Vorher/Nachher-Demo aus i18n, ohne API-Call.
5. **Erststart:** Beim allerersten Start eine Ja/Nein-Einladung. In beiden
   Fällen wird `tutorial_seen` gesetzt — kein erneutes Nerven. Jederzeit über
   einen Tray-Menüpunkt erneut startbar.

## Architektur

### Event-Dispatch auf `VocixApp` (Erfolgserkennung)

Das Tutorial muss erkennen, wann ein Schritt geschafft ist. Gewählter Ansatz:
leichter Observer-Mechanismus auf `VocixApp`, damit die **echte** Pipeline
läuft (echtes Ctrl+V ins fokussierte Übungsfeld, echte Clipboard-Rettung).

- `VocixApp` bekommt eine Listener-Liste und eine private `_emit(event, **data)`.
- Emittierte Events:
  - `recording_started` — in `_on_record_start`, nach erfolgreichem Start.
  - `text_injected` mit `text: str, mode: str` — in `_process_pipeline`, direkt
    nach erfolgreichem `self._injector.inject(...)`.
  - `mode_changed` mit `mode: str` — in `_set_mode`.
- Öffentliche API: `register_tutorial_listener(cb)` / `unregister_tutorial_listener(cb)`.
- Listener werden im Overlay-/Tk-Thread aufgerufen? Nein: Events feuern aus dem
  Pipeline-Worker-Thread bzw. Hotkey-Thread. Der Tutorial-Controller muss die
  Weiterverarbeitung über `root.after(0, ...)` in den Tk-Thread marshallen
  (analog zu `StatusOverlay._schedule`). Der Controller kapselt das.
- Fehler in einem Listener dürfen die Pipeline nicht stören (try/except je
  Listener, geloggt).

Begründung gegen Alternativen: eine eigene Mini-Pipeline im Tutorial würde das
reale Verhalten (Injection, Clipboard) nicht zeigen; State-Polling wäre fragil.

### Neues Modul `vocix/ui/tutorial.py`

Trennung Controller/View, damit die Schrittlogik headless testbar ist:

- **`TutorialController`** — hält die Step-Sequenz, den aktuellen Index, den
  Systemzustand-Snapshot (welche Modi frei, GPU, Provider validiert) und
  entscheidet, ob ein eingehendes Event den aktuellen Schritt erfüllt. Kennt
  **keine** Tk-Widgets. Kann in Tests mit gefakten Events durchgespielt werden.
- **`TutorialWindow`** — `tk.Toplevel`, **kein `grab_set`** (globaler
  PTT-Hotkey, Tippen und ein später geöffneter Settings-Dialog müssen
  koexistieren). Enthält:
  - Fortschrittsanzeige (z.B. „Schritt 3 / 9")
  - Titel + Anweisungstext des aktuellen Schritts
  - **fokussiertes Übungs-Textfeld** (`tk.Text`, normal beschreibbar, damit das
    reale Ctrl+V dort landet); Fokus wird beim Betreten eines Aufnahme-Schritts
    erzwungen.
  - Buttons: Zurück / Weiter / Überspringen / Schließen
  - Für Script-Demo-Schritte: eine Vorher/Nachher-Karte statt Übungsfeld.
- Singleton-Verhalten analog `show_about`/`show_settings`: bereits offenes
  Fenster wird nach vorne gehoben.

### Schritt-Modell

Schritte sind **Daten** (Liste von `Step`-Objekten/Dicts), nicht hartkodierte
Methoden. Jeder Schritt trägt:

- `id` (stabil, für Tests/Persistenz)
- `title_key`, `body_key` (i18n-Keys)
- `kind`: `info` | `record_practice` | `mode_demo` | `settings_tour`
- `expected_event` (optional): welches Event + welche Bedingung den Schritt
  erfüllt und „Weiter" freigibt (z.B. `text_injected`).
- `mode` (bei `mode_demo`): welcher Modus, plus `scripted_before_key` /
  `scripted_after_key` für den gesperrten Fall.
- `available_if` (optional): Predicate auf den Systemzustand-Snapshot, das
  bestimmt, ob echt oder gescriptet gespielt wird.

## Ablauf

### Kernpfad (hands-on)

1. **Willkommen** — was VOCIX in einem Satz ist; „möchtest du ein kurzes
   Tutorial?" ist bereits davor beantwortet (Einladung), hier Start.
2. **Aufnehmen** (`record_practice`) — Anweisung: „Halte `<PTT-Taste>`, sag
   einen Satz, lass wieder los." Fokus liegt im Übungsfeld. Wartet auf
   `text_injected`; bei Erfolg erscheint der echte Text im Feld → „Geschafft!".
   PTT-Taste wird live aus `config.hotkey_record` eingesetzt.
3. **Wo landet der Text** (`info`) — erklärt: immer am aktiven Cursor, technisch
   per Ctrl+V. Gerade eben sichtbar im Übungsfeld bewiesen.
4. **Clipboard-Rettung** (`info`) — erklärt: Zwischenablage wird gesichert, durch
   das Transkript ersetzt, danach wiederhergestellt („merkt man fast nicht").
5. **Modi** (`mode_demo` × 4):
   - Clean: echt vorführbar (immer verfügbar).
   - Business / Rage / LaTeX: freigeschaltet → echt spielbar; gesperrt →
     statisches Vorher/Nachher aus i18n + Hinweis „im LLM-Tab freischaltbar".
   - Rage-Szene mit Roleplay-Text („Stell dir vor, du hast Kaffee über der
     Tastatur verschüttet, während du mit deinem Chef redest — sag ihm wütend,
     dass du eine Lohnerhöhung brauchst").
   - LaTeX-Schritt bietet eine **Formel-Vorlage zum Ablesen** (z.B. „x quadrat
     plus y quadrat gleich r quadrat").
6. **Hotkeys** (`info`) — PTT muss Einzeltaste sein (kein `+`); Modus-Hotkeys
   Ctrl+Shift+1/2/3/L; Hinweis: Modus-Hotkeys werden freigeschaltet, sobald ein
   LLM-Provider validiert ist.

### Settings-Tour (Stufe 2)

- Öffnet den **echten** `SettingsDialog` (über den bestehenden
  `open_settings`-Pfad), sodass das Tutorial-Panel daneben Tab für Tab führt:
  Basics → LLM → Erweitert → Expert.
- Erklärt je Tab die **wichtigen** Felder konzeptionell (nicht stur jedes
  einzelne Widget — reduziert Pflege-Drift), zeigt aber explizit:
  - den **Speichern/Abbrechen**-Button („anklicken und gut, wie im Browser —
    nichts wird wirksam, bevor du Speichern drückst")
  - im LLM-Tab: hier schaltet man Business/Rage/LaTeX (und deren Hotkeys) frei.
- Da `TutorialWindow` kein `grab_set` hält, koexistiert es mit dem
  `SettingsDialog` (der selbst `grab_set` macht). Reihenfolge und Fokus-Handling
  werden im Plan präzisiert.

## Verkabelung (bestehende Dateien)

- **`vocix/main.py`** (`VocixApp`):
  - Event-Dispatch (`_emit`, `register_tutorial_listener`,
    `unregister_tutorial_listener`); `_emit`-Aufrufe in `_on_record_start`,
    `_process_pipeline`, `_set_mode`.
  - `open_tutorial()` — öffnet das Tutorial im Overlay-Tk-Thread.
  - Erststart-Check nach „ready": wenn `not load_state().get("tutorial_seen")`
    → Ja/Nein-Einladung anzeigen; in beiden Fällen `tutorial_seen = True`
    persistieren.
- **`vocix/ui/overlay.py`** — `show_tutorial(...)` analog zu `show_settings`
  (Scheduler in den Tk-Thread, Singleton).
- **`vocix/ui/tray.py`** — neuer Menüpunkt (Key `tray.tutorial`) + Callback
  `on_open_tutorial`, verkabelt in `main.py`.
- **`vocix/i18n.py` / `locales/de.json` / `locales/en.json`** — alle
  Tutorial-Texte inkl. Script-Demo-Vorher/Nachher-Texte und der Einladung.
- **`state.json`** — neues Flag `tutorial_seen: bool`.

## Systemabhängigkeit (Snapshot beim Öffnen)

Der Controller nimmt beim Start einen Snapshot:
- Welche Modi freigeschaltet (`_any_llm_validated`-Äquivalent bzw.
  `config.llm_validated` je Modus-Slot).
- GPU verfügbar (`cuda_available()`) — für den Whisper-/Beschleunigungs-Teil der
  Settings-Tour relevant.
- Aktuelle PTT-Taste + Modus-Hotkeys aus der Config (in Anweisungen einsetzen).

## Erststart-Einladung

- Kleines Toplevel (oder wiederverwendetes Dialog-Muster) mit Titel, ein/zwei
  Sätzen und **Ja / Nein**.
- „Ja" → Tutorial öffnen. „Nein" → schließen. Beide Wege setzen
  `tutorial_seen = True`.
- Erscheint nach der „ready"-Meldung, damit das Modell-Laden nicht überlagert
  wird.

## Testbarkeit

- `TutorialController` wird von Tk entkoppelt: Step-Sequenz-Aufbau,
  Event→Fortschritt-Logik und der Systemzustand-Snapshot lassen sich headless
  testen (gefakte Events einspeisen, erwarteten Fortschritt prüfen).
- Erststart-Flag-Logik (`tutorial_seen` setzen/lesen) testbar über `load_state`/
  `update_state`.
- Reine Tk-Darstellung wird nicht automatisiert getestet (bestehende Praxis).

## Bewusst nicht enthalten (YAGNI)

- Kein Video, keine animierten Highlights einzelner Widgets im Settings-Dialog
  (ttk-Widget-Highlighting ist fragil).
- Keine Persistenz des Fortschritts über Sessions (Tutorial startet immer von
  vorn; „Überspringen" pro Schritt reicht).
- Keine Mehrsprachigkeit über die bestehenden DE/EN-Locales hinaus.

## Offene Punkte für die Plan-Phase

- Genaue Fokus-/Fenster-Reihenfolge, wenn Tutorial + Settings-Dialog gleichzeitig
  offen sind.
- Endgültige Tab-für-Tab-Texttiefe der Settings-Tour (Balance „alles erklären"
  vs. Pflege-Drift) — beim Spec-Review kalibrieren.
