from unittest.mock import MagicMock

from vocix.ui.tray import TrayApp


def test_tray_calls_open_settings_callback():
    on_open = MagicMock()
    tray = TrayApp.__new__(TrayApp)
    tray._on_open_settings = on_open
    tray._invoke_open_settings()
    on_open.assert_called_once()


def test_tray_invoke_settings_handles_missing_callback():
    tray = TrayApp.__new__(TrayApp)
    tray._on_open_settings = None
    # Sollte nicht crashen
    tray._invoke_open_settings()
