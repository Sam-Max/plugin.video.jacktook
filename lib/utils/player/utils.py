from urllib.parse import quote
from lib.jacktook.utils import kodilog
from lib.utils.debrid.debrid_utils import (
    get_debrid_direct_url,
    get_debrid_pack_direct_url,
    is_supported_debrid_type,
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
from lib.utils.general.utils import (
    DebridType,
    IndexerType,
    Players,
    torrent_clients,
)
from xbmcgui import Dialog
from xbmc import LOGDEBUG
from typing import Any, Dict, Optional


def resolve_playback_url(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    indexer_type: str = data.get("type", "")
    debrid_type: str = data.get("debrid_type", "")
    is_pack: bool = data.get("is_pack", False)

    if indexer_type in [IndexerType.DIRECT, IndexerType.STREMIO_DEBRID]:
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


def get_torrent_url(data: Dict[str, Any]) -> Optional[str]:
    magnet: str = data.get("magnet", "")
    url: str = data.get("url", "")
    mode: str = data.get("mode", "")
    ids: Any = data.get("ids", "")
    info_hash: str = data.get("info_hash", "")

    if not magnet and info_hash:
        from lib.utils.general.utils import info_hash_to_magnet

        magnet = info_hash_to_magnet(info_hash)

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
    chosen_client = Dialog().select(translation(30800), torrent_clients)
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
            yeslabel="Ok",
            nolabel="No",
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
        f"Preparing Jacktorr URL with magnet: {magnet} and url: {url}", level=LOGDEBUG
    )
    if not is_jacktorr_addon():
        if Dialog().yesno(
            translation(30253),
            translation(30255),
            yeslabel="Ok",
            nolabel="No",
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
        raise TorrentException("No magnet or url found for Jacktorr playback")
    return _url


def get_torrest_url(magnet: str, url: str) -> Optional[str]:
    if not is_torrest_addon():
        if Dialog().yesno(
            translation(30250),
            translation(30256),
            yeslabel="Ok",
            nolabel="No",
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


def precache_next_episodes(item_data):
    kodilog("Precaching next episodes...")

    from lib.search import search_client
    from lib.clients.tmdb.utils.utils import tmdb_get

    if not get_setting("precaching_enabled", False):
        return

    if item_data.get("mode") != "tv":
        return

    ids = item_data.get("ids")
    if not ids:
        return

    tmdb_id = ids.get("tmdb_id")
    if not tmdb_id:
        return

    details = tmdb_get("tv_details", tmdb_id)
    tv_data = item_data.get("tv_data", {})
    season = tv_data.get("season")
    episode = tv_data.get("episode")

    if season is None or episode is None:
        kodilog("Invalid season or episode data")
        return

    season_details = tmdb_get("season_details", {"id": tmdb_id, "season": season})
    if not season_details or not hasattr(season_details, "episodes"):
        kodilog("Invalid season details")
        return

    episodes_to_cache = []
    for e in getattr(season_details, "episodes"):
        episode_number = getattr(e, "episode_number", 0)
        if episode_number > int(episode):
            episodes_to_cache.append(e)

    kodilog(f"Found {len(episodes_to_cache)} episodes to cache")

    if not episodes_to_cache:
        return

    count = int(get_setting("precaching_episode_count", 1))
    for i in range(min(count, len(episodes_to_cache))):
        next_episode = episodes_to_cache[i]
        episode_number = getattr(next_episode, "episode_number", 0)
        query = getattr(details, "name", "")

        search_client(
            query=query,
            ids=ids,
            mode=item_data["mode"],
            media_type=item_data.get("media_type", ""),
            rescrape=True,
            season=season,
            episode=episode_number,
            show_dialog=False,
        )

        kodilog(f"Precaching episode {season}x{episode_number}")


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
