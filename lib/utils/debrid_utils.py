import requests
import requests
from threading import Lock
from lib.api.jacktook.kodi import kodilog
from lib.utils.ed_utils import check_ed_cached, get_ed_link
from lib.utils.kodi_utils import get_setting
from lib.utils.pm_utils import check_pm_cached, get_pm_link
from lib.utils.rd_utils import check_rd_cached, get_rd_link, get_rd_pack_link
from lib.utils.torbox_utils import check_torbox_cached, get_torbox_link, get_torbox_pack_link
from lib.utils.torrent_utils import extract_magnet_from_url
from lib.utils.utils import (
    USER_AGENT_HEADER,
    get_cached,
    get_info_hash_from_magnet,
    is_ed_enabled,
    is_pm_enabled,
    is_rd_enabled,
    is_tb_enabled,
    is_url,
    set_cached,
    dialog_update,
)

def check_debrid_cached(query, results, mode, media_type, dialog, rescrape, episode=1):
    if not rescrape:
        debrid_cached_check = get_setting("debrid_cached_check")
        if debrid_cached_check:
            if query:
                if mode == "tv" or media_type == "tv":
                    cached_results = get_cached(query, params=(episode, "deb"))
                else:
                    cached_results = get_cached(query, params=("deb"))

                if cached_results:
                    return cached_results

    lock = Lock()
    cached_results = []
    uncached_results = []
    total = len(results)

    extract_infohash(results, dialog)

    if is_rd_enabled():
        check_rd_cached(results, cached_results, uncached_results, total, dialog, lock)
    
    if is_tb_enabled():
        check_torbox_cached(
            results, cached_results, uncached_results, total, dialog, lock
        )
    if is_pm_enabled():
        check_pm_cached(results, cached_results, uncached_results, total, dialog, lock)

    if is_ed_enabled():
        check_ed_cached(results, cached_results, uncached_results, total, dialog, lock)

    if is_tb_enabled() or is_pm_enabled():
        if get_setting("show_uncached"):
            cached_results.extend(uncached_results)

    dialog_update["count"] = -1
    dialog_update["percent"] = 50

    if query:
        if mode == "tv" or media_type == "tv":
            set_cached(cached_results, query, params=(episode, "deb"))
        else:
            set_cached(cached_results, query, params=("deb"))

    return cached_results


def extract_infohash(results, dialog):
    for count, res in enumerate(results[:]):
        dialog.update(
            0,
            "Jacktook [COLOR FFFF6B00]Debrid[/COLOR]",
            f"Processing...{count}/{len(results)}",
        )

        info_hash = None
        if res.get("infoHash"):
            info_hash = res["infoHash"].lower()
        elif (guid := res.get("guid", "")) and (
            guid.startswith("magnet:?") or len(guid) == 40
        ):
            info_hash = get_info_hash_from_magnet(guid).lower()
        elif (
            url := res.get("magnetUrl", "") or res.get("downloadUrl", "")
        ) and url.startswith("magnet:?"):
            info_hash = get_info_hash_from_magnet(url).lower()

        if info_hash:
            res["infoHash"] = info_hash
        else:
            results.remove(res)


def get_magnet_from_uri(uri):
    magnet = info_hash = ""
    if is_url(uri):
        try:
            res = requests.head(
                uri, allow_redirects=False, timeout=10, headers=USER_AGENT_HEADER
            )
            if res.status_code == 200:
                if res.is_redirect:
                    uri = res.headers.get("Location")
                    if uri.startswith("magnet:"):
                        magnet = uri
                        info_hash = get_info_hash_from_magnet(uri).lower()
                elif res.headers.get("Content-Type") == "application/octet-stream":
                    magnet = extract_magnet_from_url(uri)
        except Exception as e:
            kodilog(f"Failed to extract torrent data from: {str(e)}")
    return magnet, info_hash


def get_debrid_direct_url(info_hash, debrid_type):
    if debrid_type == "RD":
        return get_rd_link(info_hash)
    elif debrid_type == "PM":
        return get_pm_link(info_hash)
    elif debrid_type == "TB":
        return get_torbox_link(info_hash)
    elif debrid_type == "ED":
        return get_ed_link(info_hash)


def get_debrid_pack_direct_url(file_id, torrent_id, debrid_type):
    if debrid_type == "RD":
        return get_rd_pack_link(file_id, torrent_id)
    elif debrid_type == "TB":
        return get_torbox_pack_link(file_id, torrent_id)
