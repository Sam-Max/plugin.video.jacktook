import sys
import os
from unittest.mock import MagicMock

# 1. Mock Kodi Modules before and during imports
mock_xbmc = MagicMock()
mock_xbmcgui = MagicMock()
mock_xbmcaddon = MagicMock()
mock_xbmcvfs = MagicMock()
mock_xbmcplugin = MagicMock()

sys.modules["xbmc"] = mock_xbmc
sys.modules["xbmcgui"] = mock_xbmcgui
sys.modules["xbmcaddon"] = mock_xbmcaddon
sys.modules["xbmcvfs"] = mock_xbmcvfs
sys.modules["xbmcplugin"] = mock_xbmcplugin

# 2. Add current directory to path so we can import 'lib'
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


# 3. Create a mock for kodi utils and DB
def mock_kodilog(message, level=None):
    print(f"[LOG] {message}")


def mock_notification(message, header="Jacktook", time=5000, icon=""):
    print(f"[NOTIFICATION] {header}: {message}")


def mock_translation(id):
    return f"String_{id}"


def mock_get_setting(id, default=""):
    return default


# Mock the entire utils module
utils_mock = MagicMock()
utils_mock.kodilog = mock_kodilog
utils_mock.notification = mock_notification
utils_mock.translation = mock_translation
utils_mock.get_setting = mock_get_setting
sys.modules["lib.utils.kodi.utils"] = utils_mock

# Mock the cache module to prevent SQL errors
cache_mock = MagicMock()
sys.modules["lib.db.cached"] = cache_mock

# Mock TVDBAPI as well since it triggers the imports
sys.modules["lib.api.tvdbapi.tvdbapi"] = MagicMock()
sys.modules["lib.api.tvdbapi"] = MagicMock()

# 4. Now import the clients
from lib.api.debrid.realdebrid import RealDebrid
from lib.api.debrid.alldebrid import AllDebrid
from lib.api.debrid.torbox import Torbox
from lib.api.debrid.premiumize import Premiumize
from lib.api.debrid.debrider import Debrider

# === CONFIGURATION: ADD YOUR TOKENS HERE ===
TOKENS = {
    "REALDEBRID": "",  # Real-Debrid API Key
    "ALLDEBRID": "",  # AllDebrid API Key
    "TORBOX": "",  # Torbox API Key
    "PREMIUMIZE": "",  # Premiumize API Key
    "DEBRIDER": "",  # Debrider API Key
}
# ===========================================


def test_service(name, client_class, token):
    print(f"\n--- Testing {name} ---")
    if not token:
        print(f"Skipping {name}: No token provided.")
        return

    try:
        # Special case for Premiumize which might need different params if it changed,
        # but let's try standard first based on current code
        client = client_class(token)
        days = client.days_remaining()
        if days is not None:
            print(f"SUCCESS: {name} reports {days} days remaining.")
        else:
            print(
                f"FAILED: {name} returned None. Check if token is valid or if account has premium."
            )
    except Exception as e:
        print(f"ERROR testing {name}: {str(e)}")


if __name__ == "__main__":
    print("Jacktook Debrid Expiration Verification Tool")
    print("============================================")

    test_service("Real-Debrid", RealDebrid, TOKENS["REALDEBRID"])
    test_service("AllDebrid", AllDebrid, TOKENS["ALLDEBRID"])
    test_service("Torbox", Torbox, TOKENS["TORBOX"])
    test_service("Premiumize", Premiumize, TOKENS["PREMIUMIZE"])
    test_service("Debrider", Debrider, TOKENS["DEBRIDER"])
