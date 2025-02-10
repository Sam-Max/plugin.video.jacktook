from concurrent.futures import ThreadPoolExecutor
import copy
import requests
from threading import Lock
from lib.api.jacktook.kodi import kodilog
from lib.utils.ed_utils import EasyDebridHelper
from lib.utils.kodi_utils import get_setting
from lib.utils.pm_utils import PremiumizeHelper
from lib.utils.rd_utils import RealDebridHelper
from lib.utils.torbox_utils import TorboxHelper
from lib.utils.torrent_utils import extract_magnet_from_url
from lib.utils.utils import (
    USER_AGENT_HEADER,
    Debrids,
    Indexer,
    IndexerType,
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
    direct_results = []

    total = len(results)
    dialog.create("")

    filter_results(results, direct_results)

    check_functions = []
    if is_rd_enabled():
        check_functions.append(RealDebridHelper().check_rd_cached)
    if is_tb_enabled():
        check_functions.append(TorboxHelper().check_torbox_cached)
    if is_pm_enabled():
        check_functions.append(PremiumizeHelper().check_pm_cached)
    if is_ed_enabled():
        check_functions.append(EasyDebridHelper().check_ed_cached)

    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                fn, results, cached_results, uncached_results, total, dialog, lock
            )
            for fn in check_functions
        ]
        for future in futures:
            future.result()

    cached_results.extend(direct_results)

    if any([is_tb_enabled(), is_pm_enabled(), is_ed_enabled()]) and get_setting(
        "show_uncached"
    ):
        cached_results.extend(uncached_results)

    dialog_update["count"] = -1
    dialog_update["percent"] = 50

    if query:
        if mode == "tv" or media_type == "tv":
            set_cached(cached_results, query, params=(episode, "deb"))
        else:
            set_cached(cached_results, query, params=("deb"))

    return cached_results


def get_debrid_status(res):
    type = res.get("type")

    if res.get("isPack"):
        if type == Debrids.RD:
            status_string = get_rd_status_pack(res)
        else:
            status_string = f"[B]Cached-Pack[/B]"
    else:
        if type == Debrids.RD:
            status_string = get_rd_status(res)
        else:
            status_string = f"[B]Cached[/B]"

    return status_string


def get_rd_status(res):
    if res.get("isCached"):
        label = f"[B]Cached[/B]"
    else:
        label = f"[B]Download[/B]"
    return label


def get_rd_status_pack(res):
    if res.get("isCached"):
        label = f"[B]Pack-Cached[/B]"
    else:
        label = f"[B]Pack-Download[/B]"
    return label


def get_pack_info(type, info_hash):
    if type == Debrids.PM:
        info = PremiumizeHelper().get_pm_pack_info(info_hash)
    elif type == Debrids.TB:
        info = TorboxHelper().get_torbox_pack_info(info_hash)
    elif type == Debrids.RD:
        info = RealDebridHelper().get_rd_pack_info(info_hash)
    elif type == Debrids.ED:
        info = EasyDebridHelper().get_ed_pack_info(info_hash)
    return info


def filter_results(results, direct_results):
    filtered_results = []

    for res in copy.deepcopy(results):
        info_hash = extract_info_hash(res)

        if info_hash:
            res["infoHash"] = info_hash
            filtered_results.append(res)
        elif (
            res["indexer"] == Indexer.TELEGRAM
            or res["type"] == IndexerType.STREMIO_DEBRID
        ):
            direct_results.append(res)

    results[:] = filtered_results


def extract_info_hash(res):
    """Extracts and returns the info hash from a result if available."""
    if res.get("infoHash"):
        return res["infoHash"].lower()

    if (guid := res.get("guid", "")) and (
        guid.startswith("magnet:?") or len(guid) == 40
    ):
        return get_info_hash_from_magnet(guid).lower()

    url = res.get("magnetUrl", "") or res.get("downloadUrl", "")
    if url.startswith("magnet:?"):
        return get_info_hash_from_magnet(url).lower()

    return None


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


def get_debrid_direct_url(type, data):
    info_hash = data.get("info_hash", "")
    if type == Debrids.RD:
        return RealDebridHelper().get_rd_link(info_hash, data)
    elif type == Debrids.PM:
        return PremiumizeHelper().get_pm_link(info_hash)
    elif type == Debrids.TB:
        return TorboxHelper().get_torbox_link(info_hash)
    elif type == Debrids.ED:
        return EasyDebridHelper().get_ed_link(info_hash)


def get_debrid_pack_direct_url(file_id, torrent_id, type):
    if type == Debrids.RD:
        return RealDebridHelper().get_rd_pack_link(file_id, torrent_id)
    elif type == Debrids.TB:
        return TorboxHelper().get_torbox_pack_link(file_id, torrent_id)
