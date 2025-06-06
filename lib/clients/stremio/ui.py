from typing import List
from lib.clients.stremio.addons_manager import Addon, AddonManager
from lib.clients.stremio.client import Stremio
from lib.db.cached import cache
from datetime import timedelta
from lib.utils.kodi.utils import ADDON, get_setting, kodilog, set_setting

import xbmcgui


STREMIO_ADDONS_KEY = "stremio_addons"
STREMIO_CATALOGS_ADDONS_KEY = "stremio_catalog_addons"
STREMIO_CATALOG_KEY = "stremio_catalog"


def get_addons_catalog():
    catalog = cache.get(STREMIO_CATALOG_KEY)
    if not catalog:
        stremio = Stremio()
        try:
            catalog = stremio.get_community_addons()
        except Exception as e:
            kodilog(f"Failed to fetch catalog: {e}")
            return AddonManager([])

        selected_keys = cache.get(STREMIO_ADDONS_KEY) or ""
        if not selected_keys:
            selected_keys = "com.stremio.torrentio.addon"
            cache.set(
                STREMIO_ADDONS_KEY,
                selected_keys,
                timedelta(days=365 * 20),
            )

        cache.set(STREMIO_CATALOG_KEY, catalog, timedelta(days=1))
    return AddonManager(catalog)


def get_selected_addon_urls() -> List[str]:
    selected_addons = cache.get(STREMIO_ADDONS_KEY) or ""
    return selected_addons.split(",")


def get_selected_catalogs_addon_urls() -> List[str]:
    selected_addons = cache.get(STREMIO_CATALOGS_ADDONS_KEY) or ""
    return selected_addons.split(",")


def get_selected_addons() -> List[Addon]:
    catalog = get_addons_catalog()
    selected_ids = cache.get(STREMIO_ADDONS_KEY) or ""
    return [addon for addon in catalog.addons if addon.key() in selected_ids]


def get_selected_catalogs_addons() -> List[Addon]:
    catalog = get_addons_catalog()
    selected_ids = cache.get(STREMIO_CATALOGS_ADDONS_KEY) or ""
    return [addon for addon in catalog.addons if addon.key() in selected_ids]


def stremio_login(params):
    dialog = xbmcgui.Dialog()
    dialog.ok(
        "Stremio Add-ons Import",
        "To import your add-ons, please log in with your Stremio email and password.\n\n"
        + "Your login details will not be saved and are only used once for this process.",
    )

    email = dialog.input(heading="Enter your Email", type=xbmcgui.INPUT_ALPHANUM)
    if not email:
        return

    password = dialog.input(heading="Enter your Password", type=xbmcgui.INPUT_ALPHANUM)
    if not password:
        return

    log_in(email, password, dialog)


def stremio_update(params):
    dialog = xbmcgui.Dialog()
    confirm = dialog.yesno(
        "Update Stremio Addons",
        "Do you want to update the Addons from you account?",
        nolabel="Cancel",
        yeslabel="Yes",
    )
    if not confirm:
        return

    email = get_setting("stremio_email")
    password = get_setting("stremio_pass")

    log_in(email, password, dialog)


def log_in(email, password, dialog):
    try:
        stremio = Stremio()
        stremio.login(email, password)
    except Exception as e:
        dialog.ok("Login Failed", f"Failed to login: {e}")
        return

    try:
        addons = stremio.get_my_addons()
        cache.set(STREMIO_CATALOG_KEY, addons, timedelta(days=365 * 20))
        manager = AddonManager(addons).get_addons_with_resource_and_id_prefix(
            "stream", "tt"
        )
        selected_addons = [addon.key() for addon in manager]
        cache.set(
            STREMIO_ADDONS_KEY,
            ",".join(selected_addons),
            timedelta(days=365 * 20),
        )

        dialog = xbmcgui.Dialog()
        confirm = dialog.yesno(
            "Stremio Add-ons Import",
            "Do you want also to import catalogs?",
            nolabel="Cancel",
            yeslabel="Yes",
        )
        if confirm:
            catalogs = AddonManager(addons).get_addons_with_resource("catalog")
            selected_catalogs = [catalog.key() for catalog in catalogs]
            cache.set(
                STREMIO_CATALOGS_ADDONS_KEY,
                ",".join(selected_catalogs),
                timedelta(days=365 * 20),
            )

        set_setting("stremio_loggedin", "true")
        set_setting("stremio_email", email)
        set_setting("stremio_pass", password)
    except Exception as e:
        dialog.ok(
            "Add-ons Import Failed",
            "Please try again later and report the issue if the problem persists. For more details, check the log file.",
        )
        kodilog(f"Failed to import addons: {e} Response ")
        return

    dialog.ok("Addons Imported", f"Successfully imported addons from your account.")

    stremio_toggle_addons(None)


def stremio_logout(params):
    dialog = xbmcgui.Dialog()

    confirm = dialog.yesno(
        "Log Out from Stremio",
        "Are you sure you want to log out? You can continue using Stremio without logging in, but your settings will be reset to the default configuration.",
        nolabel="Cancel",
        yeslabel="Log Out",
    )
    if confirm:
        cache.set(STREMIO_ADDONS_KEY, None, timedelta(seconds=1))
        cache.set(
            STREMIO_CATALOGS_ADDONS_KEY, None, timedelta(seconds=1)
        )
        cache.set(STREMIO_CATALOG_KEY, None, timedelta(seconds=1))
        settings = ADDON.getSettings()
        ADDON.setSetting("stremio_loggedin", "false")
        settings.setString("stremio_email", "")
        settings.setString("stremio_pass", "")
        _ = get_addons_catalog()
        stremio_toggle_addons(None)
        stremio_toggle_catalogs(None)


def stremio_toggle_catalogs(params):
    kodilog("stremio_toggle_catalogs")
    selected_ids = get_selected_catalogs_addon_urls()

    addon_manager = get_addons_catalog()
    addons = addon_manager.get_addons_with_resource("catalog")

    dialog = xbmcgui.Dialog()
    selected_addon_ids = [
        addons.index(addon) for addon in addons if addon.key() in selected_ids
    ]

    options = []
    for addon in addons:
        option = xbmcgui.ListItem(
            label=addon.manifest.name, label2=f"{addon.manifest.description}"
        )

        logo = addon.manifest.logo
        if not logo or logo.endswith(".svg"):
            logo = "DefaultAddon.png"

        option.setArt({"icon": logo})
        options.append(option)

    settings = ADDON.getSettings()
    stremio_email = settings.getString("stremio_email")
    title = stremio_email or "Stremio Community Catalogs List"
    selected_indexes = dialog.multiselect(
        title, options, preselect=selected_addon_ids, useDetails=True
    )

    if selected_indexes is None:
        return

    selected_addon_ids = [addons[index].key() for index in selected_indexes]

    cache.set(
        STREMIO_CATALOGS_ADDONS_KEY,
        ",".join(selected_addon_ids),
        timedelta(days=365 * 20),
    )


def stremio_toggle_addons(params):
    selected_ids = get_selected_addon_urls()
    addon_manager = get_addons_catalog()

    addons = addon_manager.get_addons_with_resource_and_id_prefix("stream", "tt")

    dialog = xbmcgui.Dialog()
    selected_addon_ids = [
        addons.index(addon) for addon in addons if addon.key() in selected_ids
    ]

    options = []
    for addon in addons:
        option = xbmcgui.ListItem(
            label=addon.manifest.name, label2=f"{addon.manifest.description}"
        )

        logo = addon.manifest.logo
        if not logo or logo.endswith(".svg"):
            logo = "DefaultAddon.png"

        option.setArt({"icon": logo})
        options.append(option)

    settings = ADDON.getSettings()
    stremio_email = settings.getString("stremio_email")
    title = stremio_email or "Stremio Community Addons List"
    selected_indexes = dialog.multiselect(
        title, options, preselect=selected_addon_ids, useDetails=True
    )

    if selected_indexes is None:
        return

    selected_addon_ids = [addons[index].key() for index in selected_indexes]

    cache.set(
        STREMIO_ADDONS_KEY,
        ",".join(selected_addon_ids),
        timedelta(days=365 * 20),
    )
