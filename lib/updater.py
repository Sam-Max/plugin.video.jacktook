# -*- coding: utf-8 -*-
import shutil
import requests
from os import path as ospath
from xbmcvfs import translatePath as translate_path

from lib.utils.kodi.utils import (
    ADDON_VERSION, notification, dialog_ok, dialogyesno, close_all_dialog,
    execute_builtin, delete_file, update_local_addons, disable_enable_addon,
    update_kodi_addons_db, dialog_text
)
from lib.utils.general.utils import clear_cache_on_update, unzip
from lib.utils.kodi.settings import cache_clear_update


# =========================
# Constants
# =========================
ADDON_ID = "plugin.video.jacktook"
ADDON_NAME = "Jacktook"
HEADING = f"{ADDON_NAME} Updater"

PACKAGES_DIR = translate_path("special://home/addons/packages/")
HOME_ADDONS_DIR = translate_path("special://home/addons/")
DESTINATION_DIR = translate_path(f"special://home/addons/{ADDON_ID}/")
CHANGELOG_PATH = translate_path(f"special://home/addons/{ADDON_ID}/CHANGELOG.md")

BASE_REPO_URL = "https://github.com/Sam-Max/repository.jacktook/raw/main/packages"
BASE_ZIP_URL = "https://raw.githubusercontent.com/Sam-Max/repository.jacktook/main/repo/zips"

VERSION_FILE = f"{BASE_REPO_URL}/jacktook_version"
CHANGELOG_FILE = f"{BASE_REPO_URL}/jacktook_changelog"

# =========================
# Helpers
# =========================
def http_get(url, stream=False):
    """Make a GET request and return text or raw stream."""
    try:
        resp = requests.get(url, stream=stream)
        resp.raise_for_status()
        return resp.text if not stream else resp.raw
    except requests.RequestException as e:
        notification(f"HTTP Error: {e}")
        return None

def get_versions():
    """Return (current_version, online_version) or (None, None) on failure."""
    online_version = http_get(VERSION_FILE)
    if not online_version:
        return None, None
    return ADDON_VERSION, online_version.strip()

def get_changes(online_version=None):
    """Display changelog (online if version passed, else local)."""
    if online_version:
        changelog = http_get(CHANGELOG_FILE)
        if changelog:
            dialog_text(f"New Release v{online_version} - Changelog", changelog)
    else:
        dialog_text("Changelog", file=CHANGELOG_PATH)

# =========================
# Core Update Logic
# =========================
def update_addon(new_version, action):
    if cache_clear_update():
        clear_cache_on_update()

    close_all_dialog()
    execute_builtin("ActivateWindow(Home)", True)

    zip_name = f"{ADDON_ID}-{new_version}.zip"
    zip_url = f"{BASE_ZIP_URL}/{ADDON_ID}/{zip_name}"
    zip_path = ospath.join(PACKAGES_DIR, zip_name)

    # Download new version
    raw_data = http_get(zip_url, stream=True)
    if not raw_data:
        return dialog_ok(heading=HEADING, line1="Error: Unable to download update.")

    with open(zip_path, "wb") as f:
        shutil.copyfileobj(raw_data, f)

    # Remove old addon
    if ospath.exists(DESTINATION_DIR):
        shutil.rmtree(DESTINATION_DIR)

    # Extract
    if not unzip(zip_path, HOME_ADDONS_DIR, DESTINATION_DIR):
        delete_file(zip_path)
        return dialog_ok(heading=HEADING, line1="Error updating. Please install manually.")

    delete_file(zip_path)

    # Success message & changelog
    if action in (0, 4):
        if dialog_ok(heading=HEADING, line1=f"Updated to v{new_version}") is not False:
            get_changes()

    # Refresh Kodi addon system
    update_local_addons()
    disable_enable_addon()
    update_kodi_addons_db()

# =========================
# Entry Point
# =========================
def updates_check_addon(action=4):
    """Main updater entry point."""
    if action == 3:
        return

    current_version, online_version = get_versions()
    if not current_version:
        return

    msg = f"Installed: [B]{current_version}[/B][CR]Online: [B]{online_version}[/B][CR][CR]"

    if current_version == online_version:
        if action == 4:
            dialog_ok(heading=HEADING, line1=msg + "[B]No Update Available[/B]")
        return

    if action in (0, 4) and not dialogyesno(
        header=HEADING, text=msg + "[B]Update available[/B][CR]Do you want to update?"
    ):
        return

    if action == 1:
        notification("Updating...")
    elif action == 2:
        notification(f"{ADDON_NAME} Update Available")
        return

    update_addon(online_version, action)
