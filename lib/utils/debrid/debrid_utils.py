import base64
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import requests
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

from lib.api.debrid.base import ProviderException
from lib.clients.debrid.alldebrid import AllDebridHelper
from lib.clients.debrid.debrider import DebriderHelper
from lib.clients.debrid.easydebrid import EasyDebridHelper
from lib.clients.debrid.premiumize import PremiumizeHelper
from lib.clients.debrid.torbox import TorboxHelper
from lib.clients.debrid.realdebrid import RealDebridHelper
from lib.utils.kodi.utils import get_setting, kodilog, notification, translation
from lib.utils.torrent.torrserver_utils import extract_torrent_metadata
from lib.utils.general.utils import (
    USER_AGENT_HEADER,
    DebridType,
    Indexer,
    IndexerType,
    get_cached,
    get_info_hash_from_magnet,
    info_hash_to_magnet,
    is_ad_enabled,
    is_debrider_enabled,
    is_ed_enabled,
    is_pm_enabled,
    is_rd_enabled,
    is_tb_enabled,
    is_url,
    set_cached,
)
from lib.domain.torrent import TorrentStream
from lib.utils.kodi.logging import summarize_locator_for_log

from xbmcgui import Dialog
from xbmc import LOGDEBUG


DEBRID_HELPERS = {
    DebridType.RD: RealDebridHelper,
    DebridType.PM: PremiumizeHelper,
    DebridType.TB: TorboxHelper,
    DebridType.DB: DebriderHelper,
    DebridType.AD: AllDebridHelper,
    DebridType.ED: EasyDebridHelper,
}

DEBRID_CHECKS = {
    DebridType.RD: is_rd_enabled,
    DebridType.TB: is_tb_enabled,
    DebridType.PM: is_pm_enabled,
    DebridType.DB: is_debrider_enabled,
    DebridType.AD: is_ad_enabled,
}

PACK_DIRECT_DEBRID_TYPES = {DebridType.RD, DebridType.TB, DebridType.AD}

SUPPORTED_CLOUD_TRANSFER_DEBRIDS = (
    DebridType.RD,
    DebridType.AD,
    DebridType.TB,
    DebridType.DB,
)


def get_debrid_helper(debrid_type: str):
    helper_cls = DEBRID_HELPERS.get(debrid_type)
    if not helper_cls:
        notification(f"Unknown debrid type: {debrid_type}")
        raise ValueError(f"Unknown debrid type: {debrid_type}")
    return helper_cls()


def get_enabled_cloud_transfer_debrids() -> List[str]:
    return [
        debrid_type
        for debrid_type in SUPPORTED_CLOUD_TRANSFER_DEBRIDS
        if DEBRID_CHECKS.get(debrid_type, lambda: False)()
    ]


def choose_debrid_for_transfer(preferred_debrid: str = "") -> Optional[str]:
    enabled_debrids = get_enabled_cloud_transfer_debrids()
    if not enabled_debrids:
        notification(translation(90364))
        return None

    if preferred_debrid in enabled_debrids:
        return preferred_debrid

    if len(enabled_debrids) == 1:
        return enabled_debrids[0]

    selected = Dialog().select(translation(90363), enabled_debrids)
    if selected < 0:
        return None
    return enabled_debrids[selected]


def _is_torrent_ready_in_debrid(debrid_type: str, info_hash: str) -> bool:
    """Check if a torrent is ready/cached in the specified debrid service."""
    if not info_hash:
        return False
    
    try:
        if debrid_type == DebridType.RD:
            torrent_info = RealDebridHelper().client.get_available_torrent(info_hash)
            if torrent_info and torrent_info.get("status") == "downloaded":
                return True
        elif debrid_type == DebridType.AD:
            result = AllDebridHelper().client.add_magnet(info_hash_to_magnet(info_hash))
            magnet = result.get("data", {}).get("magnets", [])[0]
            if magnet and magnet.get("ready"):
                return True
        elif debrid_type == DebridType.TB:
            torrent_info = TorboxHelper().client.get_available_torrent(info_hash)
            if (torrent_info and 
                torrent_info.get("download_finished") and 
                torrent_info.get("download_present")):
                return True
        elif debrid_type == DebridType.DB:
            info = DebriderHelper().get_info(info_hash)
            if info and info.get("files"):
                return True
    except Exception as e:
        kodilog(f"Error checking if torrent is ready in {debrid_type}: {e}")
    
    return False


def _add_to_realdebrid(info_hash: str, torrent_data: bytes, torrent_name: str):
    if torrent_data:
        kodilog("Debrid transfer path: uploading torrent file to RD")
        return RealDebridHelper().add_torrent_file(torrent_data, torrent_name=torrent_name)
    elif info_hash:
        kodilog("Debrid transfer path: sending magnet/info_hash to RD")
        return RealDebridHelper().add_magnet(info_hash)
    notification(translation(90361))
    return None


def _add_to_alldebrid(info_hash: str, torrent_data: bytes, torrent_name: str):
    if torrent_data:
        kodilog("Debrid transfer path: uploading torrent file to AD")
        return AllDebridHelper().add_torrent_file(torrent_data, torrent_name=torrent_name)
    elif info_hash:
        kodilog("Debrid transfer path: sending magnet/info_hash to AD")
        return AllDebridHelper().client.add_magnet(info_hash_to_magnet(info_hash))
    notification(translation(90361))
    return None


def _add_to_torbox(info_hash: str, torrent_data: bytes, torrent_name: str):
    if torrent_data:
        kodilog("Debrid transfer path: uploading torrent file to TB")
        return TorboxHelper().add_torrent_file(torrent_data, torrent_name=torrent_name)
    elif info_hash:
        kodilog("Debrid transfer path: sending magnet/info_hash to TB")
        return TorboxHelper().add_torbox_torrent(info_hash)
    notification(translation(90361))
    return None


def _add_to_debrider(info_hash: str):
    if not info_hash:
        notification(translation(90361))
        return None
    kodilog("Debrid transfer path: sending magnet/info_hash to DB")
    return DebriderHelper().add_magnet(info_hash)


_DEBRID_ADDERS = {
    DebridType.RD: _add_to_realdebrid,
    DebridType.AD: _add_to_alldebrid,
    DebridType.TB: _add_to_torbox,
    DebridType.DB: _add_to_debrider,
}


def add_source_to_debrid(
    info_hash: str,
    preferred_debrid: str = "",
    torrent_data: bytes = b"",
    torrent_name: str = "",
) -> Optional[str]:
    debrid_type = choose_debrid_for_transfer(preferred_debrid)
    if not debrid_type:
        return None

    try:
        adder = _DEBRID_ADDERS.get(debrid_type)
        if not adder:
            raise ValueError(f"Unsupported debrid cloud transfer type: {debrid_type}")
        
        if debrid_type == DebridType.DB:
            result = adder(info_hash)
        else:
            result = adder(info_hash, torrent_data, torrent_name)
        
        if not result:
            raise ProviderException(f"Failed to add torrent to {debrid_type}: no response data")

        kodilog(f"Debrid transfer succeeded: debrid={debrid_type}, result={result is not None}")
        
        is_ready = _is_torrent_ready_in_debrid(debrid_type, info_hash)
        if is_ready:
            notification(translation(90362) % debrid_type)
        else:
            notification(translation(90694) % debrid_type)
        
        return debrid_type
    except Exception as exc:
        kodilog(f"Failed to add source to debrid cloud: {exc}")
        notification(str(exc))
        return None


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

    if direct_results and not results:
        kodilog("Only direct results found, returning them.")
        return direct_results

    check_functions = get_debrid_check_functions()
    if not check_functions:
        kodilog("No debrid services enabled for caching check.")
        return direct_results

    execute_debrid_checks(
        check_functions, results, cached_results, uncached_results, dialog, lock
    )

    cached_results.extend(direct_results)
    if should_include_uncached():
        cached_results.extend(uncached_results)

    kodilog(f"Cached results: {len(cached_results)}")

    update_cache(query, mode, media_type, cached_results, episode)
    return cached_results


def get_cached_results(
    query: Optional[str], mode: str, media_type: str, episode: int
) -> Optional[List[TorrentStream]]:
    if query:
        params = (episode, "deb") if mode == "tv" or media_type == "tv" else ("deb",)
        cached_results = get_cached(query, params=params)
        return cached_results if isinstance(cached_results, list) else None
    return None


def get_debrid_check_functions() -> List:
    check_functions = []
    for debrid_type, is_enabled in DEBRID_CHECKS.items():
        if is_enabled():
            check_functions.append(get_debrid_helper(debrid_type).check_cached)
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
        max_workers=int(get_setting("thread_number", 6))
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
            try:
                future.result()
            except Exception as exc:
                kodilog(f"Debrid cache check failed: {exc}")


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


def get_source_status(res: TorrentStream) -> str:
    is_cached = res.isCached
    added_label = f"{res.debridType} Added".strip() if res.debridType else "Added"

    if res.isPack:
        if is_cached:
            label = f"[B]Cached-[Pack][/B]"
        elif res.addedToDebrid:
            label = f"[B]{added_label}-[Pack][/B]"
        else:
            label = f"[B]Download-[Pack][/B]"
    else:
        if is_cached:
            label = f"[B]Cached[/B]"
        elif res.addedToDebrid:
            label = f"[B]{added_label}[/B]"
        else:
            label = f"[B]Download[/B]"
    return label


def get_pack_info(debrid_type, info_hash):
    return get_debrid_helper(debrid_type).get_pack_info(info_hash)


def filter_results(
    results: List[TorrentStream], direct_results: List[TorrentStream]
) -> None:
    filtered_results = []
    dropped_results = []

    for res in copy.deepcopy(results):
        info_hash = extract_info_hash(res)
        if info_hash:
            res.infoHash = info_hash
            filtered_results.append(res)
        elif res.indexer in [Indexer.TELEGRAM, Indexer.EASYNEWS] or res.type in [
            IndexerType.STREMIO_DEBRID,
            IndexerType.DIRECT,
        ]:
            direct_results.append(res)
        else:
            dropped_results.append(res)

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


def get_torrent_data_from_uri(uri: str) -> Tuple[bytes, str, str, str]:
    kodilog(f"get_torrent_data_from_uri: Checking URI: {uri}", level=LOGDEBUG)
    torrent_data = b""
    magnet = ""
    info_hash = ""
    torrent_url = ""

    if not is_url(uri):
        return torrent_data, magnet, info_hash, torrent_url

    try:
        current_uri = uri
        for redirect_count in range(5):
            res = requests.get(
                current_uri,
                allow_redirects=False,
                timeout=10,
                headers=USER_AGENT_HEADER,
            )
            kodilog(
                "get_torrent_data_from_uri: GET request to {} returned status code: {}".format(
                    summarize_locator_for_log(current_uri),
                    res.status_code,
                )
            )

            if 300 <= res.status_code < 400:
                location = res.headers.get("Location", "")
                if not location:
                    break

                kodilog(
                    "get_torrent_data_from_uri: Redirect {} -> {}".format(
                        summarize_locator_for_log(current_uri),
                        summarize_locator_for_log(location),
                    )
                )

                if location.startswith("magnet:?"):
                    magnet = location
                    info_hash = get_info_hash_from_magnet(magnet).lower()
                    return torrent_data, magnet, info_hash, torrent_url

                current_uri = urljoin(current_uri, location)
                continue

            if res.status_code == 200:
                kodilog(
                    "get_torrent_data_from_uri: Processing content from {}".format(
                        summarize_locator_for_log(current_uri)
                    )
                )
                if res.url.startswith("magnet:"):
                    magnet = str(res.url or "")
                    info_hash = get_info_hash_from_magnet(magnet).lower()
                    return torrent_data, magnet, info_hash, torrent_url

                magnet = extract_torrent_metadata(res.content)
                kodilog(
                    "get_torrent_data_from_uri: Extracted magnet: {}".format(
                        summarize_locator_for_log(magnet)
                    )
                )
                if magnet:
                    torrent_data = bytes(res.content or b"")
                    info_hash = get_info_hash_from_magnet(magnet).lower()
                    torrent_url = current_uri
                    kodilog(
                        "get_torrent_data_from_uri: Preserving torrent URL for playback: {}".format(
                            summarize_locator_for_log(torrent_url)
                        )
                    )
                return torrent_data, str(magnet or ""), str(info_hash or ""), str(
                    torrent_url or ""
                )

            break
    except Exception as e:
        kodilog(f"get_torrent_data_from_uri: Exception occurred for uri: {uri}: {e}")
    return torrent_data, str(magnet or ""), str(info_hash or ""), str(torrent_url or "")


def get_magnet_from_uri(uri: str) -> Tuple[str, str, str]:
    _, magnet, info_hash, torrent_url = get_torrent_data_from_uri(uri)
    return magnet, info_hash, torrent_url


def get_debrid_direct_url(debrid_type, data) -> Optional[Dict[str, Any]]:
    info_hash = data.get("info_hash", "")
    try:
        return get_debrid_helper(debrid_type).get_link(info_hash, data)
    except ValueError as e:
        kodilog(f"Unknown debrid type: {debrid_type}: {e}")
        return None
    except Exception as e:
        kodilog(f"get_debrid_direct_url failed: {e}")
        return None


def get_debrid_pack_direct_url(debrid_type, data) -> Optional[Dict[str, Any]]:
    if debrid_type not in PACK_DIRECT_DEBRID_TYPES:
        kodilog(f"Unknown debrid type for pack link: {debrid_type}")
        return None

    return get_debrid_helper(debrid_type).get_pack_link(data)


def is_supported_debrid_type(debrid_type: str) -> bool:
    return debrid_type in DEBRID_HELPERS


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
