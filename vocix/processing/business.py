from vocix.config import Config
from vocix.processing.llm_backed import LLMBackedProcessor


class BusinessProcessor(LLMBackedProcessor):
    """Modus B: Professionelle Geschäftssprache."""

    def __init__(self, config: Config):
        super().__init__(config, name="Business", prompt_key="prompt.business", mode="business")
