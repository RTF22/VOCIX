from vocix.config import Config
from vocix.processing.claude_base import ClaudeProcessor


class RageProcessor(ClaudeProcessor):
    """Modus C: Deeskalation — aggressiv → höflich (Claude API)."""

    def __init__(self, config: Config):
        super().__init__(config, name="Rage", prompt_key="prompt.rage")
