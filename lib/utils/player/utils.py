from urllib.parse import quote
from lib.utils.debrid.debrid_utils import (
    get_debrid_direct_url,
    get_debrid_pack_direct_url,
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
from typing import Any, Dict, Optional


def resolve_playback_url(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    indexer_type: str = data.get("type", "")
    debrid_type: str = data.get("debrid_type", "")
    is_pack: bool = data.get("is_pack", False)

    torrent_enable = bool(get_setting("torrent_enable"))
    torrent_client = str(get_setting("torrent_client"))

    if indexer_type in [IndexerType.DIRECT, IndexerType.STREMIO_DEBRID]:
        return data

    addon_url = get_torrent_url(data, torrent_enable, torrent_client)
    if addon_url:
        data["url"] = addon_url
        return data

    debrid_url = get_debrid_url(data, debrid_type, is_pack)
    if debrid_url:
        return data

    return None


def get_torrent_url(
    data: Dict[str, Any], torrent_enable: bool, torrent_client: str
) -> Optional[str]:
    magnet: str = data.get("magnet", "")
    url: str = data.get("url", "")
    mode: str = data.get("mode", "")
    ids: Any = data.get("ids", "")

    if torrent_enable:
        return get_torrent_url_for_client(torrent_client, magnet, url, mode, ids)
    else:
        if data.get("is_torrent"):
            selected_client = get_torrent_client_selection(magnet, url, mode, ids)
            if selected_client:
                return get_torrent_url_for_client(
                    selected_client, magnet, url, mode, ids
                )
            else:
                raise TorrentException("No torrent client selected")
    return None


def get_torrent_client_selection(
    magnet: str, url: str, mode: str, ids: Any
) -> Optional[str]:
    chosen_client = Dialog().select(translation(30800), torrent_clients)
    if chosen_client < 0:
        return None
    return torrent_clients[chosen_client]


def get_torrent_url_for_client(
    client: str, magnet: str, url: str, mode: str, ids: Any
) -> Optional[str]:
    if client in [Players.TORREST]:
        return get_torrest_url(magnet, url)
    elif client in [Players.ELEMENTUM]:
        return get_elementum_url(magnet, url, mode, ids)
    elif client in [Players.JACKTORR]:
        return get_jacktorr_url(magnet, url)
    else:
        raise TorrentException(f"Unknown torrent client selected: {client}")


def get_debrid_url(
    data: Dict[str, Any], debrid_type: str, is_pack: bool
) -> Optional[Dict[str, Any]]:
    if is_pack and debrid_type in [DebridType.RD, DebridType.TB]:
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

    tmdb_id = ids["tmdb_id"] if ids else ""

    if magnet or url:
        return f"plugin://plugin.video.elementum/play?uri={quote(magnet or url)}&type={mode}&tmdb={tmdb_id}"
    else:
        raise TorrentException("No magnet or url found for Elementum playback")


def get_jacktorr_url(magnet: str, url: str) -> Optional[str]:
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
