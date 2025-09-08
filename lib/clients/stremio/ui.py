import os
import requests
from typing import List
from datetime import timedelta

from lib.clients.stremio.addons_manager import Addon, AddonManager
from lib.clients.stremio.client import Stremio
from lib.db.cached import cache
from lib.utils.general.utils import USER_AGENT_HEADER
from lib.utils.kodi.utils import ADDON, ADDON_PATH, get_setting, kodilog, set_setting

import xbmcgui
import xbmc


STREMIO_ADDONS_KEY = "stremio_addons"
STREMIO_ADDONS_CATALOGS_KEY = "stremio_catalog_addons"
STREMIO_USER_ADDONS = "stremio_user_addons"
TORRENTIO_PROVIDERS_KEY = "torrentio.providers"


all_torrentio_providers = [
    ("yts", "YTS", "torrentio.png"),
    ("nyaasi", "Nyaa", "torrentio.png"),
    ("eztv", "EZTV", "torrentio.png"),
    ("rarbg", "RARBG", "torrentio.png"),
    ("mejortorrent", "MejorTorrent", "torrentio.png"),
    ("wolfmax4k", "WolfMax4K", "torrentio.png"),
    ("cinecalidad", "CineCalidad", "torrentio.png"),
    ("1337x", "1337x", "torrentio.png"),
    ("thepiratebay", "The Pirate Bay", "torrentio.png"),
    ("kickasstorrents", "Kickass", "torrentio.png"),
    ("torrentgalaxy", "TorrentGalaxy", "torrentio.png"),
    ("magnetdl", "MagnetDL", "torrentio.png"),
    ("horriblesubs", "HorribleSubs", "torrentio.png"),
    ("tokyotosho", "Tokyotosho", "torrentio.png"),
    ("anidex", "Anidex", "torrentio.png"),
    ("rutracker", "Rutracker", "torrentio.png"),
    ("comando", "Comando", "torrentio.png"),
    ("torrent9", "Torrent9", "torrentio.png"),
    ("ilcorsaronero", "Il Corsaro Nero", "torrentio.png"),
    ("besttorrents", "BestTorrents", "torrentio.png"),
    ("bludv", "BluDV", "torrentio.png"),
]

excluded_addons = {
    "imdb.ratings.local",
    "org.stremio.deepdivecompanion",
    "community.ratings.aggregator",
    "org.stremio.ageratings",
    "com.stremio.autostream.addon",
    "org.cinetorrent",
    "community.peario",
    "community.stremioeasynews",
    "Community-knightcrawler.elfhosted.com",
    "jackettio.elfhosted.com",
    "org.stremio.zamunda",
    "com.stremify",
    "org.anyembedaddon",
    "org.stremio.tmdbcollections",
    "org.stremio.ytztvio",
    "com.skyflix",
    "org.stremio.local",
    "com.animeflv.stremio.addon",
    "org.cinecalidad.addon",
    "org.stremio.hellspy",
    "org.prisonmike.streamvix",
    "community.SeedSphere",
    "org.moviesindetail.openlink",
    "app.torbox.stremio",
}


def merge_addons_lists(*lists):
    seen = set()
    merged = []

    for addon_source in lists:
        if isinstance(addon_source, dict):
            addons = addon_source.get("addons", [])
        else:
            addons = addon_source
        for addon in addons:
            key = addon.get("manifest", {}).get("id") or addon.get("id")
            if key and key not in seen:
                seen.add(key)
                merged.append(addon)
    return merged


def get_addons():
    # Always get custom addons from STREMIO_USER_ADDONS
    all_user_addons = cache.get(STREMIO_USER_ADDONS) or []
    custom_addons = [a for a in all_user_addons if a.get("transportName") == "custom"]

    logged_in = get_setting("stremio_loggedin")
    if logged_in:
        stremio = Stremio()
        try:
            email = get_setting("stremio_email")
            password = get_setting("stremio_pass")
            if email and password:
                stremio.login(email, password)
                user_addons = stremio.get_my_addons() or []
            else:
                kodilog("Stremio credentials missing, cannot fetch user addons.")
                user_addons = []
        except Exception as e:
            kodilog(f"Failed to fetch user addons: {e}")
            user_addons = []
        merged_addons = merge_addons_lists(user_addons, custom_addons)
    else:
        community_addons = cache.get("stremio_community_addons")
        if community_addons is None:
            stremio = Stremio()
            try:
                community_addons = stremio.get_community_addons()
            except Exception as e:
                kodilog(f"Failed to fetch community addons: {e}")
                community_addons = []
            cache.set("stremio_community_addons", community_addons, timedelta(hours=12))
        merged_addons = merge_addons_lists(community_addons, custom_addons)

    kodilog(f"Loaded {len(merged_addons)} addons from catalog", level=xbmc.LOGDEBUG)
    return AddonManager(merged_addons)


def get_selected_stream_addons() -> List[Addon]:
    catalog = get_addons()
    selected_ids = cache.get(STREMIO_ADDONS_KEY)
    if not selected_ids:
        return []
    return [addon for addon in catalog.addons if addon.key() in selected_ids]


def get_selected_catalogs_addons() -> List[Addon]:
    catalog = get_addons()
    selected_ids = cache.get(STREMIO_ADDONS_CATALOGS_KEY)
    if not selected_ids:
        return []
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


def log_in(email, password, dialog):
    try:
        stremio = Stremio()
        stremio.login(email, password)
    except Exception as e:
        dialog.ok("Login Failed", f"Failed to login: {e}")
        return

    try:
        # Only merge user account addons with custom addons
        user_account_addons = stremio.get_my_addons() or []
        all_user_addons = cache.get(STREMIO_USER_ADDONS) or []
        custom_addons = [
            a for a in all_user_addons if a.get("transportName") == "custom"
        ]
        all_addons = merge_addons_lists(user_account_addons, custom_addons)
        cache.set(STREMIO_USER_ADDONS, all_addons, timedelta(days=365 * 20))

        set_setting("stremio_email", email)
        set_setting("stremio_pass", password)
        set_setting("stremio_loggedin", "true")

        kodilog(f"Stremio addons imported: {len(all_addons)}")
    except Exception as e:
        dialog.ok(
            "Add-ons Import Failed",
            "Please try again later and report the issue if the problem persists. For more details, check the log file.",
        )
        kodilog(f"Failed to import addons: {e}")
        return

    dialog.ok("Addons Imported", f"Successfully imported addons from your account.")


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
        cache.set(STREMIO_ADDONS_CATALOGS_KEY, None, timedelta(seconds=1))
        # Do not clear custom addons, only clear login state and user (login) addons
        all_user_addons = cache.get(STREMIO_USER_ADDONS) or []
        custom_addons = [
            a for a in all_user_addons if a.get("transportName") == "custom"
        ]
        cache.set(STREMIO_USER_ADDONS, custom_addons, timedelta(days=365 * 20))

        set_setting("stremio_loggedin", "false")
        set_setting("stremio_email", "")
        set_setting("stremio_pass", "")


def stremio_toggle_addons(params):
    selected_ids = cache.get(STREMIO_ADDONS_KEY) or ""
    addon_manager = get_addons()
    addons = addon_manager.get_addons_with_resource_and_id_prefix("stream", "tt")

    addons = [
        addon
        for addon in addons
        if not addon.manifest.isConfigurationRequired()
        and addon.key() not in excluded_addons
    ]
    
    addons = list(reversed(addons))

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


def stremio_toggle_catalogs(params):
    kodilog("stremio_toggle_catalogs called")

    selected_ids = cache.get(STREMIO_ADDONS_CATALOGS_KEY) or ""
    addon_manager = get_addons()
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
        STREMIO_ADDONS_CATALOGS_KEY,
        ",".join(selected_addon_ids),
        timedelta(days=365 * 20),
    )


def add_custom_stremio_addon(params):
    dialog = xbmcgui.Dialog()
    url = dialog.input(
        "Enter the custom Stremio addon URL", type=xbmcgui.INPUT_ALPHANUM
    )
    if not url:
        dialog.ok("Custom Addon", "No URL provided.")
        return

    # Try to fetch the manifest from the URL
    try:
        response = requests.get(url, headers=USER_AGENT_HEADER, timeout=10)
        response.raise_for_status()
        manifest = response.json()
    except Exception as e:
        kodilog(f"Failed to fetch custom addon manifest: {e}")
        dialog.ok("Custom Addon", f"Failed to fetch manifest: {e}")
        return

    try:
        addon_key = manifest.get("id") or manifest.get("name")
        if not addon_key:
            dialog.ok("Custom Addon", "Manifest missing 'id' or 'name'.")
            return

        resources = manifest.get("resources", [])
        # Normalize resources to list of dicts or strings
        if isinstance(resources, dict):
            resources = [resources]
        elif isinstance(resources, str):
            resources = [resources]

        # Determine capabilities
        is_stream = False
        is_catalog = False
        for res in resources:
            if isinstance(res, dict):
                if res.get("name") == "stream":
                    id_prefixes = res.get("idPrefixes", [])
                    if "tt" in id_prefixes:
                        is_stream = True
                if res.get("name") == "catalog":
                    is_catalog = True
            elif isinstance(res, str):
                if res == "stream":
                    is_stream = True
                if res == "catalog":
                    is_catalog = True

        # Add to selected addons if stream
        if is_stream:
            selected_addons = cache.get(STREMIO_ADDONS_KEY)
            selected_keys = selected_addons.split(",") if selected_addons else []
            if addon_key not in selected_keys:
                selected_keys.append(addon_key)
                cache.set(
                    STREMIO_ADDONS_KEY,
                    ",".join(selected_keys),
                    timedelta(days=365 * 20),
                )

        # Add to selected catalogs if catalog
        if is_catalog:
            selected_catalogs = cache.get(STREMIO_ADDONS_CATALOGS_KEY) or ""
            selected_catalog_keys = (
                selected_catalogs.split(",") if selected_catalogs else []
            )
            if addon_key not in selected_catalog_keys:
                selected_catalog_keys.append(addon_key)
                cache.set(
                    STREMIO_ADDONS_CATALOGS_KEY,
                    ",".join(selected_catalog_keys),
                    timedelta(days=365 * 20),
                )

        # Always add custom addon to user addons catalog
        user_addons = cache.get(STREMIO_USER_ADDONS) or []

        custom_addon = {
            "manifest": manifest,
            "transportUrl": response.url,
            "transportName": "custom",
        }
        if not any(
            (a.get("manifest", {}).get("id") or a.get("manifest", {}).get("name"))
            == addon_key
            for a in user_addons
        ):
            user_addons.append(custom_addon)
            cache.set(STREMIO_USER_ADDONS, user_addons, timedelta(days=365 * 20))

            if is_stream or is_catalog:
                dialog.ok("Custom Addon", "Custom Stremio addon added successfully!")
            else:
                dialog.ok(
                    "Custom Addon",
                    "Addon does not provide 'stream' or 'catalog' resources.",
                )
        else:
            dialog.ok("Custom Addon", "This addon is already added to your list.")
    except Exception as e:
        dialog.ok("Custom Addon", f"Failed to add custom addon: {e}")


def torrentio_toggle_providers(params):
    selected_ids = cache.get(TORRENTIO_PROVIDERS_KEY) or ""
    selected_ids = selected_ids.split(",") if selected_ids else []

    options = []
    selected_indexes = []
    for i, (key, name, logo) in enumerate(all_torrentio_providers):
        item = xbmcgui.ListItem(label=name)
        item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "torrentio.png")}
        )
        options.append(item)
        if key in selected_ids:
            selected_indexes.append(i)

    dialog = xbmcgui.Dialog()
    title = "Seleccionar proveedores de Torrentio"

    selected = dialog.multiselect(
        title, options, preselect=selected_indexes, useDetails=True
    )

    if selected is None:
        return

    new_selected_ids = [all_torrentio_providers[i][0] for i in selected]
    cache.set(
        TORRENTIO_PROVIDERS_KEY, ",".join(new_selected_ids), timedelta(days=365 * 20)
    )
