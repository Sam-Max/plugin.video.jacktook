import copy
import os
from lib.clients.debrid.premiumize import Premiumize
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import ADDON_PATH, get_setting, notification, url_for
from lib.utils.utils import (
    debrid_dialog_update,
    get_cached,
    info_hash_to_magnet,
    set_cached,
    supported_video_extensions,
)
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem


pm_client = Premiumize(token=get_setting("premiumize_token"))


def check_pm_cached(results, cached_results, uncached_result, total, dialog, lock):
    kodilog("debrid::check_pm_cached")
    hashes = [res.get("infoHash") for res in results]
    cached_torrents = pm_client.get_torrent_instant_availability(hashes)
    cached_response = cached_torrents.get("response")
    for e, res in enumerate(copy.deepcopy(results)):
        debrid_dialog_update("PM", total, dialog, lock)
        res["debridType"] = "PM"
        if cached_response[e] is True:
            res["isDebrid"] = True
            cached_results.append(res)
        else:
            res["isDebrid"] = False
            uncached_result.append(res)


def get_pm_link(infoHash):
    magnet = info_hash_to_magnet(infoHash)
    response_data = pm_client.create_download_link(magnet)
    if "error" in response_data.get("status"):
        kodilog(f"Failed to get link from Premiumize {response_data.get('message')}")
        return
    content = response_data.get("content")
    selected_file = max(content, key=lambda x: x.get("size", 0))
    return selected_file["stream_link"]


def get_pm_pack_info(info_hash):
    info = get_cached(info_hash)
    if info:
        return info
    extensions = supported_video_extensions()[:-1]
    magnet = info_hash_to_magnet(info_hash)
    response_data = pm_client.create_download_link(magnet)
    if "error" in response_data.get("status"):
        notification(
            f"Failed to get link from Premiumize {response_data.get('message')}"
        )
        return
    info = {}
    if response_data.get("content") > 0:
        for item in response_data.get("content"):
            name = item.get("path").rsplit("/", 1)[-1]
            if (
                any(name.lower().endswith(x) for x in extensions)
                and not item.get("link", "") == ""
            ):
                title = f"[B][Cached][/B]-{name}"
                info["files"] = (item["link"], title)
        if info:
            set_cached(info, info_hash)
            return info
    else:
        notification("Not a torrent pack")
        return


def show_pm_pack_info(info, ids, debrid_type, tv_data, mode, plugin):
    for url, title in info["files"]:
        list_item = ListItem(label=f"{title}")
        list_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png")}
        )
        addDirectoryItem(
            plugin.handle,
            url_for(
                name="play_torrent",
                title=title,
                mode=mode,
                is_torrent=False,
                data={
                    "ids": ids,
                    "url": url,
                    "tv_data": tv_data,
                    "debrid_info": {
                        "debrid_type": debrid_type,
                        "is_debrid_pack": True,
                    },
                },
            ),
            list_item,
            isFolder=False,
        )
