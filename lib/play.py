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


def get_playback_info(data):
    title = data.get("title", "")
    mode = data.get("mode", "")
    type = data.get("type", "")
    url = data.get("url", "")
    magnet = data.get("magnet", "")
    is_torrent = data.get("is_torrent", "")
    ids = data.get("ids", "")
    is_pack = data.get("is_pack", False)

    torrent_enable = get_setting("torrent_enable")
    torrent_client = get_setting("torrent_client")
    _url = None
    addon_url = None

    if type == IndexerType.DIRECT:
        set_watched_file(title, data, is_direct=True)
        return data

    if type == IndexerType.STREMIO_DEBRID:
        set_watched_file(title, data)
        return data

    if torrent_enable:
        if torrent_client == Players.TORREST:
            addon_url = get_torrest_url(magnet, url)
        elif torrent_client == Players.ELEMENTUM:
            addon_url = get_elementum_url(magnet, url, mode, ids)
        elif torrent_client == Players.JACKTORR:
            addon_url = get_jacktorr_url(magnet, url)
        if not addon_url:
            return
    else:
        if is_torrent:
            addon_url = get_torrent_url()
            if not addon_url:
                return
        else:
            if is_pack:
                if type in [Debrids.RD, Debrids.TB]:
                    pack_info = data.get("pack_info", {})
                    file_id = pack_info.get("file_id", "")
                    torrent_id = pack_info.get("torrent_id", "")
                    _url = get_debrid_pack_direct_url(file_id, torrent_id, type)
                else:
                    _url = url
            else:
                _url = get_debrid_direct_url(type, data)
                
    if _url:
        data["url"] = _url
    else:
        data["url"] = addon_url

    set_watched_file(title, data, is_torrent=is_torrent)

    return data


def get_torrent_url(magnet, url, mode, ids):
    chosen_client = Dialog().select(translation(30800), torrent_clients)
    if chosen_client < 0:
        return None
    if torrent_clients[chosen_client] == "Torrest":
        addon_url = get_torrest_url(magnet, url)
    elif torrent_clients[chosen_client] == "Elementum":
        addon_url = get_elementum_url(magnet, url, mode, ids)
    elif torrent_clients[chosen_client] == "Jacktorr":
        addon_url = get_jacktorr_url(magnet, url)
    return addon_url


def get_elementum_url(magnet, url, mode, ids):
    if not is_elementum_addon():
        notification(translation(30252))
        return
    
    if ids:
        tmdb_id = ids["tmdb_id"]
    else:
        tmdb_id = ""

    uri = magnet or url or ""
    return f"plugin://plugin.video.elementum/play?uri={quote(uri)}&type={mode}&tmdb={tmdb_id}"


def get_jacktorr_url(magnet, url):
    if not is_jacktorr_addon():
        notification(translation(30253))
        return
    if magnet:
        _url = f"plugin://plugin.video.jacktorr/play_magnet?magnet={quote(magnet)}"
    else:
        _url = f"plugin://plugin.video.jacktorr/play_url?url={quote(url)}"
    return _url


def get_torrest_url(magnet, url):
    if not is_torrest_addon():
        notification(translation(30250))
        return
    if magnet:
        _url = f"plugin://plugin.video.torrest/play_magnet?magnet={quote(magnet)}"
    else:
        _url = f"plugin://plugin.video.torrest/play_url?url={quote(url)}"
    return _url
