import json
from urllib.parse import quote
from lib.api.jacktook.kodi import kodilog
from lib.debrid import get_debrid_direct_url, get_debrid_pack_direct_url
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
from lib.utils.utils import (
    Players,
    set_video_info,
    set_media_infotag,
    set_watched_file,
    torrent_clients,
)
from xbmcplugin import (
    setResolvedUrl,
)
from xbmcgui import ListItem, Dialog


def play(
    title,
    mode,
    is_torrent=False,
    plugin=None,
    extra_data={},
):
    kodilog("play::play")
    url = extra_data.get("url", "")
    magnet = extra_data.get("magnet", "")
    ids = extra_data.get("ids", [])
    debrid_type = extra_data["debrid_info"].get("debrid_type", "")
    is_debrid_pack = extra_data["debrid_info"].get("is_debrid_pack", False)

    set_watched_file(
        title,
        is_torrent,
        extra_data=extra_data,
    )

    client = get_setting("client_player")
    _url = None
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
            chosen_client = Dialog().select(translation(30800), torrent_clients)
            if chosen_client < 0:
                return
            if torrent_clients[chosen_client] == "Torrest":
                addon_url = get_torrest_url(magnet, url)
            elif torrent_clients[chosen_client] == "Elementum":
                addon_url = get_elementum_url(magnet, mode, ids)
            elif torrent_clients[chosen_client] == "Jacktorr":
                addon_url = get_jacktorr_url(magnet, url)
        else:
            if is_debrid_pack:
                if debrid_type in ["RD", "TB"]:
                    file_id = extra_data["debrid_info"].get("file_id", "")
                    torrent_id = extra_data["debrid_info"].get("torrent_id", "")
                    _url = get_debrid_pack_direct_url(file_id, torrent_id, debrid_type)
                    if _url is None:
                        notification("File not cached")
                        return
                else:
                    _url = url
            else:
                _url = get_debrid_direct_url(
                    extra_data.get("info_hash", ""), debrid_type
                )
                if _url is None:
                    notification("File not cached")
                    return

    if _url:
        list_item = ListItem(title, path=_url)
        make_listing(
            list_item, mode, _url, title, ids, tv_data=extra_data.get("tv_data", {})
        )
        run_player(_url, list_item)
    else:
        list_item = ListItem(title, path=addon_url)
        make_listing(
            list_item,
            mode,
            addon_url,
            title,
            ids,
            tv_data=extra_data.get("tv_data", {}),
        )
        setResolvedUrl(plugin.handle, True, list_item)
        # run_player(addon_url, list_item)


def run_player(url, item):
    player = JacktookPlayer(bookmark_db)
    player.set_constants(url)
    player.run(item)


def make_listing(list_item, mode, url="", title="", ids="", tv_data=""):
    list_item.setPath(url)
    list_item.setContentLookup(False)
    list_item.setLabel(title)

    if tv_data:
        ep_name, episode, season = tv_data.split("(^)")
    else:
        ep_name = episode = season = ""

    if get_kodi_version() >= 20:
        set_media_infotag(
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
        if mode == "movies":
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
