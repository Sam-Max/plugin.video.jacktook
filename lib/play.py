from urllib.parse import quote
from lib.utils.debrid_utils import get_debrid_direct_url, get_debrid_pack_direct_url
from lib.utils.kodi_utils import (
    get_setting,
    is_elementum_addon,
    is_jacktorr_addon,
    is_torrest_addon,
    notification,
    translation,
)
from lib.utils.utils import (
    Debrids,
    IndexerType,
    Players,
    set_watched_file,
    torrent_clients,
)
from xbmcgui import Dialog
from typing import Any, Dict, Optional


def get_playback_info(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    title: str = data.get("title", "")
    mode: str = data.get("mode", "")
    indexer_type: str = data.get("type", "")
    url: str = data.get("url", "")
    magnet: str = data.get("magnet", "")
    is_torrent: Any = data.get("is_torrent", "")
    ids: Any = data.get("ids", "")
    is_pack: bool = data.get("is_pack", False)

    torrent_enable = get_setting("torrent_enable")
    torrent_client = get_setting("torrent_client")

    if indexer_type in [IndexerType.DIRECT, IndexerType.STREMIO_DEBRID]:
        set_watched_file(title, data, is_direct=(indexer_type == IndexerType.DIRECT))
        return data

    addon_url = None
    _url = None

    if torrent_enable:
        addon_url = get_addon_url_for_client(torrent_client, magnet, url, mode, ids)
        if not addon_url:
            return None
    else:
        if is_torrent:
            addon_url = get_torrent_url(magnet, url, mode, ids)
            if not addon_url:
                return None
        else:
            if is_pack and indexer_type in [Debrids.RD, Debrids.TB]:
                pack_info = data.get("pack_info", {})
                file_id = pack_info.get("file_id", "")
                torrent_id = pack_info.get("torrent_id", "")
                _url = get_debrid_pack_direct_url(file_id, torrent_id, indexer_type)
            else:
                _url = get_debrid_direct_url(indexer_type, data)

    data["url"] = _url if _url else addon_url
    set_watched_file(title, data, is_torrent=is_torrent)
    return data


def get_addon_url_for_client(
    client: str, magnet: str, url: str, mode: str, ids: Any
) -> Optional[str]:
    if client in [Players.TORREST]:
        return get_torrest_url(magnet, url)
    elif client in [Players.ELEMENTUM]:
        return get_elementum_url(magnet, url, mode, ids)
    elif client in [Players.JACKTORR]:
        return get_jacktorr_url(magnet, url)
    return None


def get_torrent_url(magnet: str, url: str, mode: str, ids: Any) -> Optional[str]:
    chosen_client = Dialog().select(translation(30800), torrent_clients)
    if chosen_client < 0:
        return None
    selected_client = torrent_clients[chosen_client]
    return get_addon_url_for_client(selected_client, magnet, url, mode, ids)


def get_elementum_url(magnet: str, url: str, mode: str, ids: Any) -> Optional[str]:
    if not is_elementum_addon():
        notification(translation(30252))
        return None

    if ids:
        tmdb_id = ids["tmdb_id"]
    else:
        tmdb_id = ""

    uri: str = magnet or url or ""
    return f"plugin://plugin.video.elementum/play?uri={quote(uri)}&type={mode}&tmdb={tmdb_id}"


def get_jacktorr_url(magnet: str, url: str) -> Optional[str]:
    if not is_jacktorr_addon():
        notification(translation(30253))
        return None
    if magnet:
        _url = f"plugin://plugin.video.jacktorr/play_magnet?magnet={quote(magnet)}"
    else:
        _url = f"plugin://plugin.video.jacktorr/play_url?url={quote(url)}"
    return _url


def get_torrest_url(magnet: str, url: str) -> Optional[str]:
    if not is_torrest_addon():
        notification(translation(30250))
        return None
    if magnet:
        _url = f"plugin://plugin.video.torrest/play_magnet?magnet={quote(magnet)}"
    else:
        _url = f"plugin://plugin.video.torrest/play_url?url={quote(url)}"
    return _url
