# Workflows

Dokumentation der Arbeitsabläufe für dieses Projekt.

---

## Code-Review → GitHub-Issues (2026-04-18)

**Zweck:** Befunde aus einem Code-Review strukturiert und nachvollziehbar abarbeiten, statt sie in Chat-Protokollen zu verlieren.

### Ablauf

1. **Review durchführen** — z.B. via Claude Code Agent (`superpowers:code-reviewer`) oder manuell. Scope (gesamter Codebase, uncommitted Changes, Modul) vorher festlegen.
2. **Findings sichten** — Übersichtstabelle mit Severity (`HIGH`/`MEDIUM`/`LOW`/`NIT`), Datei-Referenzen und Kurzbegründung.
3. **Drafts lokal ablegen** — pro Finding eine Markdown-Datei in `.plans/issues/NN-<kurzbezeichnung>.md`. Struktur: Problem / Referenzen / Empfehlung / Akzeptanzkriterien.
4. **GitHub-Issues erstellen** — via `gh issue create --title "[HIGH|MEDIUM] ..." --body-file ".plans/issues/NN-...md" --label bug`.
   - `HIGH`-Findings einzeln als Issue.
   - `MEDIUM`-Findings können thematisch gebündelt werden (z.B. mehrere Thread-Safety-Issues im selben Modul → 1 Issue).
   - Severity im Titel kodieren: `[HIGH]`, `[MEDIUM]`.
   - Nur Standardlabels nutzen: `bug`, `enhancement`, `documentation`.
5. **Issues abarbeiten** — sequenziell, pro Issue ein Commit mit `Closes #N` in der Commit-Message, damit GitHub das Issue automatisch schließt.

### Konventionen

- **Drafts in `.plans/issues/` behalten** — nachvollziehbar, auch wenn GitHub-Issue später bearbeitet wird. Nicht committen (`.plans/` ist in `.gitignore`, falls nicht: hinzufügen).
- **Sprache:** Deutsch, passend zum Projektstil (CLAUDE.md, Docstrings, Logmessages).
- **Referenzen:** `datei.py:ZeileStart-ZeileEnde` im Draft-Body — kein Anspruch auf GitHub-Permalinks mit SHA, da die Issues beim Review-Zeitpunkt erstellt werden und Line-Numbers beim Fixen wandern.
- **Akzeptanzkriterien:** Als Checkliste im Issue — erleichtert das Schließen und den Umgang mit Reviewern.

### Wer wann aufruft

- Der Nutzer fordert ein Review explizit an (z.B. *"Machen wir noch ein Code-Review"*).
- Bei Zustimmung wird der `code-reviewer`-Agent dispatched und anschließend der Issue-Erstellungs-Workflow durchlaufen.
- Keine Issues ohne Bestätigung durch den Nutzer — Issues sind in GitHub sichtbar und lösen ggf. Notifications aus.

### Agenten im Einsatz

- **Review-Agent** (`superpowers:code-reviewer` für lokale Codebases, `code-review:code-review` für GitHub-PRs) — läuft als eigener Subagent mit isoliertem Kontext und liefert eine strukturierte Finding-Liste zurück. Der Haupt-Agent behält nur die Zusammenfassung, nicht die zwischengelagerten Dateiinhalte.
- **Unterverteilung innerhalb des Review-Agents** — der Review-Agent selbst orchestriert Haiku- und Sonnet-Sub-Agenten: Haiku filtert (ist die PR noch offen, gibt es bereits ein Review?), Sonnet liest Dateien parallel unter verschiedenen Gesichtspunkten (CLAUDE.md-Konformität, offensichtliche Bugs, Git-History, Kommentar-Vorgaben). Das parallelisiert den Review und hält einzelne Kontexte klein.
- **Plan-Agent** für Entscheidungen mit mehreren Optionen pro Issue (z.B. Clipboard-Multi-Format vs. Warnung + ADR) — liefert strukturierten Vorschlag zurück, auf dessen Basis der Haupt-Agent die Option mit dem Nutzer verhandelt.
- **Task-Tracking via TaskCreate/TaskUpdate** — innerhalb der Session behält der Haupt-Agent den Fortschritt (welche Issues sind zu, welche offen, welche haben noch offene Entscheidungen). Keine Persistenz über die Session hinaus, reine Working-Memory-Struktur.

### Sequenzielle Abarbeitung

Pro Issue genau dieser Ablauf:

1. **Issue lesen** via `gh issue view N` — Problem, Referenzen, Empfehlung, Akzeptanzkriterien.
2. **Entscheidungsgate** — Issues mit Optionen A/B/C werden dem Nutzer vorgelegt (Empfehlung + Kompromiss, 2–3 Sätze pro Option). Keine Implementierung ohne explizite Antwort.
3. **Implementieren** — kleinstmögliche Änderung, die das Akzeptanzkriterium erfüllt. Keine Refactorings oder Nebenänderungen.
4. **Verifizieren** — `python -m py_compile`, gezielter Smoke-Test der veränderten Funktion.
5. **Commit** — einzelner Commit pro Issue, Footer mit `Closes #N`. Commit-Body erklärt *warum* (Ursache), nicht *was* (diff).
6. **Weiter zum nächsten Issue** — keine Batch-Commits, keine Reihenfolge-Abhängigkeit außerhalb technischer Notwendigkeiten.

### Release-Commit und Push

Nach jeweils einem zusammenhängenden Issue-Block:

- **Versions-Bump** in `vocix/__init__.py` (Patch-Stelle, z.B. `0.8.1 → 0.8.2`).
- **CHANGELOG-Eintrag** mit neuem `[0.8.2]`-Abschnitt, pro Issue ein Stichpunkt mit Issue-Nummer in Klammern.
- **ADR** falls die Umsetzung eine grundsätzliche Entscheidung enthält (z.B. Clipboard-Grenze, Package-Name).
- **`git push origin main`** — GitHub schließt jedes Issue mit `Closes #N`-Referenz automatisch; keine manuelle Nachbearbeitung nötig.

### Warum das funktioniert

- **Jeder Commit ist unabhängig review- und revertierbar** — wenn später ein Fix Probleme macht, betrifft das nur den einen Commit. Batch-Commits verwischen Ursachen.
- **GitHub-Issues als Ziel-Liste** — der Haupt-Agent muss nicht raten, was zu tun ist, sondern arbeitet eine gepflegte Liste ab. Der Nutzer sieht parallel in GitHub, was läuft und was offen ist.
- **Entscheidungsgates halten den Menschen im Loop** — die KI schlägt vor, der Mensch entscheidet. Die Qualität der Einzelentscheidung ist der Hebel, nicht die Implementierungsgeschwindigkeit.
- **Referenz-Case (2026-04-18, VOCIX v0.8.0 → v0.8.2):** ein Review-Durchlauf produzierte 11 Issues, Abarbeitung in zwei Phasen → 10 Issue-Fixes + 2 Release-Commits + 2 neue ADRs, insgesamt 14 Commits, einmal `git push`. Alle 10 Issues sind durch die Commit-Referenzen automatisch geschlossen.

---
