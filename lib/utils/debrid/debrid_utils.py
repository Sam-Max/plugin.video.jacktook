from concurrent.futures import ThreadPoolExecutor
import copy
import requests
from threading import Lock
from typing import List, Optional

from lib.utils.debrid.ed_utils import EasyDebridHelper
from lib.utils.debrid.pm_utils import PremiumizeHelper
from lib.utils.debrid.torbox_utils import TorboxHelper
from lib.utils.debrid.rd_utils import RealDebridHelper
from lib.utils.kodi.utils import get_setting, kodilog
from lib.utils.torrent.torrserver_utils import extract_magnet_from_url
from lib.utils.general.utils import (
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
)
from lib.domain.torrent import TorrentStream

from xbmcgui import Dialog



def check_debrid_cached(
    query: Optional[str],
    results: List[TorrentStream],
    mode: str,
    media_type: str,
    dialog: Dialog,
    rescrape: bool,
    episode: int = 1,
) -> List[TorrentStream]:

    kodilog("Checking debrid cached results...")

    if not rescrape:
        cached_results = get_cached_results(query, mode, media_type, episode)
        if cached_results:
            return cached_results

    lock = Lock()
    cached_results, uncached_results, direct_results = [], [], []

    dialog.create("")
    filter_results(results, direct_results)

    check_functions = get_debrid_check_functions()
    execute_debrid_checks(
        check_functions, results, cached_results, uncached_results, dialog, lock
    )

    cached_results.extend(direct_results)
    if should_include_uncached():
        cached_results.extend(uncached_results)

    kodilog(f"Cached results: {len(cached_results)}")

    update_cache(query, mode, media_type, cached_results, episode)
    return cached_results


def get_cached_results(query: Optional[str], mode: str, media_type: str, episode: int):
    if query:
        params = (episode, "deb") if mode == "tv" or media_type == "tv" else ("deb",)
        return get_cached(query, params=params)
    return None


def get_debrid_check_functions() -> List:
    check_functions = []
    if is_rd_enabled():
        check_functions.append(RealDebridHelper().check_rd_cached)
    if is_tb_enabled():
        check_functions.append(TorboxHelper().check_torbox_cached)
    if is_pm_enabled():
        check_functions.append(PremiumizeHelper().check_pm_cached)
    if is_ed_enabled():
        check_functions.append(EasyDebridHelper().check_ed_cached)
    return check_functions


def execute_debrid_checks(
    check_functions: List,
    results: List[TorrentStream],
    cached_results: list,
    uncached_results: list,
    dialog: Dialog,
    lock: Lock,
):
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                fn,
                results,
                cached_results,
                uncached_results,
                len(results),
                dialog,
                lock,
            )
            for fn in check_functions
        ]
        for future in futures:
            future.result()


def should_include_uncached() -> bool:
    return any([is_tb_enabled(), is_pm_enabled(), is_ed_enabled()]) and get_setting(
        "show_uncached"
    )


def update_cache(
    query: Optional[str],
    mode: str,
    media_type: str,
    cached_results: List[TorrentStream],
    episode: int,
):
    if query:
        params = (episode, "deb") if mode == "tv" or media_type == "tv" else ("deb",)
        set_cached(cached_results, query, params=params)


def get_debrid_status(res: TorrentStream) -> str:
    type = res.type

    if res.isPack:
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


def get_rd_status(res: TorrentStream) -> str:
    if res.isCached:
        label = f"[B]Cached[/B]"
    else:
        label = f"[B]Download[/B]"
    return label


def get_rd_status_pack(res: TorrentStream) -> str:
    if res.isCached:
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


def filter_results(results: List[TorrentStream], direct_results: List[dict]) -> None:
    filtered_results = []

    for res in copy.deepcopy(results):
        info_hash = extract_info_hash(res)
        if info_hash:
            res.infoHash = info_hash
            filtered_results.append(res)
        elif res.indexer == Indexer.TELEGRAM or res.type == IndexerType.STREMIO_DEBRID:
            direct_results.append(res)

    results[:] = filtered_results


def extract_info_hash(res: TorrentStream) -> Optional[str]:
    try:
        if res.infoHash:
            return res.infoHash.lower()

        if res.guid:
            if res.guid.startswith("magnet:?") or len(res.guid) == 40:
                info_hash = get_info_hash_from_magnet(res.guid)
                if info_hash:
                    return info_hash.lower()

        if res.url and res.url.startswith("magnet:?"):
            info_hash = get_info_hash_from_magnet(res.url)
            if info_hash:
                return info_hash.lower()
    except Exception as e:
        kodilog(f"Error extracting info hash from TorrentStream: {e}")

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
        return PremiumizeHelper().get_pm_link(info_hash, data)
    elif type == Debrids.TB:
        return TorboxHelper().get_torbox_link(info_hash)
    elif type == Debrids.ED:
        return EasyDebridHelper().get_ed_link(info_hash, data)


def get_debrid_pack_direct_url(file_id, torrent_id, type):
    if type == Debrids.RD:
        return RealDebridHelper().get_rd_pack_link(file_id, torrent_id)
    elif type == Debrids.TB:
        return TorboxHelper().get_torbox_pack_link(file_id, torrent_id)
