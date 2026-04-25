from datetime import timedelta
from typing import Any, Dict, Optional
from urllib.parse import quote

from xbmc import LOGDEBUG
from xbmcgui import Dialog

from lib.db.cached import cache
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


def get_torrent_url(data: Dict[str, Any]) -> Optional[str]:
    magnet: str = data.get("magnet", "")
    url: str = data.get("url", "")
    mode: str = data.get("mode", "")
    ids: Any = data.get("ids", "")
    info_hash: str = data.get("info_hash", "")

    if not magnet and info_hash:
        from lib.utils.general.utils import info_hash_to_magnet

        magnet = info_hash_to_magnet(info_hash)

    kodilog(
        "Torrent playback resolution: indexer={!r}, client={!r}, magnet={!r}, url={!r}, infohash={!r}, is_torrent={}".format(
            data.get("indexer", ""),
            str(get_setting("torrent_client")),
            summarize_locator_for_log(magnet),
            summarize_locator_for_log(url),
            str(info_hash).lower()[:12],
            data.get("is_torrent", False),
        )
    )

    if get_setting("torrent_enable"):
        return get_torrent_url_for_client(magnet, url, mode, ids)

    if data.get("is_torrent"):
        selected_client = get_torrent_client_selection(magnet, url, mode, ids)
        if selected_client:
            return get_torrent_url_for_client(magnet, url, mode, ids, selected_client)
        else:
            raise TorrentException("No torrent client selected")
    return None


def get_torrent_url_for_client(
    magnet: str, url: str, mode: str, ids: Any, client: str = ""
) -> Optional[str]:
    torrent_client = client or str(get_setting("torrent_client"))
    if torrent_client in [Players.TORREST]:
        return get_torrest_url(magnet, url)
    elif torrent_client in [Players.ELEMENTUM]:
        return get_elementum_url(magnet, url, mode, ids)
    elif torrent_client in [Players.JACKTORR]:
        return get_jacktorr_url(magnet, url)
    else:
        raise TorrentException(f"Unknown torrent client selected: {torrent_client}")


def get_torrent_client_selection(
    magnet: str, url: str, mode: str, ids: Any
) -> Optional[str]:
    chosen_client = Dialog().select(translation(90341), torrent_clients)
    if chosen_client < 0:
        return None
    return torrent_clients[chosen_client]


def get_debrid_url(
    data: Dict[str, Any], debrid_type: str, is_pack: bool
) -> Optional[Dict[str, Any]]:
    if is_pack and debrid_type in [DebridType.RD, DebridType.TB, DebridType.AD]:
        return get_debrid_pack_direct_url(debrid_type, data)
    else:
        return get_debrid_direct_url(debrid_type, data)


def get_elementum_url(magnet: str, url: str, mode: str, ids: Any) -> Optional[str]:
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

    if magnet or url:
        return f"plugin://plugin.video.elementum/play?uri={quote(magnet or url)}&type={mode}&tmdb={tmdb_id}"
    else:
        raise TorrentException("No magnet or url found for Elementum playback")


def get_jacktorr_url(magnet: str, url: str) -> Optional[str]:
    kodilog(
        "Preparing Jacktorr URL with magnet={!r}, url={!r}, has_magnet={}, has_url={}".format(
            summarize_locator_for_log(magnet),
            summarize_locator_for_log(url),
            bool(magnet),
            bool(url),
        ),
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
    if magnet:
        _url = f"plugin://plugin.video.jacktorr/play_magnet?magnet={quote(magnet)}"
    elif url:
        _url = f"plugin://plugin.video.jacktorr/play_url?url={quote(url)}"
    else:
        kodilog("Jacktorr playback failed due to empty magnet and url", level=LOGDEBUG)
        raise TorrentException("No magnet or url found for Jacktorr playback")
    return _url


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
    def __init__(
        self, message: str, status_code: Optional[int] = None, error_content: Any = None
    ):
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


def cache_autoscrape_result(key: str, data: Dict[str, Any], ttl_hours: Optional[int] = None) -> None:
    """Cache resolved playback data with a TTL (default from autoscrape_ttl setting)."""
    if ttl_hours is None:
        ttl_hours = int(get_setting("autoscrape_ttl", 4) or 4)
    cache.set(key, data, expires=timedelta(hours=ttl_hours))


def autoscrape_next_episode(item_data: Dict[str, Any], next_tv_data: Dict[str, Any]) -> None:
    """Background thread: search, select, resolve, and cache next episode."""
    if not get_setting("autoscrape_next_episode", False):
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

    try:
        from lib.search import search_client

        results = search_client(
            query=item_data.get("title", ""),
            ids=ids,
            mode=item_data.get("mode", ""),
            media_type=item_data.get("media_type", ""),
            rescrape=True,
            season=season,
            episode=episode,
            show_dialog=False,
        )

        if not results:
            kodilog("Autoscrape: no results found")
            return

        # Apply auto_play heuristics to select best source
        preferred_quality = str(get_setting("auto_play_quality", "1080p"))
        quality_matches = [
            r for r in results if preferred_quality.lower() in r.quality.lower()
        ]
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
