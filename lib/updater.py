import requests

from lib.utils.kodi.utils import (
    ADDON_VERSION,
    close_busy_dialog,
    dialog_ok,
    dialog_text,
    dialogyesno,
    execute_builtin,
    kodilog,
    notification,
    show_busy_dialog,
    translation,
)

# =========================
# Constants
# =========================
ADDON_ID = "plugin.video.jacktook"
ADDON_NAME = "Jacktook"
HEADING = f"{ADDON_NAME} Updater"

CHANGELOG_PATH = f"special://home/addons/{ADDON_ID}/CHANGELOG.md"

BASE_REPO_URL = "https://github.com/Sam-Max/repository.jacktook/raw/main/packages"

VERSION_FILE = f"{BASE_REPO_URL}/jacktook_version"
CHANGELOG_FILE = f"{BASE_REPO_URL}/jacktook_changelog"

UPDATE_ACTION_ASK = 0
UPDATE_ACTION_NOTIFY = 1
UPDATE_ACTION_NONE = 2


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
    show_busy_dialog()
    online_version = http_get(VERSION_FILE)
    close_busy_dialog()
    if not online_version:
        return None, None
    return ADDON_VERSION, online_version.strip()


def version_less_than(v1, v2):
    """Return True if v1 < v2 using numeric comparison."""
    try:
        import re

        def normalize(v):
            return [int(x) for x in re.sub(r"[^0-9.]", "", v).split(".")]

        return normalize(v1) < normalize(v2)
    except Exception:
        return v1 < v2


def get_changes(online_version=None):
    """Display changelog (online if version passed, else local)."""
    if online_version:
        changelog = http_get(CHANGELOG_FILE)
        if changelog:
            dialog_text(translation(90592) % online_version, str(changelog))
    else:
        dialog_text(translation(90577), file=CHANGELOG_PATH)


# =========================
# Entry Point
# =========================
def updates_check_addon(automatic=False):
    kodilog("Checking for updates...")
    current_version, online_version = get_versions()
    if not current_version or not online_version:
        kodilog("Failed to fetch versions for update check.")
        if not automatic:
            dialog_ok(heading=HEADING, line1=translation(90578))
        return

    kodilog(f"Update check - Current: {current_version}, Online: {online_version}")

    msg = translation(90580) % (current_version, online_version)

    if current_version == online_version:
        kodilog("No update available.")
        if not automatic:
            notification(heading=HEADING, message=translation(90579))
        return

    if version_less_than(online_version, current_version):
        kodilog("Installed version is newer than the repository version.")
        if not automatic:
            notification(heading=HEADING, message=translation(90964))
        return

    if version_less_than(current_version, online_version):
        kodilog("Newer version available.")
        if not automatic:
            if not dialogyesno(
                header=HEADING,
                text=msg + translation(90581),
            ):
                return
            update_addon(online_version)
        else:
            from lib.utils.kodi.settings import get_update_action

            action = get_update_action()
            if action == UPDATE_ACTION_ASK:
                if dialogyesno(
                    header=HEADING,
                    text=msg + translation(90581),
                ):
                    update_addon(online_version)
            elif action == UPDATE_ACTION_NOTIFY:
                notification(
                    heading=HEADING,
                    message=translation(90582) % online_version,
                )
            elif action == UPDATE_ACTION_NONE:
                return


def update_addon(new_version):
    kodilog(f"Requesting Kodi update to version: {new_version}")
    execute_builtin("UpdateAddonRepos", True)
    execute_builtin(f"InstallAddon({ADDON_ID})")
