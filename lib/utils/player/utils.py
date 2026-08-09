from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote, urlparse

from xbmc import LOGDEBUG
from xbmcgui import Dialog

from lib.db.cached import cache
from lib.domain.torrent import TorrentStream
from lib.jacktook.utils import kodilog
from lib.utils.debrid.debrid_utils import (
    get_debrid_direct_url,
    get_debrid_pack_direct_url,
    is_supported_debrid_type,
)
from lib.utils.general.utils import (
    DebridType,
    Indexer,
    IndexerType,
    Players,
    torrent_clients,
)
from lib.utils.kodi.logging import summarize_locator_for_log
from lib.utils.parsers.pack_parser import (
    pack_scope_allows_transition,
    playback_pack_scope,
)
from lib.utils.kodi.utils import (
    execute_builtin,
    get_setting,
    is_elementum_addon,
    is_jacktorr_addon,
    is_torrest_addon,
    notification,
    translation,
)


def resolve_playback_url(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    indexer_type: str = data.get("type", "")
    debrid_type: str = data.get("debrid_type", "")
    is_pack: bool = data.get("is_pack", False)

    if indexer_type in [IndexerType.DIRECT, IndexerType.STREMIO_DEBRID]:
        if data.get("indexer") == Indexer.EASYNEWS:
            resolved_url = get_easynews_url(data)
            if resolved_url:
                data["url"] = resolved_url
                return data
            return None
        elif data.get("indexer") in [Indexer.JACKGRAM, Indexer.TELEGRAM]:
            token = get_setting("jackgram_token", "")
            url = data.get("url", "")
            if token and "|Authorization=Bearer" not in url:
                data["url"] = f"{url}|Authorization=Bearer {token}"
        return data

    if is_supported_debrid_type(debrid_type):
        debrid_url = get_debrid_url(data, debrid_type, is_pack)
        if debrid_url:
            return data
        return None

    addon_url = get_torrent_url(data)
    if addon_url:
        data["url"] = addon_url
        return data
    return None


def get_easynews_url(data: Dict[str, Any]) -> Optional[str]:
    from lib.clients.easynews import Easynews

    try:
        user = str(get_setting("easynews_user"))
        password = str(get_setting("easynews_password"))
        timeout = int(get_setting("easynews_timeout", "10") or "10")
        client = Easynews(user, password, timeout, notification)
        return client.resolve_url(data.get("url", ""))
    except Exception as e:
        kodilog(f"Error resolving Easynews link: {e}")
        return None


def get_torrent_url(data: Dict[str, Any], client: str = "") -> Optional[str]:
    magnet: str = data.get("magnet", "")
    url: str = data.get("url", "")
    mode: str = data.get("mode", "")
    ids: Any = data.get("ids", "")
    info_hash: str = data.get("info_hash", "")

    if not magnet and info_hash:
        from lib.utils.general.utils import info_hash_to_magnet

        magnet = info_hash_to_magnet(info_hash)

    if client:
        return get_torrent_url_for_client(magnet, url, mode, ids, client, data=data)

    if get_setting("torrent_enable"):
        return get_torrent_url_for_client(magnet, url, mode, ids, data=data)

    if data.get("is_torrent"):
        selected_client = get_torrent_client_selection(magnet, url, mode, ids)
        if selected_client:
            return get_torrent_url_for_client(magnet, url, mode, ids, selected_client, data=data)
        else:
            raise TorrentException("No torrent client selected")
    return None


def get_torrent_url_for_client(
    magnet: str,
    url: str,
    mode: str,
    ids: Any,
    client: str = "",
    data: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    torrent_client = client or str(get_setting("torrent_client"))
    if torrent_client in [Players.TORREST]:
        return get_torrest_url(magnet, url)
    elif torrent_client in [Players.ELEMENTUM]:
        return get_elementum_url(magnet, url, mode, ids, data=data)
    elif torrent_client in [Players.JACKTORR]:
        jacktorr_data = dict(data or {})
        jacktorr_data.pop("file_idx", None)
        jacktorr_data.pop("fileIdx", None)
        return get_jacktorr_url(magnet, url, data=jacktorr_data)
    else:
        raise TorrentException(f"Unknown torrent client selected: {torrent_client}")


def get_torrent_client_selection(magnet: str, url: str, mode: str, ids: Any) -> Optional[str]:
    chosen_client = Dialog().select(translation(90341), torrent_clients)
    if chosen_client < 0:
        return None
    return torrent_clients[chosen_client]


def get_debrid_url(
    data: Dict[str, Any], debrid_type: str, is_pack: bool
) -> Optional[Dict[str, Any]]:
    if is_pack and debrid_type in [DebridType.RD, DebridType.TB, DebridType.OC, DebridType.AD]:
        return get_debrid_pack_direct_url(debrid_type, data)
    else:
        return get_debrid_direct_url(debrid_type, data)


def get_elementum_url(
    magnet: str,
    url: str,
    mode: str,
    ids: Any,
    data: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    if not is_elementum_addon():
        if Dialog().yesno(
            translation(30252),
            translation(30254),
            yeslabel=translation(90605),
            nolabel=translation(90606),
        ):
            execute_builtin("InstallAddon(plugin.video.elementum)")
        else:
            notification(translation(30252))
            return None

    tmdb_id = ids.get("tmdb_id", "") if isinstance(ids, dict) else ""
    uri = url or magnet

    if not uri:
        raise TorrentException("No magnet or url found for Elementum playback")

    episode_params = ""
    tv_data = (data or {}).get("tv_data")
    if mode == "tv" and isinstance(tv_data, dict):
        season = tv_data.get("season")
        episode = tv_data.get("episode")
        if all(
            not isinstance(value, bool) and str(value).isdigit()
            for value in (tmdb_id, season, episode)
        ):
            episode_params = (
                f"&show={quote(str(tmdb_id))}"
                f"&season={quote(str(season))}"
                f"&episode={quote(str(episode))}"
            )

    return (
        f"plugin://plugin.video.elementum/play?uri={quote(uri)}"
        f"&type={mode}&tmdb={tmdb_id}{episode_params}"
    )


def build_elementum_pack_next_playback(
    data: Dict[str, Any], next_tv_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Build resolved PlayNext data when the selected Elementum pack covers it."""
    if data.get("mode") != "tv" or not isinstance(next_tv_data, dict):
        return None

    ids = data.get("ids")
    current_tv_data = data.get("tv_data")
    if not isinstance(ids, dict) or not isinstance(current_tv_data, dict):
        return None

    tmdb_id = ids.get("tmdb_id")
    current_season = current_tv_data.get("season")
    next_season = next_tv_data.get("season")
    next_episode = next_tv_data.get("episode")
    values = (tmdb_id, current_season, next_season, next_episode)
    if not all(not isinstance(value, bool) and str(value).isdigit() for value in values):
        return None

    pack_scope = playback_pack_scope(data, current_season=current_season)
    if not pack_scope.get("is_pack"):
        kodilog(
            f"[PLAYNEXT] Elementum pack reuse rejected: "
            f"type={pack_scope.get('pack_type')}, reason={pack_scope.get('pack_reason')}"
        )
        return None
    if not pack_scope_allows_transition(pack_scope, current_season, next_season):
        kodilog(
            f"[PLAYNEXT] Elementum pack reuse rejected for season transition "
            f"S{current_season}->S{next_season}: type={pack_scope.get('pack_type')}, "
            f"seasons={pack_scope.get('pack_seasons')}"
        )
        return None

    current_url = str(data.get("url") or "")
    parsed = urlparse(current_url)
    if (
        parsed.scheme != "plugin"
        or parsed.netloc != "plugin.video.elementum"
        or parsed.path.rstrip("/") != "/play"
    ):
        return None

    uri_values = parse_qs(parsed.query).get("uri") or []
    uri = str(uri_values[0]) if uri_values else str(data.get("magnet") or "")
    if not uri:
        return None

    next_data = dict(data)
    next_data["tv_data"] = dict(next_tv_data)
    next_data["playnext_context"] = True
    next_data["is_pack"] = True
    next_data["pack_type"] = pack_scope["pack_type"]
    next_data["pack_seasons"] = pack_scope["pack_seasons"]
    next_data["pack_reason"] = pack_scope["pack_reason"]
    for key in (
        "autoplay",
        "current_time",
        "direct_play",
        "next_tv_data",
        "progress",
        "resume",
        "subtitles_path",
        "stream_subtitles",
        "total_time",
    ):
        next_data.pop(key, None)

    magnet = uri if uri.startswith("magnet:") else ""
    torrent_url = "" if magnet else uri
    next_data["url"] = get_elementum_url(
        magnet,
        torrent_url,
        "tv",
        ids,
        data=next_data,
    )
    return next_data


def get_jacktorr_url(magnet: str, url: str, data: Optional[Dict[str, Any]] = None) -> Optional[str]:
    kodilog(
        f"Preparing Jacktorr URL with magnet={summarize_locator_for_log(magnet)!r}, url={summarize_locator_for_log(url)!r}, has_magnet={bool(magnet)}, has_url={bool(url)}",
        level=LOGDEBUG,
    )
    if not is_jacktorr_addon():
        if Dialog().yesno(
            translation(30253),
            translation(30255),
            yeslabel=translation(90605),
            nolabel=translation(90606),
        ):
            execute_builtin("InstallAddon(plugin.video.jacktorr)")
        else:
            notification(translation(30253))
            return None

    _save_jacktorr_playback_metadata(magnet, data or {})
    poster = (data or {}).get("poster") or ""
    poster_param = f"&poster={quote(poster)}" if poster else ""
    tv_data = (data or {}).get("tv_data")
    season_episode_param = ""
    if isinstance(tv_data, dict):
        season = tv_data.get("season")
        episode = tv_data.get("episode")
        if all(
            not isinstance(value, bool) and str(value).isdigit()
            for value in (season, episode)
        ):
            season_episode_param = f"&season={quote(str(season))}&episode={quote(str(episode))}"
    if magnet:
        _url = f"plugin://plugin.video.jacktorr/play_magnet?magnet={quote(magnet)}{poster_param}{season_episode_param}"
    elif url:
        _url = f"plugin://plugin.video.jacktorr/play_url?url={quote(url)}{poster_param}{season_episode_param}"
    else:
        kodilog("Jacktorr playback failed due to empty magnet and url", level=LOGDEBUG)
        raise TorrentException("No magnet or url found for Jacktorr playback")
    return _url


def _save_jacktorr_playback_metadata(magnet: str, data: Dict[str, Any]) -> None:
    ids = data.get("ids") if isinstance(data.get("ids"), dict) else {}
    ids.get("imdb_id")
    mode = data.get("mode", "")
    tv_data = data.get("tv_data") or {}
    title = data.get("title", "")
    info_hash = data.get("info_hash", "")

    meta = {
        "title": title,
        "mode": mode,
        "ids": ids,
        "tv_data": tv_data,
    }

    hash_candidates = []
    if info_hash:
        hash_candidates.append(info_hash)
    if magnet:
        try:
            from lib.utils.general.utils import get_info_hash_from_magnet

            magnet_hash = get_info_hash_from_magnet(magnet)
            if magnet_hash and magnet_hash not in hash_candidates:
                hash_candidates.append(magnet_hash)
        except Exception as exc:
            kodilog(f"Failed to extract Jacktorr playback metadata hash from magnet: {exc}")

    if not hash_candidates:
        kodilog("Jacktorr playback metadata not saved: no info_hash or magnet hash")
        return

    try:
        from lib.utils.torrent.torrserver_utils import save_torrent_meta

        for hash_candidate in hash_candidates:
            save_torrent_meta(hash_candidate, meta)
    except Exception as exc:
        kodilog(f"Failed to save Jacktorr playback metadata: {exc}")


def get_torrest_url(magnet: str, url: str) -> Optional[str]:
    if not is_torrest_addon():
        if Dialog().yesno(
            translation(30250),
            translation(30256),
            yeslabel=translation(90605),
            nolabel=translation(90606),
        ):
            execute_builtin("InstallAddon(plugin.video.torrest)")
        else:
            notification(translation(30250))
            return None
    if magnet:
        _url = f"plugin://plugin.video.torrest/play_magnet?magnet={quote(magnet)}"
    elif url:
        _url = f"plugin://plugin.video.torrest/play_url?url={quote(url)}"
    else:
        raise TorrentException("No magnet or url found for Torrest playback")
    return _url


class TorrentException(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, error_content: Any = None):
        self.message = message
        self.status_code = status_code
        self.error_content = error_content
        details = f"{self.message}"
        if self.status_code is not None:
            details += f" (Status code: {self.status_code})"
        if self.error_content is not None:
            details += f"\nError content: {self.error_content}"
        super().__init__(details)
        notification(details)


def get_autoscrape_cache_key(id_value: Any, season: Any, episode: Any) -> str:
    """Build autoscrape cache key using as:{id}_{season}_{episode} format."""
    return f"as:{id_value}_{season}_{episode}"


def get_autoscrape_results_cache_key(id_value: Any, season: Any, episode: Any) -> str:
    """Build autoscrape results cache key using as_results:{id}_{season}_{episode} format."""
    return f"as_results:{id_value}_{season}_{episode}"


def cache_autoscrape_result(
    key: str, data: Dict[str, Any], ttl_hours: Optional[int] = None
) -> None:
    """Cache resolved playback data with a TTL (default from autoscrape_ttl setting)."""
    if ttl_hours is None:
        ttl_hours = int(get_setting("autoscrape_ttl", 4) or 4)
    cache.set(key, data, expires=timedelta(hours=ttl_hours))


# Quality pattern -> label mapping, matching PreProcessBuilder.filter_by_quality().
# Keep in priority order: more specific patterns first.
_QUALITY_PATTERNS: List[Tuple[str, str]] = [
    ("2160", "[B][COLOR yellow]4k[/COLOR][/B]"),
    ("1080p", "[B][COLOR blue]1080p[/COLOR][/B]"),
    ("720p", "[B][COLOR orange]720p[/COLOR][/B]"),
    ("480p", "[B][COLOR orange]480p[/COLOR][/B]"),
]
_UNKNOWN_QUALITY_LABEL = "[B][COLOR yellow]N/A[/COLOR][/B]"


def _extract_quality_from_titles(results: List[TorrentStream]) -> None:
    """Mutate each result's quality field by matching patterns in the title."""
    for res in results:
        matched = False
        for pattern, label in _QUALITY_PATTERNS:
            if pattern in res.title:
                res.quality = label
                matched = True
                break
        if not matched:
            res.quality = _UNKNOWN_QUALITY_LABEL


def autoscrape_next_episode(
    item_data: Dict[str, Any],
    next_tv_data: Dict[str, Any],
    force: bool = False,
) -> None:
    """Background thread: search and cache the next episode.

    ``force`` is used after an explicit PlayNext click. It bypasses only the
    proactive pre-scrape setting; it does not enable global autoplay.
    """
    if not force and not get_setting("autoscrape_next_episode", False):
        return

    ids = item_data.get("ids")
    if not ids:
        return

    id_value = ids.get("original_id") or ids.get("imdb_id") or ids.get("tmdb_id")
    if not id_value:
        return

    season = next_tv_data.get("season")
    episode = next_tv_data.get("episode")
    if season is None or episode is None:
        return

    cache_key = get_autoscrape_cache_key(id_value, season, episode)
    results_cache_key = get_autoscrape_results_cache_key(id_value, season, episode)

    try:
        from lib.search import _process_search_results, search_client

        raw_results = search_client(
            query=item_data.get("title", ""),
            ids=ids,
            mode=item_data.get("mode", ""),
            media_type=item_data.get("media_type", ""),
            rescrape=True,
            season=season,
            episode=episode,
            show_dialog=False,
        )

        if not raw_results:
            kodilog("Autoscrape: no results found")
            return

        if not get_setting("auto_play", False):
            results = _process_search_results(
                raw_results,
                item_data.get("mode", ""),
                next_tv_data.get("name", ""),
                episode,
                season,
                "",
                item_data.get("title", ""),
                item_data.get("media_type", ""),
                True,
                suppress_debrid_dialog=True,
                suppress_busy_dialog=force,
            )
            if not results:
                kodilog("Autoscrape: no results after normal source processing")
                return
            cache_autoscrape_result(results_cache_key, results)
            kodilog(
                f"Autoscrape: cached processed results {results_cache_key} "
                f"({len(results)} sources)"
            )
            return

        results = raw_results
        _extract_quality_from_titles(results)
        cache_autoscrape_result(results_cache_key, results)
        kodilog(f"Autoscrape: cached results {results_cache_key} ({len(results)} sources)")

        # Apply auto_play heuristics to select best source
        preferred_quality = str(get_setting("auto_play_quality", "1080p"))
        quality_matches = [r for r in results if preferred_quality.lower() in r.quality.lower()]
        if not quality_matches:
            quality_matches = results

        selected_result = quality_matches[0]

        playback_info = resolve_playback_url(
            data={
                "title": selected_result.title,
                "mode": item_data.get("mode", ""),
                "indexer": selected_result.indexer,
                "type": selected_result.type,
                "debrid_type": selected_result.debridType,
                "ids": ids,
                "info_hash": selected_result.infoHash,
                "url": selected_result.url,
                "tv_data": next_tv_data,
                "poster": item_data.get("poster"),
                "is_torrent": False,
            },
        )

        if not playback_info:
            kodilog("Autoscrape: failed to resolve playback URL")
            return

        # Enrich with metadata needed for direct playback
        playback_info["ids"] = ids
        playback_info["tv_data"] = next_tv_data
        playback_info["mode"] = item_data.get("mode", "")
        playback_info["title"] = selected_result.title

        cache_autoscrape_result(cache_key, playback_info)
        kodilog(f"Autoscrape: cached next episode {cache_key}")
    except Exception as e:
        kodilog(f"Autoscrape: error during background scrape: {e}")
