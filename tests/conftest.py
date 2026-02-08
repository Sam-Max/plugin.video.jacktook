import sys
import os
from unittest.mock import MagicMock

# Setup Kodi mocking BEFORE adding lib to sys.path
mock_modules = ["xbmc", "xbmcgui", "xbmcaddon", "xbmcvfs", "xbmcplugin", "pydevd"]

for module in mock_modules:
    sys.modules[module] = MagicMock()

# Configure specific mock behaviors
import xbmc

xbmc.getSupportedMedia.return_value = ".mp4|.mkv|.avi|.ts|.m2ts"

# Mock sys.argv to simulate Kodi addon arguments
sys.argv = ["plugin.video.jacktook", "1", "/", ""]

# Mock sqlite3.connect to avoid side effects during module imports
import sqlite3

sqlite3.connect = MagicMock(return_value=MagicMock())

# Add the project root to sys.path to allow importing lib
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
