from vocix.config import Config
from vocix.processing.llm_backed import LLMBackedProcessor


class RageProcessor(LLMBackedProcessor):
    """Modus C: Deeskalation — aggressiv → höflich."""

    def __init__(self, config: Config):
        super().__init__(config, name="Rage", prompt_key="prompt.rage", mode="rage")
