# -*- coding: utf-8 -*-
import shutil
import requests
import os
from zipfile import ZipFile, BadZipFile
import xml.etree.ElementTree as ET
import xbmc
from xbmcvfs import translatePath as translate_path

from lib.utils.kodi.utils import (
    ADDON_VERSION,
    notification,
    dialog_ok,
    dialogyesno,
    close_all_dialog,
    execute_builtin,
    delete_file,
    update_local_addons,
    disable_enable_addon,
    update_kodi_addons_db,
    dialog_text,
    dialog_select,
    show_busy_dialog,
    close_busy_dialog,
    kodilog,
    translation,
)
from lib.utils.general.utils import unzip


# =========================
# Constants
# =========================
ADDON_ID = "plugin.video.jacktook"
ADDON_NAME = "Jacktook"
HEADING = f"{ADDON_NAME} Updater"

PACKAGES_DIR = translate_path("special://home/addons/packages/")
HOME_ADDONS_DIR = translate_path("special://home/addons/")
DESTINATION_DIR = translate_path(f"special://home/addons/{ADDON_ID}")
CHANGELOG_PATH = translate_path(f"special://home/addons/{ADDON_ID}/CHANGELOG.md")

BASE_REPO_URL = "https://github.com/Sam-Max/repository.jacktook/raw/main/packages"
BASE_ZIP_URL = (
    "https://raw.githubusercontent.com/Sam-Max/repository.jacktook/main/repo/zips"
)

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


def _safe_remove_path(path):
    if not os.path.lexists(path):
        return

    if os.path.islink(path):
        os.unlink(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def _read_addon_version_from_xml(xml_path):
    tree = ET.parse(xml_path)
    return tree.getroot().attrib.get("version")


def _validate_downloaded_zip(zip_path, expected_version):
    addon_xml = f"{ADDON_ID}/addon.xml"

    try:
        with ZipFile(zip_path) as zip_file:
            names = zip_file.namelist()
            if addon_xml not in names:
                raise ValueError("addon.xml missing from update package")

            xml_data = zip_file.read(addon_xml)
    except (BadZipFile, KeyError, ValueError) as exc:
        raise ValueError(str(exc))

    try:
        version = ET.fromstring(xml_data).attrib.get("version")
    except ET.ParseError as exc:
        raise ValueError(f"Invalid addon.xml: {exc}")

    if version != expected_version:
        raise ValueError(
            "Package version mismatch: expected %s, found %s"
            % (expected_version, version)
        )


def _validate_installed_version(destination_dir, expected_version):
    addon_xml_path = os.path.join(destination_dir, "addon.xml")
    if not os.path.exists(addon_xml_path):
        raise ValueError("Installed addon.xml not found after update")

    version = _read_addon_version_from_xml(addon_xml_path)
    if version != expected_version:
        raise ValueError(
            "Installed version mismatch: expected %s, found %s"
            % (expected_version, version)
        )


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


# =========================
# Core Update Logic
# =========================


def downgrade_addon_menu():
    """Fetch available versions from GitHub and display them in a selection dialog."""
    repo_contents_url = "https://api.github.com/repos/Sam-Max/repository.jacktook/contents/repo/zips/plugin.video.jacktook"
    try:
        resp = requests.get(repo_contents_url)
        resp.raise_for_status()
        contents = resp.json()
    except Exception as e:
        dialog_ok(heading=HEADING, line1=translation(90583) % e)
        return

    # Extract versions from zip filenames: plugin.video.jacktook-X.Y.Z.zip
    versions = []
    prefix = f"{ADDON_ID}-"
    suffix = ".zip"
    for item in contents:
        name = item.get("name", "")
        if name.startswith(prefix) and name.endswith(suffix):
            version_str = name[len(prefix) : -len(suffix)]
            versions.append(version_str)

    kodilog(f"Available versions found: {versions}")

    # Downgrade should only offer versions older than the installed one.
    versions = [v for v in versions if version_less_than(v, ADDON_VERSION)]

    if not versions:
        dialog_ok(heading=HEADING, line1=translation(90584))
        return

    # Sort versions
    try:
        from pkg_resources import parse_version

        versions.sort(key=parse_version, reverse=True)
    except ImportError:
        import re

        def n(v):
            return [int(x) for x in re.sub(r"[^0-9.]", "", v).split(".")]

        versions.sort(key=n, reverse=True)

    selected_index = dialog_select(
        heading=translation(90585), _list=versions
    )

    if selected_index == -1:
        return

    selected_version = versions[selected_index]

    if not dialogyesno(
        header=HEADING,
        text=translation(90586) % selected_version,
    ):
        return

    update_addon(selected_version)


def update_addon(new_version):
    kodilog(f"Starting update to version: {new_version}")
    close_all_dialog()
    execute_builtin("ActivateWindow(Home)", True)
    notification(heading=HEADING, message=translation(90587))

    zip_name = f"{ADDON_ID}-{new_version}.zip"
    zip_url = f"{BASE_ZIP_URL}/{ADDON_ID}/{zip_name}"
    zip_path = os.path.join(PACKAGES_DIR, zip_name)
    staging_dir = os.path.join(PACKAGES_DIR, f"{ADDON_ID}-staging")
    staging_addon_dir = os.path.join(staging_dir, ADDON_ID)
    backup_dir = os.path.join(PACKAGES_DIR, f"{ADDON_ID}-backup")
    kodilog(f"Zip URL: {zip_url}")
    kodilog(f"Zip Path: {zip_path}")

    # Download new version
    show_busy_dialog()
    kodilog("Downloading zip file...")
    raw_data = http_get(zip_url, stream=True)
    close_busy_dialog()
    if not raw_data:
        kodilog("Error: Unable to download update.")
        dialog_ok(heading=HEADING, line1=translation(90588))
        return

    try:
        with open(zip_path, "wb") as f:
            shutil.copyfileobj(raw_data, f)
        kodilog("Zip file downloaded successfully.")
    except Exception as e:
        kodilog(f"Error saving update file: {e}")
        dialog_ok(heading=HEADING, line1=translation(90589) % e)
        return

    try:
        _validate_downloaded_zip(zip_path, new_version)
    except ValueError as e:
        kodilog(f"Error validating update package: {e}")
        delete_file(zip_path)
        dialog_ok(heading=HEADING, line1=translation(90590))
        return

    try:
        _safe_remove_path(staging_dir)
        os.makedirs(staging_dir)
    except Exception as e:
        kodilog(f"Error preparing staging directory: {e}")
        delete_file(zip_path)
        dialog_ok(heading=HEADING, line1=translation(90590))
        return

    try:
        if not unzip(zip_path, staging_dir, staging_addon_dir):
            raise ValueError("Staging extraction failed")

        _validate_installed_version(staging_addon_dir, new_version)
    except Exception as e:
        kodilog(f"Error extracting update to staging: {e}")
        delete_file(zip_path)
        try:
            _safe_remove_path(staging_dir)
        except Exception:
            pass
        dialog_ok(
            heading=HEADING, line1=translation(90590)
        )
        return

    replaced_existing_install = False
    try:
        _safe_remove_path(backup_dir)

        if os.path.lexists(DESTINATION_DIR):
            kodilog(f"Backing up current installation from: {DESTINATION_DIR}")
            shutil.move(DESTINATION_DIR, backup_dir)
            replaced_existing_install = True

        kodilog(f"Installing staged version to: {DESTINATION_DIR}")
        shutil.move(staging_addon_dir, DESTINATION_DIR)
        _validate_installed_version(DESTINATION_DIR, new_version)
    except Exception as e:
        kodilog(f"Error replacing addon version: {e}")

        try:
            if os.path.lexists(DESTINATION_DIR):
                _safe_remove_path(DESTINATION_DIR)
            if replaced_existing_install and os.path.lexists(backup_dir):
                shutil.move(backup_dir, DESTINATION_DIR)
        except Exception as restore_error:
            kodilog(f"Error restoring previous addon version: {restore_error}")

        delete_file(zip_path)
        try:
            _safe_remove_path(staging_dir)
        except Exception:
            pass
        dialog_ok(heading=HEADING, line1=translation(90590))
        return

    delete_file(zip_path)
    try:
        _safe_remove_path(staging_dir)
        _safe_remove_path(backup_dir)
    except Exception as e:
        kodilog(f"Error cleaning temporary update paths: {e}")

    if dialogyesno(
        header=HEADING,
        text=translation(90591),
    ):
        get_changes()

    # Refresh Kodi addon system
    update_local_addons()
    disable_enable_addon()
    update_kodi_addons_db()
    notification(heading=HEADING, message="Reloading Kodi profile to apply addon changes")
    execute_builtin('LoadProfile(%s)' % xbmc.getInfoLabel("System.ProfileName"), True)

    notification(heading=HEADING, message=translation(90593))
    kodilog("Update process finished successfully.")
