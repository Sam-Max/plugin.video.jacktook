from urllib.parse import quote
from lib.utils.debrid.debrid_utils import (
    get_debrid_direct_url,
    get_debrid_pack_direct_url,
)
from lib.utils.kodi.utils import (
    get_setting,
    is_elementum_addon,
    is_jacktorr_addon,
    is_torrest_addon,
    notification,
    translation,
)
from lib.utils.general.utils import (
    Debrids,
    IndexerType,
    Players,
    torrent_clients,
)
from xbmcgui import Dialog
from typing import Any, Dict, Optional


def resolve_playback_source(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    indexer_type: str = data.get("type", "")
    is_pack: bool = data.get("is_pack", False)

    torrent_enable = get_setting("torrent_enable")
    torrent_client = get_setting("torrent_client")

    if indexer_type in [IndexerType.DIRECT, IndexerType.STREMIO_DEBRID]:
        return data

    addon_url = get_addon_url(data, torrent_enable, torrent_client)
    if addon_url:
        data["url"] = addon_url
    else:
        data["url"] = get_debrid_url(data, indexer_type, is_pack)

    return data


def get_addon_url(
    data: Dict[str, Any], torrent_enable: bool, torrent_client: str
) -> Optional[str]:
    magnet: str = data.get("magnet", "")
    url: str = data.get("url", "")
    mode: str = data.get("mode", "")
    ids: Any = data.get("ids", "")

    if torrent_enable:
        return get_torrent_addon_url_for_client(torrent_client, magnet, url, mode, ids)
    elif data.get("is_torrent", False):
        return get_torrent_addon_url_select(magnet, url, mode, ids)
    return None


def get_torrent_addon_url_for_client(
    client: str, magnet: str, url: str, mode: str, ids: Any
) -> Optional[str]:
    if client in [Players.TORREST]:
        return get_torrest_url(magnet, url)
    elif client in [Players.ELEMENTUM]:
        return get_elementum_url(magnet, url, mode, ids)
    elif client in [Players.JACKTORR]:
        return get_jacktorr_url(magnet, url)
    return None


def get_torrent_addon_url_select(
    magnet: str, url: str, mode: str, ids: Any
) -> Optional[str]:
    chosen_client = Dialog().select(translation(30800), torrent_clients)
    if chosen_client < 0:
        return None
    selected_client = torrent_clients[chosen_client]
    return get_torrent_addon_url_for_client(selected_client, magnet, url, mode, ids)


def get_debrid_url(
    data: Dict[str, Any], indexer_type: str, is_pack: bool
) -> Optional[str]:
    if is_pack and indexer_type in [Debrids.RD, Debrids.TB]:
        pack_info = data.get("pack_info", {})
        file_id = pack_info.get("file_id", "")
        torrent_id = pack_info.get("torrent_id", "")
        return get_debrid_pack_direct_url(file_id, torrent_id, indexer_type)
    return get_debrid_direct_url(indexer_type, data)


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
