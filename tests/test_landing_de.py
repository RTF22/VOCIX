"""Die deutsche Landingpage docs/de/index.html muss zum Generator-Output passen."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("build_landing_de", ROOT / "scripts" / "build_landing_de.py")
assert _spec is not None and _spec.loader is not None
build_landing_de = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_landing_de)


def _build() -> str:
    en_page = build_landing_de.EN_PAGE.read_text(encoding="utf-8")
    data = json.loads(build_landing_de.DE_STRINGS.read_text(encoding="utf-8"))
    return build_landing_de.build(en_page, data)


def test_de_page_is_up_to_date():
    committed = build_landing_de.DE_PAGE.read_text(encoding="utf-8")
    assert committed == _build(), "python scripts/build_landing_de.py ausführen"


def test_de_page_is_german_and_self_canonical():
    page = _build()
    assert '<html lang="de">' in page
    assert '<link rel="canonical" href="https://vocix.de/de/">' in page
    assert 'href="../vocix-tokens.css"' in page
    assert 'hreflang="de" lang="de" aria-current="page">DE</a>' in page


def test_replace_i18n_handles_nested_tags():
    page = '<div data-i18n="a">x <span>y</span> z</div><p data-i18n="b">old</p>'
    new, unused = build_landing_de.replace_i18n(page, {"a": "A<span>B</span>", "b": "B", "c": "C"})
    assert new == '<div data-i18n="a">A<span>B</span></div><p data-i18n="b">B</p>'
    assert unused == ["c"]
