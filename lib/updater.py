# -*- coding: utf-8 -*-
import shutil
import requests
import os
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import (
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
)
from lib.utils.general_utils import clear_all_cache, unzip
from lib.utils.settings import cache_clear_update
from xbmcvfs import translatePath as translate_path

packages_dir = translate_path("special://home/addons/packages/")
home_addons_dir = translate_path("special://home/addons/")
destination_check = translate_path("special://home/addons/plugin.video.jacktook/")
changelog_location = translate_path(
    "special://home/addons/plugin.video.jacktook/CHANGELOG.md"
)
repo_url = "https://github.com/Sam-Max/repository.jacktook/raw/main/packages"
jacktook_url = "https://raw.githubusercontent.com/Sam-Max/repository.jacktook/main/repo/zips/plugin.video.jacktook"
heading = "Jacktook Updater"


# Taken from Fen Update Mechanism
def get_versions():
    try:
        result = requests.get(f"{repo_url}/jacktook_version")
        if result.status_code != 200:
            notification(f"Error: {result.status_code}"),
            return None, None
        kodilog(result.text)
        online_version = result.text.replace("\n", "")
        current_version = ADDON_VERSION
        return current_version, online_version
    except:
        return None, None


def updates_check_addon(action=4):
    if action == 3:
        return
    current_version, online_version = get_versions()
    if current_version is None:
        return
    msg = f"Installed Version: [B]{current_version}[/B][CR]"
    msg += f"Online Version: [B]{online_version}[/B][CR][CR]"
    if current_version == online_version:
        if action == 4:
            return dialog_ok(heading=heading, line1=msg + "[B]No Update Available[/B]")
        return
    if action in (0, 4):
        if not dialogyesno(
            header=heading,
            text=msg + "[B]An update is available[/B][CR]Do you want to update?",
        ):
            return
    if action == 1:
        notification("Updating...")
    if action == 2:
        return notification("Jacktook Update Available")
    return update_addon(online_version, action)


def get_changes(online_version=False):
    if online_version:
        try:
            result = requests.get(f"{repo_url}/jacktook_changelog")
            if result.status_code != 200:
                notification(f"Error: {result.status_code}")
                return
            dialog_text(
                f"New Online Release (v{online_version}) Changelog", result.text
            )
        except Exception as err:
            return notification(f"Error:{err}")
    else:
        dialog_text("Changelog", file=changelog_location)


def update_addon(new_version, action):
    if cache_clear_update(): 
        clear_all_cache()
    close_all_dialog()
    execute_builtin("ActivateWindow(Home)", True)
    zip_name = f"plugin.video.jacktook-{new_version}.zip"
    url = f"{jacktook_url}/{zip_name}"
    result = requests.get(url, stream=True)
    if result.status_code != 200:
        return dialog_ok(
            heading=heading,
            line1="Error Updating. Please install new update manually",
        )
    zip_location = os.path.join(packages_dir, zip_name)
    with open(zip_location, "wb") as f:
        shutil.copyfileobj(result.raw, f)
    shutil.rmtree(os.path.join(home_addons_dir, "plugin.video.jacktook"))
    success = unzip(zip_location, home_addons_dir, destination_check)
    delete_file(zip_location)
    if not success:
        return dialog_ok(
            heading=heading,
            line1="Error Updating.[CR]Please install new update manually",
        )
    if (
        action in (0, 4)
        and dialog_ok(
            heading=heading,
            line1=f"Success.[CR]Jacktook updated to version [B]{new_version}[/B]",
        )
        != False
    ):
        get_changes()
    update_local_addons()
    disable_enable_addon()
    update_kodi_addons_db()
    
