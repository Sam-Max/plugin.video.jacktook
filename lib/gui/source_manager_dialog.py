import os

import xbmcgui

from lib.db.cached import cache
from lib.utils.kodi.settings import get_setting
from lib.utils.kodi.utils import ADDON_PATH, kodilog, translation
from lib.utils.source_manager import (
    BUILTIN_SOURCE_SETTINGS,
    CACHE_KEY,
    KNOWN_CACHE_KEY,
    persist_source_selection,
    reconcile_source_selection,
)


def _get_icon_path(name):
    icon_name = f"{name.lower()}.png"
    media_path = os.path.join(ADDON_PATH, "resources", "media", icon_name)
    if os.path.exists(media_path):
        return media_path
    img_path = os.path.join(ADDON_PATH, "resources", "img", icon_name)
    if os.path.exists(img_path):
        return img_path
    return os.path.join(ADDON_PATH, "icon.png")


def _load_stremio_addons():
    """Import and return the Stremio addon selector, or None on failure."""
    try:
        from lib.clients.stremio.helpers import get_selected_stream_addons

        return get_selected_stream_addons
    except Exception as e:
        kodilog(f"Failed to import get_selected_stream_addons: {e}")
        return None


def _add_stremio_sources(items, cache_keys, get_selected_stream_addons):
    """Append enabled Stremio addon entries to items/cache_keys."""
    if get_selected_stream_addons is None:
        return
    try:
        addons = get_selected_stream_addons()
        for addon in addons:
            key = f"Stremio:{addon.key()}"
            addon_name = addon.manifest.name
            addon_icon_path = _get_icon_path(addon_name)
            li_addon = xbmcgui.ListItem(label=addon_name)
            li_addon.setArt({"icon": addon_icon_path})
            items.append(li_addon)
            cache_keys.append(key)
    except Exception as e:
        kodilog(f"Error loading Stremio addons: {e}")


def _build_source_items():
    """Return (ListItem list, cache key list) for enabled sources."""
    get_selected_stream_addons = _load_stremio_addons()
    items = []
    cache_keys = []

    for setting_key, display_name in BUILTIN_SOURCE_SETTINGS:
        if not get_setting(setting_key):
            continue

        if setting_key == "external_scraper_enabled":
            module_name = get_setting("external_scraper_module_name")
            if module_name:
                display_name = str(module_name)

        if setting_key == "stremio_enabled":
            _add_stremio_sources(items, cache_keys, get_selected_stream_addons)
            continue

        icon_path = _get_icon_path(display_name)
        li = xbmcgui.ListItem(label=display_name)
        li.setArt({"icon": icon_path})
        items.append(li)
        cache_keys.append(display_name)

    return items, cache_keys


def _resolve_selection(cache_keys):
    return reconcile_source_selection(cache_keys, cache_backend=cache)


def _persist_selection(selected, cache_keys):
    """Save the user's selection and the set of known source keys."""
    persist_source_selection(selected, cache_keys, cache_backend=cache)


def open_source_manager_dialog():
    items, cache_keys = _build_source_items()
    if not items:
        xbmcgui.Dialog().notification("Jacktook", translation(90756))
        return

    current_selection = _resolve_selection(cache_keys)
    preselect = [i for i, key in enumerate(cache_keys) if key in current_selection]

    result = xbmcgui.Dialog().multiselect(
        translation(90755),
        items,
        preselect=preselect,
        useDetails=True,
    )

    if result is None:
        return

    selected = [cache_keys[i] for i in result]
    _persist_selection(selected, cache_keys)
