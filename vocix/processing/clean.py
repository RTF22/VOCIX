import re

from vocix.processing.base import TextProcessor

# Deutsche Füllwörter und Hesitationslaute.
# Reihenfolge: Mehrwort-Phrasen vor Einzelwörtern — Python's re.sub verwendet
# leftmost match, die längere Variante muss in der Alternation zuerst stehen,
# damit z.B. "halt so" als ganze Phrase erkannt wird und nicht nur "halt".
_FILLER_WORDS = [
    r"\bim\s+Grunde\s+genommen\b",
    r"\bsagen\s+wir\s+mal\b",
    r"\bsag\s+ich\s+mal\b",
    r"\bja\s+also\b",
    r"\bim\s+Prinzip\b",
    r"\bhalt\s+so\b",
    r"\bäh+m?\b", r"\bhm+\b", r"\bumm?\b",
    r"\bnaja\b", r"\btja\b", r"\bhalt\b",
    r"\bsozusagen\b", r"\bquasi\b", r"\birgendwie\b",
    r"\bgrundsätzlich\b", r"\beigentlich\b",
    r"\balso\b",
    r"\bgenau\b", r"\beben\b",
]

_FILLER_PATTERN = re.compile(
    "|".join(_FILLER_WORDS), re.IGNORECASE
)


class CleanProcessor(TextProcessor):
    """Modus A: Saubere Transkription mit Füllwort-Entfernung."""

    @property
    def name(self) -> str:
        return "Clean"

    def process(self, text: str) -> str:
        if not text.strip():
            return text

        # Füllwörter entfernen
        result = _FILLER_PATTERN.sub("", text)

        # Mehrfache Leerzeichen normalisieren
        result = re.sub(r" {2,}", " ", result)

        # Leerzeichen vor Satzzeichen entfernen
        result = re.sub(r"\s+([.,;:!?])", r"\1", result)

        # Füllwort-Entfernung kann führende Satzzeichen hinterlassen,
        # z.B. "Eigentlich, das ist gut" → ", das ist gut". Führende
        # Kommas/Semikola am Text- und Zeilenanfang bereinigen.
        result = re.sub(r"(^|\n)\s*[,;:]\s*", r"\1", result)

        # Doppelte Kommas entfernen (entstehen durch Phrasen mitten im Satz)
        result = re.sub(r",\s*,+", ",", result)

        # Satzanfänge großschreiben
        result = re.sub(r"(^|[.!?]\s+)(\w)", lambda m: m.group(1) + m.group(2).upper(), result)

        # Führende/trailing Leerzeichen pro Zeile
        result = "\n".join(line.strip() for line in result.split("\n"))

        # Sicherstellen, dass der erste Buchstabe groß ist
        if result and result[0].isalpha():
            result = result[0].upper() + result[1:]

        return result.strip()
