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

---
