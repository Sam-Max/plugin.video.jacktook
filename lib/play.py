import json
from urllib.parse import quote
from lib.api.jacktook.kodi import kodilog
from lib.debrid import get_debrid_direct_url
from lib.player import JacktookPlayer
from lib.db.bookmark_db import bookmark_db
from lib.utils.kodi_utils import (
    get_kodi_version,
    get_setting,
    is_elementum_addon,
    is_jacktorr_addon,
    is_torrest_addon,
    notification,
    set_property,
    translation,
)
from lib.utils.general_utils import (
    Players,
    set_video_info,
    set_video_infotag,
    set_watched_file,
    torrent_clients,
)
from xbmcplugin import (
    setResolvedUrl,
)
from xbmcgui import ListItem, Dialog

def play(
    url,
    ids,
    tv_data,
    title,
    plugin,
    magnet="",
    info_hash="",
    mode="",
    debrid_type="",
    is_torrent=False,
    is_plex=False,
    is_debrid_pack=False,
):
    if not is_torrent and not (is_plex or is_debrid_pack):
        url = get_debrid_direct_url(info_hash, debrid_type)

    set_watched_file(
        title,
        ids,
        tv_data,
        magnet,
        url,
        info_hash,
        debrid_type,
        is_torrent,
        is_debrid_pack,
    )

    if not magnet and not url:
        notification(translation(30251))
        return

    client = get_setting("client_player")

    if client == Players.PLEX:
        _url = url
    if client == Players.TORREST:
        _url = get_torrest_url(magnet, url)
    elif client == Players.ELEMENTUM:
        _url = get_elementum_url(magnet, mode, ids)
    elif client == Players.JACKTORR:
        _url = get_jacktorr_url(magnet, url)
    elif client == Players.DEBRID:
        if is_torrent:
            chosen_client = Dialog().select(translation(30800), torrent_clients)
            if chosen_client < 0:
                return
            if torrent_clients[chosen_client] == "Torrest":
                _url = get_torrest_url(magnet, url)
            elif torrent_clients[chosen_client] == "Elementum":
                _url = get_elementum_url(magnet, mode, ids)
            elif torrent_clients[chosen_client] == "Jacktorr":
                _url = get_jacktorr_url(magnet, url)
        else:
            _url = url

    if _url:
        list_item = ListItem(title, path=_url)
        make_listing(list_item, mode, _url, title, ids, tv_data)
        setResolvedUrl(plugin.handle, True, list_item)

        if not is_torrent:
            player = JacktookPlayer(bookmark_db)
            player.set_constants(_url, list_item)
            player.run(list_item)


def make_listing(list_item, mode, url="", title="", ids="", tv_data=""):
    list_item.setPath(url)
    list_item.setContentLookup(False)
    list_item.setLabel(title)

    if tv_data:
        ep_name, episode, season = tv_data.split("(^)")
    else:
        ep_name = episode = season = ""

    if get_kodi_version() >= 20:
        set_video_infotag(
            list_item,
            mode,
            title,
            season_number=season,
            episode=episode,
            ep_name=ep_name,
            ids=ids,
        )
    else:
        set_video_info(
            list_item,
            mode,
            title,
            season_number=season,
            episode=episode,
            ep_name=ep_name,
            ids=ids,
        )

    set_windows_property(mode, ids)


def set_windows_property(mode, ids):
    if ids:
        tmdb_id, tvdb_id, imdb_id = ids.split(", ")
        if mode == "movie":
            ids = {
                "tmdb": tmdb_id,
                "imdb": imdb_id,
            }
        else:
            ids = {
                "tvdb": tvdb_id,
            }
        set_property(
            "script.trakt.ids",
            json.dumps(ids),
        )


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
