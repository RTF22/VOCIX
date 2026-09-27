"""Impressum auf vocix.de: Inhalt wie jensfricke.com/impressum, ohne JavaScript erreichbar, Anschrift nicht im HTML."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
SEITEN = {
    "en": (DOCS / "index.html", "https://jensfricke.com/en/legal-notice/", "https://jensfricke.com/en/privacy/vocix/"),
    "de": (DOCS / "de" / "index.html", "https://jensfricke.com/impressum/", "https://jensfricke.com/datenschutz/vocix/"),
}
PLZ_ORT = re.compile(r"\b\d{5} [A-ZÄÖÜ][a-zäöüß]+")


def _css_klartext(css: str) -> dict[str, str]:
    """Inhalt der content-Angaben je Klasse, CSS-Escapes aufgelöst wie im Browser."""
    werte = dict(re.findall(r"\.(anschrift-\w+)::before \{ content: \"([^\"]*)\"; \}", css))
    return {
        k: re.sub(r"\\([0-9a-f]{1,6}) ?", lambda m: chr(int(m.group(1), 16)), v, flags=re.I) for k, v in werte.items()
    }


def test_footer_verlinkt_impressum_und_datenschutz_ohne_javascript():
    for sprache, (seite, impressum, datenschutz) in SEITEN.items():
        html = seite.read_text(encoding="utf-8")
        assert re.search(rf'<a class="footer-link" href="{re.escape(impressum)}" onclick="event.preventDefault\(\);', html), sprache
        assert f'<a class="footer-link" href="{datenschutz}"' in html, sprache


def test_impressum_nennt_ddg_und_kontaktadresse_der_domain():
    for sprache, (seite, _, _) in SEITEN.items():
        html = seite.read_text(encoding="utf-8")
        assert "§ 5 DDG" in html and "MStV" in html, sprache
        assert "TMG" not in html, sprache
        assert "mailto:kontakt@jensfricke.com" in html, sprache
        assert "gmail.com" not in html, sprache


def test_anschrift_steht_nur_in_adresse_css():
    for sprache, (seite, _, _) in SEITEN.items():
        html = seite.read_text(encoding="utf-8")
        assert 'class="anschrift-strasse"' in html and 'class="anschrift-ort"' in html, sprache
        assert "assets/adresse.css" in html, sprache
        assert not PLZ_ORT.search(html), sprache
    css = (DOCS / "assets" / "adresse.css").read_text(encoding="utf-8")
    assert not PLZ_ORT.search(css), "Anschrift steht im Klartext in adresse.css"
    klar = _css_klartext(css)
    assert re.fullmatch(r".+ \d+[a-z]?", klar["anschrift-strasse"]), klar
    assert PLZ_ORT.fullmatch(klar["anschrift-ort"]), klar


def test_robots_sperrt_adresse_css():
    assert re.search(r"^Disallow: /assets/adresse\.css$", (DOCS / "robots.txt").read_text(encoding="utf-8"), re.M)
