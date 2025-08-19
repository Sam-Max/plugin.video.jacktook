import base64
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import requests
from threading import Lock
from typing import Any, Dict, List, Optional

from lib.utils.debrid.debrider_helper import DebriderHelper
from lib.utils.debrid.pm_helper import PremiumizeHelper
from lib.utils.debrid.torbox_helper import TorboxHelper
from lib.utils.debrid.rd_helper import RealDebridHelper
from lib.utils.kodi.utils import get_setting, kodilog
from lib.utils.torrent.torrserver_utils import extract_magnet_from_url
from lib.utils.general.utils import (
    USER_AGENT_HEADER,
    DebridType,
    Indexer,
    IndexerType,
    get_cached,
    get_info_hash_from_magnet,
    is_debrider_enabled,
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
        check_functions.append(RealDebridHelper().check_cached)
    if is_tb_enabled():
        check_functions.append(TorboxHelper().check_cached)
    if is_pm_enabled():
        check_functions.append(PremiumizeHelper().check_cached)
    if is_debrider_enabled():
        check_functions.append(DebriderHelper().check_cached)
    return check_functions


def execute_debrid_checks(
    check_functions: List,
    results: List[TorrentStream],
    cached_results: list,
    uncached_results: list,
    dialog: Dialog,
    lock: Lock,
):
    with ThreadPoolExecutor(
        max_workers=int(get_setting("thread_number", 8))
    ) as executor:
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
    return any([is_tb_enabled(), is_pm_enabled(), is_ed_enabled()]) and bool(
        get_setting("show_uncached")
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
    is_cached = res.isCached

    if res.isPack:
        if is_cached:
            label = f"[B]Cached-[Pack][/B]"
        else:
            label = f"[B]Download-[Pack][/B]"
    else:
        if is_cached:
            label = f"[B]Cached[/B]"
        else:
            label = f"[B]Download[/B]"
    return label


def get_pack_info(debrid_type, info_hash):
    if debrid_type == DebridType.PM:
        info = PremiumizeHelper().get_pack_info(info_hash)
    elif debrid_type == DebridType.TB:
        info = TorboxHelper().get_pack_info(info_hash)
    elif debrid_type == DebridType.RD:
        info = RealDebridHelper().get_pack_info(info_hash)
    elif debrid_type == DebridType.DB:
        info = DebriderHelper().get_pack_info(info_hash)
    else:
        kodilog(f"Unknown debrid type: {debrid_type}")
        info = {}
    return info


def filter_results(
    results: List[TorrentStream], direct_results: List[TorrentStream]
) -> None:
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
                    if uri and uri.startswith("magnet:"):
                        magnet = uri
                        info_hash = get_info_hash_from_magnet(uri).lower()
                elif res.headers.get("Content-Type") == "application/octet-stream":
                    magnet = extract_magnet_from_url(uri)
        except Exception as e:
            kodilog(f"Failed to extract torrent data from: {str(e)}")
    return magnet, info_hash


def get_debrid_direct_url(debrid_type, data) -> Optional[Dict[str, Any]]:
    info_hash = data.get("info_hash", "")
    if debrid_type == DebridType.RD:
        return RealDebridHelper().get_link(info_hash, data)
    elif debrid_type == DebridType.PM:
        return PremiumizeHelper().get_link(info_hash, data)
    elif debrid_type == DebridType.TB:
        return TorboxHelper().get_link(info_hash, data)
    elif debrid_type == DebridType.DB:
        return DebriderHelper().get_link(info_hash, data)
    else:
        kodilog(f"Unknown debrid type: {debrid_type}")
        return None


def get_debrid_pack_direct_url(debrid_type, data) -> Optional[Dict[str, Any]]:
    if debrid_type == DebridType.RD:
        return RealDebridHelper().get_pack_link(data)
    elif debrid_type == DebridType.TB:
        return TorboxHelper().get_pack_link(data)
    else:
        kodilog(f"Unknown debrid type for pack link: {type}")
        return None


def process_external_cache(data: dict, debrid: str, token: str, url: str):
    try:
        imdb_id = data.get("imdb_id")
        season = data.get("season")
        episode = data.get("episode")
        mode = data.get("mode", data.get("media_type", "movie"))

        if "torrentio" in url:
            service = "torrentio"
        elif "mediafusion" in url:
            service = "mediafusion"
        elif "comet" in url:
            service = "comet"
        else:
            return None

        if not imdb_id:
            raise ValueError("Missing IMDb ID in input data")

        if service == "mediafusion":
            base_link = f"https://mediafusion.elfhosted.com/{debrid}={token}"
            params = {
                "enable_catalogs": False,
                "max_streams_per_resolution": 99,
                "torrent_sorting_priority": [],
                "certification_filter": ["Disable"],
                "nudity_filter": ["Disable"],
                "streaming_provider": {
                    "token": token,
                    "service": debrid,
                    "only_show_cached_streams": True,
                },
            }
            headers = {
                "encoded_user_data": base64.b64encode(
                    json.dumps(params).encode("utf-8")
                ).decode("utf-8")
            }

        elif service == "comet":
            params = {
                "maxResultsPerResolution": 0,
                "maxSize": 0,
                "cachedOnly": True,
                "removeTrash": True,
                "resultFormat": ["title", "size"],
                "debridService": debrid,
                "debridApiKey": token,
                "debridStreamProxyPassword": "",
                "languages": {"required": [], "exclude": [], "preferred": []},
                "resolutions": {},
                "options": {
                    "remove_ranks_under": -10000000000,
                    "allow_english_in_languages": False,
                    "remove_unknown_languages": False,
                },
            }
            params_encoded = base64.b64encode(
                json.dumps(params).encode("utf-8")
            ).decode("utf-8")
            base_link = f"https://comet.elfhosted.com/{params_encoded}"
            headers = {}

        else:  # torrentio fallback
            base_link = f"https://torrentio.strem.fun/{debrid}={token}"
            headers = {"User-Agent": "Mozilla/5.0"}

        # Choose endpoint based on media type
        if mode == "tv":
            endpoint = f"/stream/series/{imdb_id}:{season}:{episode}.json"
        else:
            endpoint = f"/stream/movie/{imdb_id}.json"

        url = f"{base_link}{endpoint}"
        response = requests.get(url, headers=headers, timeout=9)
        response.raise_for_status()
        return response
    except Exception as e:
        kodilog(f"Error checking cache for {url}: {e}")
        return None
