import json
import os
import sys

import xbmc
import xbmcgui

from lib.utils.kodi.settings import get_setting
from lib.utils.kodi.utils import kodilog, set_setting


def choose_external_scraper():
    """Display a dialog to choose an external scraper module.

    Lists all enabled ``xbmc.python.module`` addons, lets the user pick
    one, tests compatibility by importing its ``sources()`` function, and
    stores the selection in settings.
    """
    addons = _list_compatible_modules()
    if not addons:
        xbmcgui.Dialog().notification(
            "Jacktook",
            get_setting("external_scraper_no_modules_msg") or "No compatible modules found",
        )
        return

    items = []
    for addon in addons:
        name = addon.get("name", "")
        icon = addon.get("thumbnail", "")
        li = xbmcgui.ListItem(label=name)
        li.setArt({"icon": icon})
        items.append(li)

    heading = get_setting("external_scraper_choose_heading") or "Choose External Scraper"
    selected = xbmcgui.Dialog().select(heading, items, useDetails=True)
    if selected == -1:
        return

    chosen = addons[selected]
    module_id = chosen["addonid"]
    module_name = chosen["name"]

    # Test compatibility
    if not _test_module_compatibility(chosen):
        error_msg = (
            get_setting("external_scraper_incompatible_msg")
            or "The selected module is not compatible. Please choose a different one."
        )
        xbmcgui.Dialog().ok("Jacktook", error_msg)
        # Let user try again
        choose_external_scraper()
        return

    # Success — persist selection
    set_setting("external_scraper_module", module_id)
    set_setting("external_scraper_module_name", module_name)
    set_setting("external_scraper_enabled", "true")

    success_msg = (
        get_setting("external_scraper_success_msg")
        or f"Success!\n{module_name} set as External Scraper"
    )
    xbmcgui.Dialog().ok("Jacktook", success_msg)


def open_external_scraper_settings():
    """Open Kodi's settings window for the currently selected scraper."""
    module_id = get_setting("external_scraper_module")
    kodilog(f"ExternalScraper: open settings requested, module={module_id}")
    if not module_id:
        xbmcgui.Dialog().notification("Jacktook", "No external scraper selected")
        return
    try:
        # When this action is launched from Jacktook's settings window, the
        # current modal settings dialog can stay in front of (or block) the
        # external addon's settings window. Close it first, then open the
        # selected scraper settings.
        xbmc.executebuiltin("Dialog.Close(addonsettings)")
        xbmc.sleep(300)
        xbmc.executebuiltin(f"Addon.OpenSettings({module_id})")
        xbmc.sleep(500)
    except Exception as exc:
        kodilog(f"ExternalScraper: Addon.OpenSettings failed: {exc}")
        xbmcgui.Dialog().notification("Jacktook", f"Unable to open settings: {module_id}")


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _list_compatible_modules() -> list:
    """Return a list of enabled ``xbmc.python.module`` addons."""
    try:
        response = xbmc.executeJSONRPC(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "Addons.GetAddons",
                    "params": {
                        "type": "xbmc.python.module",
                        "enabled": True,
                        "properties": ["name", "thumbnail", "path"],
                    },
                    "id": 1,
                }
            )
        )
        data = json.loads(response)
        addons = data.get("result", {}).get("addons", [])
        # Exclude Kodi's own system modules
        return [
            a
            for a in addons
            if not a["addonid"].startswith(("xbmc.", "kodi."))
        ]
    except Exception as exc:
        kodilog(f"ExternalScraper: failed to list modules: {exc}")
        return []


def _test_module_compatibility(addon: dict) -> bool:
    """Try importing ``sources()`` from *addon* to verify compatibility."""
    module_id = addon["addonid"]
    module_name = module_id.split(".")[-1]
    addon_path = addon.get("path", "")

    lib_path = os.path.join(addon_path, "lib")
    if not os.path.isdir(lib_path):
        kodilog(f"ExternalScraper: no lib dir for {module_id}")
        return False

    # Temporarily add to sys.path (we leave it there since the scraper
    # will need it at search time anyway).
    if lib_path not in sys.path:
        sys.path.insert(0, lib_path)

    try:
        module = __import__(module_name, fromlist=["sources"])
        source_dict = module.sources(specified_folders=["torrents"])
        if not source_dict:
            kodilog(f"ExternalScraper: {module_id} returned no providers")
            return False
        return True
    except Exception as exc:
        kodilog(f"ExternalScraper: {module_id} compatibility test failed: {exc}")
        return False
