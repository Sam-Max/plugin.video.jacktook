from lib.api.debrid_apis.premiumize_api import Premiumize
from lib.api.jacktook.kodi import kodilog
from lib.utils.kodi_utils import get_setting, notification
from lib.utils.general_utils import (
    get_cached,
    info_hash_to_magnet,
    set_cached,
    supported_video_extensions,
)

pm_client = Premiumize(token=get_setting("premiumize_token"))


def get_pm_pack_info(info_hash):
    info = get_cached(info_hash)
    if info:
        return info
    extensions = supported_video_extensions()[:-1]
    magnet = info_hash_to_magnet(info_hash)
    response_data = pm_client.create_download_link(magnet)
    if "error" in response_data.get("status"):
        notification(f"Failed to get link from Premiumize {response_data.get('message')}")
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


def get_pm_link(infoHash):
    magnet = info_hash_to_magnet(infoHash)
    response_data = pm_client.create_download_link(magnet)
    if "error" in response_data.get("status"):
        kodilog(f"Failed to get link from Premiumize {response_data.get('message')}")
        return
    content = response_data.get("content")
    selected_file = max(content, key=lambda x: x.get("size", 0))
    return selected_file["stream_link"]
