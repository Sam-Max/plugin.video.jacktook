import xbmcgui
from typing import List
from lib.stremio.addons_manager import AddonManager, Addon
from lib.api.jacktook.kodi import kodilog
from lib.db.cached import cache
from datetime import timedelta
from lib.stremio.client import Stremio

STREMIO_ADDONS_KEY = "stremio_addons"
STREMIO_CATALOG_KEY = "stremio_catalog"


def get_addons_catalog():
    catalog = cache.get(STREMIO_CATALOG_KEY, hashed_key=True)
    if not catalog:
        stremio = Stremio()
        try:
            catalog = stremio.get_community_addons()
        except Exception as e:
            kodilog(f"Failed to fetch catalog: {e}")
            return AddonManager([])

        cache.set(STREMIO_CATALOG_KEY, catalog, timedelta(days=1), hashed_key=True)
    return AddonManager(catalog)


def get_selected_addon_urls() -> List[str]:
    selected_addons = cache.get(STREMIO_ADDONS_KEY, hashed_key=True) or ""
    return selected_addons.split(",")


def get_selected_addons() -> List[Addon]:
    catalog = get_addons_catalog()
    selected_ids = cache.get(STREMIO_ADDONS_KEY, hashed_key=True) or ""
    return [addon for addon in catalog.addons if addon.url() in selected_ids]


def stremio_addons_import(params):
    # Create a dialog box
    dialog = xbmcgui.Dialog()

    dialog.ok(
        "Stremio Add-ons Import",
        "To import your add-ons, please log in with your Stremio email and password.\n\n"
        + "Your login details will not be saved and are only used once for this process.",
    )

    # Show an input dialog for email
    email = dialog.input(heading="Enter your Email", type=xbmcgui.INPUT_ALPHANUM)

    kodilog(f"Email: {email}")
    if not email:
        return

    # Show a password dialog
    password = dialog.input(heading="Enter your Password", type=xbmcgui.INPUT_ALPHANUM)

    if not password:
        return

    try:
        stremio = Stremio()
        stremio.login(email, password)
    except Exception as e:
        dialog.ok("Login Failed", f"Failed to login: {e}")
        return

    try:
        addons = stremio.get_my_addons()
        cache.set(
            STREMIO_CATALOG_KEY, addons, timedelta(days=365 * 20), hashed_key=True
        )
        manager = AddonManager(addons).get_addons_with_resource_and_id_prefix(
            "stream", "tt"
        )
        selected_addons = [addon.url() for addon in manager]
        cache.set(
            STREMIO_ADDONS_KEY,
            ",".join(selected_addons),
            timedelta(days=365 * 20),
            hashed_key=True,
        )
    except Exception as e:
        dialog.ok(
            "Add-ons Import Failed",
            "Please try again later and report the issue if the problem persists. For more details, check the log file.",
        )
        kodilog(f"Failed to import addons: {e} Response ", exc_info=True)
        return

    dialog.ok("Addons Imported", f"Successfully imported addons from your account.")


def stremio_addons_manager(params):
    selected_ids = get_selected_addon_urls()
    addon_manager = get_addons_catalog()

    addons = addon_manager.get_addons_with_resource_and_id_prefix("stream", "tt")

    addon_names = [
        f"{addon.manifest.name}: {addon.manifest.description}" for addon in addons
    ]
    addon_urls = [addon.url() for addon in addons]

    dialog = xbmcgui.Dialog()
    selected_addon_id = None

    while True:
        options = [
            f"[{'X' if addon_url in selected_ids else ' '}] {addon_names[i]}"
            for i, addon_url in enumerate(addon_urls)
        ]

        options.append("Remove all addons")

        selected_index = dialog.select("Select an Addon", options)

        if selected_index == -1:
            break

        if selected_index == len(options) - 1:
            confirm = dialog.yesno(
                "Reset strem.io configuration",
                f"This will remove all the configured add-ons and start from scratch",
                nolabel="Cancel",
                yeslabel="Yes",
            )
            if confirm:
                cache.set(
                    STREMIO_ADDONS_KEY, None, timedelta(seconds=1), hashed_key=True
                )
                cache.set(
                    STREMIO_CATALOG_KEY, None, timedelta(seconds=1), hashed_key=True
                )
            return

        selected_addon_id = addon_urls[selected_index]

        if selected_addon_id in selected_ids:
            confirm = dialog.yesno(
                "Disable addon",
                f"{addon_names[selected_index]}",
                nolabel="Cancel",
                yeslabel="Yes",
            )
            if confirm:
                selected_ids.remove(selected_addon_id)
        else:
            confirm = dialog.yesno(
                "Enable addon",
                f"{addon_names[selected_index]}",
                nolabel="Cancel",
                yeslabel="Yes",
            )
            if confirm:
                selected_ids.append(selected_addon_id)

        cache.set(
            STREMIO_ADDONS_KEY,
            ",".join(selected_ids),
            timedelta(days=365 * 20),
            hashed_key=True,
        )
