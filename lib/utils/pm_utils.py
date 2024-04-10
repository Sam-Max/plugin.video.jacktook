from lib.api.premiumize_api import Premiumize
from lib.utils.kodi import get_setting, log
from lib.utils.utils import get_cached, info_hash_to_magnet, set_cached, supported_video_extensions


def get_pm_pack(info_hash):
    info = get_cached(info_hash)
    if info:
        return info
    extensions = supported_video_extensions()[:-1]
    pm_client = Premiumize(token=get_setting("premiumize_token"))
    magnet = info_hash_to_magnet(info_hash)
    response_data = pm_client.create_download_link(magnet)
    if "error" in response_data.get("status"):
        log(f"Failed to get link from Premiumize {response_data.get('message')}")
        return
    info = []
    for item in response_data.get("content"):
        name = item.get("path").rsplit("/", 1)[-1]
        if (
            any(name.lower().endswith(x) for x in extensions)
            and not item.get("link", "") == ""
        ):
            title = f"[B][Cached][/B]-{name}"
            info.append((item["link"], title))
    if info:
        set_cached(info, info_hash)
        return info


def get_pm_link(client, infoHash):
    magnet = info_hash_to_magnet(infoHash)
    response_data = client.create_download_link(magnet)
    if "error" in response_data.get("status"):
        log(f"Failed to get link from Premiumize {response_data.get('message')}")
        return
    content = response_data.get("content")
    selected_file = max(content, key=lambda x: x.get("size", 0))
    return selected_file["stream_link"]