# Rebranding: DICTUM → VOCIX

**TL;DR:** Das Projekt hieß bis v0.9.1 **DICTUM**. Seit v1.0.0 (April 2026) heißt es **VOCIX**. Der Code ist identisch, nur die Namen haben sich geändert.

## Warum der Wechsel?

„DICTUM" ist ein echtes lateinisches Wort („Ausspruch", „Maxime") und damit im Markenrecht angreifbar. **VOCIX** ist ein reines Kunstwort (aus *VOice Capture & Intelligent eXpression*) — neutral-technisch, keine Google-Treffer im Tech-Space, saubere Marke für eine mögliche kommerzielle Zukunft.

Der Wechsel kam früh: bei 4 Releases und einem einzigen Nutzer. Später wäre es exponentiell teurer geworden.

## Was heißt das für dich als neuer Nutzer?

**Nichts, außer:** du lädst `VOCIX-v1.0.0-win-x64.zip` herunter und startest `VOCIX.exe`. Alles Weitere wie vorher — Push-to-Talk mit `F9`, drei Modi, System Tray.

## Was heißt das für DICTUM-Bestandsnutzer?

Wenn du noch eine `DICTUM`-Version installiert hast:

1. Der **Auto-Update-Check** meldet v1.0.0 automatisch beim nächsten Start (GitHub-Redirects fangen den API-Call ab).
2. Neue ZIP herunterladen, entpacken.
3. Falls eine `.env` existiert: `DICTUM_` durch `VOCIX_` ersetzen. Beispiel:
   ```ini
   # Vorher
   DICTUM_HOTKEY_RECORD=f9
   # Nachher
   VOCIX_HOTKEY_RECORD=f9
   ```
4. Optional: `models/`-Ordner aus der alten Installation in den neuen `VOCIX/`-Ordner kopieren, um den 500-MB-Whisper-Download zu sparen.

Alte State-Dateien unter `%APPDATA%/TextME/` können gelöscht werden — der neue Pfad ist `%APPDATA%/VOCIX/`.

## Was hat sich konkret geändert?

| Alt (DICTUM) | Neu (VOCIX) |
|---|---|
| Python-Package `dictum/` | `vocix/` |
| Entry-Point `python -m dictum.main` | `python -m vocix.main` |
| Env-Var-Präfix `DICTUM_*` | `VOCIX_*` |
| Exe-Name `DICTUM.exe` | `VOCIX.exe` |
| State-Dir `%APPDATA%/TextME/` | `%APPDATA%/VOCIX/` |
| Log-Datei `dictum.log` | `vocix.log` |
| GitHub-Repo `RTF22/DICTUM` | `RTF22/VOCIX` |
| Release-Asset `DICTUM-vX.Y.Z-win-x64.zip` | `VOCIX-vX.Y.Z-win-x64.zip` |

Die alten GitHub-Releases (`v0.8.x`, `v0.9.x`) bleiben als *DICTUM*-Builds erhalten — das ist korrekte Historie, keine Altlast. Nur ab v1.0.0 gilt der neue Name.

## Funktionalität

Unverändert. Das Rebranding hat **keinen** inhaltlichen Bug gefixt, kein Feature ergänzt und keine Performance-Änderung gebracht. Es ist reines Umetikettieren.

Die Architektur, die drei Modi (Clean/Business/Rage), der Auto-Update-Check, Push-to-Talk — alles identisch zu v0.9.1.
