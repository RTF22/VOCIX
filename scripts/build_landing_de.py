"""Erzeugt die deutsche Landingpage docs/de/index.html aus docs/index.html.

Quelle der Wahrheit ist die englische Seite docs/index.html. Elemente mit
data-i18n="key" bekommen den deutschen Inhalt aus scripts/landing_de.json,
dazu werden <head>-Metadaten, relative Pfade und der Sprachschalter angepasst.

    python scripts/build_landing_de.py          # docs/de/index.html schreiben
    python scripts/build_landing_de.py --check  # nur prüfen, ob aktuell (Exit 1 sonst)
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EN_PAGE = ROOT / "docs" / "index.html"
DE_PAGE = ROOT / "docs" / "de" / "index.html"
DE_STRINGS = ROOT / "scripts" / "landing_de.json"

_OPEN_TAG = re.compile(r'<(\w+)\b[^>]*\sdata-i18n="(\w+)"[^>]*>')


def _find_close(page: str, tag: str, start: int) -> int:
    """Index des schließenden </tag>, das zum bei `start` geöffneten Element gehört."""
    depth = 1
    for m in re.compile(rf"<(/?){tag}\b[^>]*>").finditer(page, start):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return m.start()
    raise ValueError(f"Kein schließendes </{tag}> ab Position {start}")


def replace_i18n(page: str, strings: dict[str, str]) -> tuple[str, list[str]]:
    """Ersetzt den Inhalt aller data-i18n-Elemente.

    Gibt die neue Seite und die Keys aus `strings` zurück, die im Markup
    nicht vorkommen.
    """
    out: list[str] = []
    used: set[str] = set()
    pos = 0
    while (m := _OPEN_TAG.search(page, pos)) is not None:
        tag, key = m.group(1), m.group(2)
        close = _find_close(page, tag, m.end())
        out.append(page[pos:m.end()])
        if key not in strings:
            raise KeyError(f"Keine Übersetzung für data-i18n=\"{key}\"")
        out.append(strings[key])
        used.add(key)
        pos = close
    out.append(page[pos:])
    return "".join(out), sorted(set(strings) - used)


def _sub_once(pattern: str, repl: str, page: str) -> str:
    new, n = re.subn(pattern, lambda _m: repl, page, count=1)
    if n != 1:
        raise ValueError(f"Muster nicht gefunden: {pattern}")
    return new


def _replace_exact(page: str, old: str, new: str) -> str:
    if page.count(old) != 1:
        raise ValueError(f"Erwartet genau ein Vorkommen von: {old}")
    return page.replace(old, new)


def build(en_page: str, data: dict) -> str:
    meta = data["meta"]
    page, unused = replace_i18n(en_page, data["strings"])
    if unused:
        raise KeyError(f"Übersetzungen ohne data-i18n im Markup: {unused}")

    attr = lambda s: html.escape(s, quote=True)  # noqa: E731
    page = _replace_exact(page, '<html lang="en">', '<html lang="de">')
    page = _sub_once(r"<title>.*?</title>", f"<title>{html.escape(meta['title'])}</title>", page)
    for name, value in (
        (r'name="description"', meta["description"]),
        (r'property="og:title"', meta["og_title"]),
        (r'property="og:description"', meta["og_description"]),
        (r'property="og:url"', "https://vocix.de/de/"),
        (r'property="og:locale"', "de_DE"),
    ):
        page = _sub_once(rf'<meta {name} content="[^"]*">', f'<meta {name} content="{attr(value)}">', page)
    page = _replace_exact(
        page,
        '<link rel="canonical" href="https://vocix.de/">',
        '<link rel="canonical" href="https://vocix.de/de/">',
    )

    # Relative Pfade: die deutsche Seite liegt eine Ebene tiefer.
    page = page.replace('href="assets/', 'href="../assets/')
    page = _replace_exact(page, 'href="vocix-tokens.css"', 'href="../vocix-tokens.css"')

    # Sprachschalter: aktiven Zustand tauschen, Links relativ zur neuen Ebene.
    page = _replace_exact(
        page,
        '<a class="lang-btn active" href="./" hreflang="en" lang="en" aria-current="page">EN</a>',
        '<a class="lang-btn" href="../" hreflang="en" lang="en">EN</a>',
    )
    page = _replace_exact(
        page,
        '<a class="lang-btn" href="de/" hreflang="de" lang="de">DE</a>',
        '<a class="lang-btn active" href="./" hreflang="de" lang="de" aria-current="page">DE</a>',
    )
    return page


def main(argv: list[str]) -> int:
    en_page = EN_PAGE.read_text(encoding="utf-8")
    data = json.loads(DE_STRINGS.read_text(encoding="utf-8"))
    result = build(en_page, data)

    if "--check" in argv:
        current = DE_PAGE.read_text(encoding="utf-8") if DE_PAGE.exists() else ""
        if current != result:
            print("docs/de/index.html ist veraltet: python scripts/build_landing_de.py ausführen")
            return 1
        print("docs/de/index.html ist aktuell")
        return 0

    DE_PAGE.parent.mkdir(parents=True, exist_ok=True)
    DE_PAGE.write_text(result, encoding="utf-8", newline="\n")
    print(f"geschrieben: {DE_PAGE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
