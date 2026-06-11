from vocix.config import Config
from vocix.processing.llm_backed import LLMBackedProcessor
from vocix.processing.passthrough import PassthroughProcessor


class LatexProcessor(LLMBackedProcessor):
    """Modus L: Gesprochene Mathematik in LaTeX-Notation einbetten.

    Fließtext bleibt unverändert; nur erkannte Formeln/Mathe-Ausdrücke
    werden in $...$ (inline) bzw. $$...$$ (Display) gewrappt. Bei
    Provider-Fehler wird die Whisper-Rohtranskription durchgereicht
    (nicht Clean — würde Mathe-Aussprache verfälschen).
    """

    def __init__(self, config: Config):
        super().__init__(
            config,
            name="LaTeX",
            prompt_key="prompt.latex",
            mode="latex",
            fallback_processor=PassthroughProcessor(),
        )
