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
    Players,
    set_watched_file,
    torrent_clients,
)
from xbmcgui import Dialog


def get_playback_info(
    title,
    mode,
    is_torrent=False,
    extra_data={},
):
    url = extra_data.get("url", "")
    magnet = extra_data.get("magnet", "")
    ids = extra_data.get("ids", [])
    debrid_type = extra_data["debrid_info"].get("debrid_type", "")
    is_debrid_pack = extra_data["debrid_info"].get("is_debrid_pack", False)
    extra_data["mode"] = mode

    set_watched_file(
        title,
        is_torrent,
        extra_data=extra_data,
    )

    client = get_setting("client_player")
    _url = None
    addon_url = None
    if client == Players.JACKGRAM:
        _url = url
    elif client == Players.TORREST:
        addon_url = get_torrest_url(magnet, url)
    elif client == Players.ELEMENTUM:
        addon_url = get_elementum_url(magnet, mode, ids)
    elif client == Players.JACKTORR:
        addon_url = get_jacktorr_url(magnet, url)
    elif client == Players.DEBRID:
        if is_torrent:
            addon_url = get_torrent_url()
        else:
            if is_debrid_pack:
                if debrid_type in ["RD", "TB"]:
                    file_id = extra_data["debrid_info"].get("file_id", "")
                    torrent_id = extra_data["debrid_info"].get("torrent_id", "")
                    _url = get_debrid_pack_direct_url(file_id, torrent_id, debrid_type)
                    if _url is None:
                        notification("File not cached")
                        return None, None
                else:
                    _url = url
            else:
                _url = get_debrid_direct_url(
                    extra_data.get("info_hash", ""), debrid_type
                )
                if not _url:
                    notification("File not cached")
                    return None, None

    return (_url, extra_data) if _url else (addon_url, extra_data)


def get_torrent_url(magnet, url, mode, ids):
    chosen_client = Dialog().select(translation(30800), torrent_clients)
    if chosen_client < 0:
        return None
    if torrent_clients[chosen_client] == "Torrest":
        addon_url = get_torrest_url(magnet, url)
    elif torrent_clients[chosen_client] == "Elementum":
        addon_url = get_elementum_url(magnet, mode, ids)
    elif torrent_clients[chosen_client] == "Jacktorr":
        addon_url = get_jacktorr_url(magnet, url)
    return addon_url


def get_elementum_url(magnet, mode, ids):
    if not is_elementum_addon():
        notification(translation(30252))
        return
    if ids:
        tmdb_id, _, _ = ids.split(", ")
    else:
        tmdb_id = ""
    return f"plugin://plugin.video.elementum/play?uri={quote(magnet)}&type={mode}&tmdb={tmdb_id}"


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
