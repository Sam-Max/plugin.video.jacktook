import sys
import os
from unittest.mock import MagicMock

# --- Create stub classes for xbmcgui to avoid type hint issues in Python 3.13 ---
# Python 3.13 evaluates type hints at class definition time.
# If xbmcgui.WindowXMLDialog is a MagicMock, using Optional[SomeClass] where
# SomeClass inherits from it will break.


class _XbmcguiStub:
    """Stub module for xbmcgui with real classes for inheritance."""

    class Window:
        def __init__(self, *args, **kwargs):
            pass

        def show(self):
            pass

        def close(self):
            pass

        def setProperty(self, key, value):
            pass

        def getProperty(self, key):
            return ""

        def setFocus(self, control):
            pass

        def setFocusId(self, control_id):
            pass

        def getFocus(self):
            return MagicMock()

        def getFocusId(self):
            return 0

        def getControl(self, control_id):
            return MagicMock()

        def doModal(self):
            pass

    class WindowXML(Window):
        def __init__(self, *args, **kwargs):
            pass

    class WindowXMLDialog(Window):
        def __init__(self, *args, **kwargs):
            pass

    class Dialog:
        def ok(self, *args, **kwargs):
            return True

        def yesno(self, *args, **kwargs):
            return True

        def select(self, *args, **kwargs):
            return 0

        def notification(self, *args, **kwargs):
            pass

        def textviewer(self, *args, **kwargs):
            pass

        def input(self, *args, **kwargs):
            return ""

        def browse(self, *args, **kwargs):
            return ""

    class DialogProgress:
        def create(self, *args, **kwargs):
            pass

        def update(self, *args, **kwargs):
            pass

        def close(self):
            pass

        def iscanceled(self):
            return False

    class DialogProgressBG:
        def create(self, *args, **kwargs):
            pass

        def update(self, *args, **kwargs):
            pass

        def close(self):
            pass

        def isFinished(self):
            return False

    class ListItem:
        def __init__(self, *args, **kwargs):
            pass

        def setLabel(self, label):
            pass

        def setLabel2(self, label):
            pass

        def setInfo(self, *args, **kwargs):
            pass

        def setArt(self, *args, **kwargs):
            pass

        def setProperty(self, key, value):
            pass

        def getProperty(self, key):
            return ""

        def setPath(self, path):
            pass

        def getPath(self):
            return ""

        def setSubtitles(self, subtitleFiles):
            pass

        def addStreamInfo(self, cType, values):
            pass

        def addContextMenuItems(self, items):
            pass

    class ControlList:
        def addItem(self, item):
            pass

        def addItems(self, items):
            pass

        def selectItem(self, item):
            pass

        def getSelectedItem(self):
            return MagicMock()

        def getSelectedPosition(self):
            return 0

        def size(self):
            return 0

        def reset(self):
            pass

    class ControlProgress:
        def setPercent(self, percent):
            pass

        def getPercent(self):
            return 0.0

    # Fallback for any other attributes
    def __getattr__(self, name):
        return MagicMock()


# --- Create mock modules ---
xbmc_mock = MagicMock()
xbmc_mock.getSupportedMedia.return_value = ".mp4|.mkv|.avi|.ts|.m2ts"
xbmc_mock.LOGDEBUG = 0
xbmc_mock.LOGINFO = 1
xbmc_mock.LOGWARNING = 2
xbmc_mock.LOGERROR = 3

sys.modules["xbmc"] = xbmc_mock
sys.modules["xbmcgui"] = _XbmcguiStub()
sys.modules["xbmcaddon"] = MagicMock()
sys.modules["xbmcvfs"] = MagicMock()
sys.modules["xbmcplugin"] = MagicMock()
sys.modules["pydevd"] = MagicMock()

# Mock sys.argv to simulate Kodi addon arguments
sys.argv = ["plugin.video.jacktook", "1", "/", ""]

# Mock sqlite3.connect to avoid side effects during module imports
import sqlite3

sqlite3.connect = MagicMock(return_value=MagicMock())

# Add the project root to sys.path to allow importing lib
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
