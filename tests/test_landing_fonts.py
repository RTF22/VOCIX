"""Die Landingpage lädt ihre Schriften selbst gehostet, nie von Google (Datenschutz, LG München I 3 O 17493/20)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
FONTS = DOCS / "assets" / "fonts"


def test_keine_seite_laedt_google_fonts():
    for seite in [*DOCS.rglob("*.html"), *DOCS.rglob("*.css")]:
        inhalt = seite.read_text(encoding="utf-8")
        assert "fonts.googleapis.com" not in inhalt, seite
        assert "fonts.gstatic.com" not in inhalt, seite


def test_seiten_binden_die_lokale_schrift_css_ein():
    assert '<link rel="stylesheet" href="assets/fonts/fonts.css">' in (DOCS / "index.html").read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="../assets/fonts/fonts.css">' in (DOCS / "de" / "index.html").read_text(encoding="utf-8")


def test_fonts_css_verweist_nur_auf_vorhandene_dateien():
    css = (FONTS / "fonts.css").read_text(encoding="utf-8")
    dateien = re.findall(r"url\(([^)]+\.woff2)\)", css)
    assert dateien, "fonts.css enthält keine Schriftdateien"
    for name in dateien:
        assert (FONTS / name).is_file(), name
    for familie, gewichte in {"Bangers": {"400"}, "Nunito": {"400", "600", "700", "800"}, "JetBrains Mono": {"400", "700"}}.items():
        gefunden = set(re.findall(rf"font-family: '{familie}';[^}}]*?font-weight: (\d+);", css))
        assert gefunden == gewichte, (familie, gefunden)


def test_lizenzen_liegen_bei():
    for datei in ("OFL-Bangers.txt", "OFL-Nunito.txt", "OFL-JetBrainsMono.txt"):
        assert "SIL OPEN FONT LICENSE" in (FONTS / datei).read_text(encoding="utf-8").upper(), datei
