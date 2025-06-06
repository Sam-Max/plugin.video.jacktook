from lib.utils.general.utils import set_media_infoTag
from lib.utils.kodi.utils import ADDON_HANDLE
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem


def add_kodi_dir_item(
    label,
    url,
    is_folder,
    info_labels=None,
    metadata=None,
    mode=None,
    context_menu=None,
    is_playable=False,
):
    list_item = ListItem(label)
    if info_labels:
        list_item.setInfo("video", info_labels)
    if metadata:
        set_media_infoTag(list_item, metadata=metadata, mode=mode)
    if is_playable:
        list_item.setProperty("IsPlayable", "true")
    if context_menu:
        list_item.addContextMenuItems(context_menu)
    addDirectoryItem(ADDON_HANDLE, url, list_item, isFolder=is_folder)



def extract_ids(res, mode="tv"):
    ids = res.get("show" if mode == "tv" else "movie", {}).get("ids", {})
    return {
        "tmdb_id": ids.get("tmdb"),
        "tvdb_id": ids.get("tvdb") if mode == "tv" else None,
        "imdb_id": ids.get("imdb"),
    }
