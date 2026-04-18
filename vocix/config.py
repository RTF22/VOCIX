import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _get_app_dir() -> Path:
    """Gibt das Anwendungsverzeichnis zurück — funktioniert sowohl als Script als auch als .exe."""
    if getattr(sys, "frozen", False):
        # PyInstaller .exe: Verzeichnis der .exe
        return Path(sys.executable).resolve().parent
    # Normaler Python-Aufruf: Projektverzeichnis (eine Ebene über vocix/)
    return Path(__file__).resolve().parent.parent


APP_DIR = _get_app_dir()


def _get_state_file() -> Path:
    """Pfad zur persistenten State-Datei für User-Einstellungen (z.B. übersprungene Update-Versionen)."""
    appdata = os.getenv("APPDATA")
    base = Path(appdata) if appdata else APP_DIR
    return base / "VOCIX" / "state.json"


STATE_FILE = _get_state_file()


def load_state() -> dict:
    """Lädt persistenten State. Liefert {} bei Fehlern oder fehlender Datei."""
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("State-Datei konnte nicht gelesen werden: %s", e)
    return {}


def save_state(state: dict) -> None:
    """Schreibt State-Dict nach STATE_FILE. Fehler werden geloggt, nicht geraised."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning("State-Datei konnte nicht gespeichert werden: %s", e)


@dataclass
class Config:
    # Whisper
    whisper_model: str = "small"
    whisper_language: str = "de"
    whisper_model_dir: str = field(default_factory=lambda: os.getenv(
        "VOCIX_MODEL_DIR", str(APP_DIR / "models")
    ))

    # Audio
    sample_rate: int = 16000
    channels: int = 1
    silence_threshold: float = 0.01  # RMS unter diesem Wert = Stille
    min_duration: float = 0.5        # Mindestaufnahmelänge in Sekunden

    # Hotkeys (konfigurierbar via .env — Werte wie von der 'keyboard'-Library erwartet)
    # Einzeltaste oder Kombination, z.B.: "right ctrl", "ctrl+shift+space", "f9"
    hotkey_record: str = field(default_factory=lambda: os.getenv("VOCIX_HOTKEY_RECORD", "f9"))
    hotkey_mode_a: str = field(default_factory=lambda: os.getenv("VOCIX_HOTKEY_MODE_A", "ctrl+shift+1"))
    hotkey_mode_b: str = field(default_factory=lambda: os.getenv("VOCIX_HOTKEY_MODE_B", "ctrl+shift+2"))
    hotkey_mode_c: str = field(default_factory=lambda: os.getenv("VOCIX_HOTKEY_MODE_C", "ctrl+shift+3"))

    # Modus: "clean", "business", "rage"
    default_mode: str = "clean"

    # Anthropic
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    anthropic_model: str = "claude-sonnet-4-20250514"
    anthropic_timeout: float = 15.0  # Sekunden — bei Timeout Fallback auf Clean-Modus

    # RDP / Remote Desktop
    rdp_mode: bool = field(default_factory=lambda: os.getenv("VOCIX_RDP_MODE", "").lower() in ("1", "true", "yes"))
    clipboard_delay: float = 0.05   # Sekunden — in RDP auf 0.15-0.3 erhöhen
    paste_delay: float = 0.1        # Sekunden — in RDP auf 0.3-0.5 erhöhen

    # Logging
    log_level: str = field(default_factory=lambda: os.getenv("VOCIX_LOG_LEVEL", "INFO").upper())
    log_file: str = field(default_factory=lambda: os.getenv(
        "VOCIX_LOG_FILE", str(APP_DIR / "vocix.log")
    ))

    # UI
    overlay_display_seconds: float = 1.5

    def __post_init__(self):
        if self.rdp_mode:
            # Längere Delays für RDP-Clipboard-Synchronisation
            if self.clipboard_delay < 0.15:
                self.clipboard_delay = 0.2
            if self.paste_delay < 0.3:
                self.paste_delay = 0.4

        # PTT erfordert eine Einzeltaste — Kombinationen sind nicht zuverlässig
        # hold-to-record-fähig (siehe ADR 004). mode_a/b/c sind davon nicht
        # betroffen, die nutzen keyboard.add_hotkey statt Press/Release-Hooks.
        if "+" in self.hotkey_record:
            raise ValueError(
                f"VOCIX_HOTKEY_RECORD={self.hotkey_record!r} enthält '+' — "
                f"Push-to-Talk benötigt eine Einzeltaste (z.B. 'f9', 'f13', "
                f"'right shift'). Siehe .docs/DECISIONS.md ADR 004. "
                f"Default ist 'f9'."
            )

    @classmethod
    def load(cls, env_file: Path | str | None = None) -> "Config":
        """Lädt die .env-Datei und erzeugt Config aus der resultierenden Umgebung.

        Priorität: Prozess-Env schlägt .env-Werte (dotenv-Default `override=False`).
        Tests können stattdessen `Config(...)` direkt aufrufen und die Felder
        explizit setzen, ohne Dateisystem-Nebeneffekte.
        """
        path = Path(env_file) if env_file is not None else APP_DIR / ".env"
        if path.exists():
            load_dotenv(path)
        return cls()
