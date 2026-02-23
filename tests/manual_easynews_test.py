import sys
import os
from unittest.mock import MagicMock

# --- Mock Kodi modules before importing lib ---
mock_xbmc = MagicMock()
mock_xbmc.LOGINFO = 1
mock_xbmc.LOGERROR = 3
sys.modules["xbmc"] = mock_xbmc

mock_xbmcgui = MagicMock()
sys.modules["xbmcgui"] = mock_xbmcgui

mock_xbmcaddon = MagicMock()
sys.modules["xbmcaddon"] = mock_xbmcaddon

# --- Mock sqlite3 to avoid DB initialization errors ---
import sqlite3

sqlite3.connect = MagicMock(return_value=MagicMock())

mock_xbmcplugin = MagicMock()
sys.modules["xbmcplugin"] = mock_xbmcplugin

mock_xbmcvfs = MagicMock()
mock_xbmcvfs.translatePath.return_value = ":memory:"
sys.modules["xbmcvfs"] = mock_xbmcvfs

# --- Mock kodi utils ---
mock_kodi_utils = MagicMock()
mock_kodi_utils.dialog_text = lambda title, body: print(
    f"\n[DIALOG: {title}]\n{body}\n"
)
mock_kodi_utils.kodilog = lambda msg, level=1: print(f"[LOG] {msg}")
sys.modules["lib.utils.kodi.utils"] = mock_kodi_utils

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def mock_notification(msg):
    print(f"[NOTIFICATION] {msg}")


# Now we can import our client
try:
    from lib.clients.easynews import Easynews
except ImportError as e:
    print(f"Error importing Easynews: {e}")
    sys.exit(1)


def main():
    print("=== Easynews Manual Test Script ===")
    user = input("Enter Easynews Username: ").strip()
    password = input("Enter Easynews Password: ").strip()

    if not user or not password:
        print("Username and Password are required.")
        return

    # Initialize client
    client = Easynews(user, password, timeout=20, notification=mock_notification)

    print("\n--- Testing Account Info (get_info) ---")
    try:
        client.get_info()
    except Exception as e:
        print(f"Error during get_info: {e}")

    print("\n--- Testing Search (Query: 'Firebreak') ---")
    try:
        results = client.search("Firebreak", mode="movie", media_type="movie")
        print(f"Found {len(results)} results.")
        for i, res in enumerate(results[:5]):
            print(f"{i+1}. {res.title} ({res.quality}) - {res.size // (1024*1024)} MB")
            print(f"   URL: {res.url[:80]}...")

            if i == 0:
                print("\n--- Testing URL Resolve (First Result) ---")
                resolved = client.resolve_url(res.url)
                print(f"Resolved URL: {resolved}")
    except Exception as e:
        print(f"Error during search: {e}")


if __name__ == "__main__":
    main()
