"""TorrServer navigation flows."""

from urllib.parse import quote

import xbmcgui
from xbmcplugin import addDirectoryItem

from lib.utils.general.utils import build_list_item, set_pluging_category
from lib.utils.kodi.utils import (
    JACKTORR_ADDON,
    JACKTORR_ADDON_ID,
    end_of_directory,
    get_addon_handle,
    notification,
    translation,
)
from lib.utils.torrent.torrserver_init import get_torrserver_api

JACKTORR_PLAY_MAGNET_URL = f"plugin://{JACKTORR_ADDON_ID}/play_magnet"


def _torznab_play_url(magnet, title=""):
    """Build the jacktorr addon play_magnet URL for a torznab result.

    Playback is delegated to the jacktorr addon, same as the info-hash
    playback used by the torrents navigation.
    """
    params = f"magnet={quote(magnet)}&buffer=true&poster="
    if title:
        params += "&title=" + quote(title)
    return f"{JACKTORR_PLAY_MAGNET_URL}?{params}"


def _torznab_disabled_on_server(api):
    """Return True only when TorrServer reports Torznab search disabled.

    An unreadable or malformed settings payload must not claim it.
    """
    try:
        settings = api.get_settings()
    except Exception:
        return False
    if not isinstance(settings, dict):
        return False
    return settings.get("EnableTorznabSearch") is False


def _torznab_label(result):
    """Build the list item label for one torznab result."""
    label = result.get("Title", "") or result.get("Name", "")
    tracker = result.get("Tracker")
    if tracker:
        label = f"{label} [{tracker}]"
    size = result.get("Size", "")
    if size:
        label = f"{label} ({size})"
    return label


def torznab_search(params):
    if not JACKTORR_ADDON:
        notification(translation(30253))
        end_of_directory(cache=False)
        return

    api = get_torrserver_api()
    if api is None:
        notification(translation(30253))
        end_of_directory(cache=False)
        return

    set_pluging_category(translation(91064))
    query = (xbmcgui.Dialog().input(translation(91065)) or "").strip()
    if not query:
        end_of_directory(cache=False)
        return

    try:
        results = api.search_torznab(query)
    except Exception:
        # TorrServerError already surfaced the failure as a notification.
        end_of_directory(cache=False)
        return

    if not results:
        disabled = _torznab_disabled_on_server(api)
        notification(translation(91067 if disabled else 91066))
        end_of_directory(cache=False)
        return

    for result in results:
        if not isinstance(result, dict):
            continue
        magnet = result.get("Magnet", "")
        if not magnet:
            continue
        title = result.get("Title", "") or result.get("Name", "")
        item = build_list_item(_torznab_label(result), "magnet.png")
        item.setProperty("IsPlayable", "true")
        addDirectoryItem(get_addon_handle(), _torznab_play_url(magnet, title), item, isFolder=False)
    end_of_directory()
