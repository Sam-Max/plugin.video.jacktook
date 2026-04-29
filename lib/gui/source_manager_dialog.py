import json
import os
from datetime import timedelta

import xbmcgui

from lib.db.cached import cache
from lib.utils.kodi.settings import get_setting
from lib.utils.kodi.utils import ADDON_PATH, kodilog, translation


BUILTIN_SOURCE_SETTINGS = [
    ("jackett_enabled", "Jackett"),
    ("prowlarr_enabled", "Prowlarr"),
    ("jacktookburst_enabled", "Burst"),
    ("jackgram_enabled", "Jackgram"),
    ("easynews_enabled", "Easynews"),
    ("stremio_enabled", "Stremio"),
]

CACHE_KEY = "source_manager_selection"


def _get_icon_path(name):
    icon_name = f"{name.lower()}.png"
    media_path = os.path.join(ADDON_PATH, "resources", "media", icon_name)
    if os.path.exists(media_path):
        return media_path
    img_path = os.path.join(ADDON_PATH, "resources", "img", icon_name)
    if os.path.exists(img_path):
        return img_path
    return os.path.join(ADDON_PATH, "icon.png")


def open_source_manager_dialog():
    try:
        from lib.clients.stremio.helpers import get_selected_stream_addons
    except Exception as e:
        get_selected_stream_addons = None
        kodilog(f"Failed to import get_selected_stream_addons: {e}")

    items = []
    cache_keys = []

    for setting_key, display_name in BUILTIN_SOURCE_SETTINGS:
        if not get_setting(setting_key):
            continue

        if setting_key == "stremio_enabled":
            if get_selected_stream_addons is not None:
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
            continue

        icon_path = _get_icon_path(display_name)
        li = xbmcgui.ListItem(label=display_name)
        li.setArt({"icon": icon_path})
        items.append(li)
        cache_keys.append(display_name)

    if not items:
        xbmcgui.Dialog().notification("Jacktook", translation(90756))
        return

    raw_selection = cache.get(CACHE_KEY)
    if raw_selection is None:
        current_selection = []
    else:
        try:
            current_selection = (
                json.loads(raw_selection)
                if isinstance(raw_selection, str)
                else list(raw_selection)
            )
        except (ValueError, TypeError):
            current_selection = []

    if not current_selection:
        current_selection = list(cache_keys)
        cache.set(CACHE_KEY, json.dumps(current_selection), expires=timedelta(days=365))
    else:
        newly_enabled = [key for key in cache_keys if key not in current_selection]
        if newly_enabled:
            current_selection.extend(newly_enabled)
            cache.set(CACHE_KEY, json.dumps(current_selection), expires=timedelta(days=365))

    preselect = [i for i, key in enumerate(cache_keys) if key in current_selection]

    result = xbmcgui.Dialog().multiselect(
        translation(90755),
        items,
        preselect=preselect,
        useDetails=True,
    )

    if result is None or not result:
        return

    selected = [cache_keys[i] for i in result]
    cache.set(CACHE_KEY, json.dumps(selected), expires=timedelta(days=365))
