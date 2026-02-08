import sys
from unittest.mock import MagicMock

# Create mock modules for Kodi
mock_modules = [
    "xbmc",
    "xbmcgui",
    "xbmcaddon",
    "xbmcvfs",
    "pydevd",  # Sometimes used in debugging
]

for module in mock_modules:
    sys.modules[module] = MagicMock()

# Mock specific attributes if needed
import xbmcgui

xbmcgui.ListItem = MagicMock
xbmcgui.Dialog = MagicMock
xbmcgui.DialogProgressBG = MagicMock
