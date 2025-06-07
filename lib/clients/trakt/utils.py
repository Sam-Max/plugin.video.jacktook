from lib.utils.kodi.utils import ADDON_HANDLE

from xbmcplugin import addDirectoryItem


def add_kodi_dir_item(
    list_item,
    url,
    is_folder,
    is_playable=False,
):
    if is_playable:
        list_item.setProperty("IsPlayable", "true")
    addDirectoryItem(ADDON_HANDLE, url, list_item, isFolder=is_folder)


def extract_ids(res, mode="tv"):
    ids = res.get("show" if mode == "tv" else "movie", {}).get("ids", {})
    return {
        "tmdb_id": ids.get("tmdb"),
        "tvdb_id": ids.get("tvdb") if mode == "tv" else None,
        "imdb_id": ids.get("imdb"),
    }
