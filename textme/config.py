import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# .env aus dem Projektverzeichnis laden
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")


@dataclass
class Config:
    # Whisper
    whisper_model: str = "small"
    whisper_language: str = "de"

    # Audio
    sample_rate: int = 16000
    channels: int = 1
    silence_threshold: float = 0.01  # RMS unter diesem Wert = Stille
    min_duration: float = 0.5        # Mindestaufnahmelänge in Sekunden

    # Hotkeys (konfigurierbar via .env — Werte wie von der 'keyboard'-Library erwartet)
    # Einzeltaste oder Kombination, z.B.: "right ctrl", "ctrl+shift+space", "f9"
    hotkey_record: str = field(default_factory=lambda: os.getenv("DICTUM_HOTKEY_RECORD", "right ctrl"))
    hotkey_mode_a: str = field(default_factory=lambda: os.getenv("DICTUM_HOTKEY_MODE_A", "ctrl+shift+1"))
    hotkey_mode_b: str = field(default_factory=lambda: os.getenv("DICTUM_HOTKEY_MODE_B", "ctrl+shift+2"))
    hotkey_mode_c: str = field(default_factory=lambda: os.getenv("DICTUM_HOTKEY_MODE_C", "ctrl+shift+3"))

    # Modus: "clean", "business", "rage"
    default_mode: str = "clean"

    # Anthropic
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    anthropic_model: str = "claude-sonnet-4-20250514"

    # RDP / Remote Desktop
    rdp_mode: bool = field(default_factory=lambda: os.getenv("DICTUM_RDP_MODE", "").lower() in ("1", "true", "yes"))
    clipboard_delay: float = 0.05   # Sekunden — in RDP auf 0.15-0.3 erhöhen
    paste_delay: float = 0.1        # Sekunden — in RDP auf 0.3-0.5 erhöhen

    # UI
    overlay_display_seconds: float = 1.5

    def __post_init__(self):
        if self.rdp_mode:
            # Längere Delays für RDP-Clipboard-Synchronisation
            if self.clipboard_delay < 0.15:
                self.clipboard_delay = 0.2
            if self.paste_delay < 0.3:
                self.paste_delay = 0.4
