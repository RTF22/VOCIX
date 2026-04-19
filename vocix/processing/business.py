from vocix.config import Config
from vocix.processing.claude_base import ClaudeProcessor


class BusinessProcessor(ClaudeProcessor):
    """Modus B: Professionelle Geschäftssprache via Claude API."""

    def __init__(self, config: Config):
        super().__init__(config, name="Business", prompt_key="prompt.business")
