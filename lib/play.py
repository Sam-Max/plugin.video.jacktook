import json
from urllib.parse import quote
from lib.player import JacktookPlayer
from lib.utils.kodi import (
    get_kodi_version,
    get_setting,
    is_elementum_addon,
    is_jacktorr_addon,
    is_torrest_addon,
    notify,
    set_property,
    translation,
)
from lib.utils.utils import (
    set_video_info,
    set_video_infotag,
    set_watched_file,
)
from xbmcplugin import (
    setResolvedUrl,
)
from xbmcgui import ListItem, Dialog


torrent_clients = ["Jacktorr", "Torrest", "Elementum"]


def play(
    url,
    magnet,
    ids,
    tv_data,
    title,
    plugin,
    debrid_type="",
    mode="",
    is_debrid=False,
    is_torrent=False,
):
    set_watched_file(
        title,
        ids,
        tv_data,
        magnet,
        url,
        debrid_type,
        is_debrid,
        is_torrent,
    )

    if not magnet and not url:
        notify(translation(30251))
        return

    torr_client = get_setting("torrent_client")
    if torr_client == "Torrest":
        _url = get_torrest_url(magnet, url)
    elif torr_client == "Elementum":
        _url = get_elementum_url(magnet, mode, ids)
    elif torr_client == "Jacktorr":
        _url = get_jacktorr_url(magnet, url)
    elif torr_client == "Debrid":
        _url = url
    elif torr_client == "All":
        if is_debrid:
            _url = url
        elif is_torrent:
            chosen_client = Dialog().select(translation(30800), torrent_clients)
            if chosen_client < 0:
                return
            if torrent_clients[chosen_client] == "Torrest":
                _url = get_torrest_url(magnet, url)
            elif torrent_clients[chosen_client] == "Elementum":
                _url = get_elementum_url(magnet, mode, ids)
            elif torrent_clients[chosen_client] == "Jacktorr":
                _url = get_jacktorr_url(magnet, url)

    if _url:
        list_item = ListItem(title, path=_url)
        make_listing(list_item, mode, _url, title, ids, tv_data)
        setResolvedUrl(plugin.handle, True, list_item)

        if is_debrid:
            player = JacktookPlayer()
            player.set_constants(_url)
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
        notify(translation(30252))
        return
    if ids:
        tmdb_id, _, _ = ids.split(", ")
    else:
        tmdb_id = ""
    return f"plugin://plugin.video.elementum/play?uri={quote(magnet)}&type={mode}&tmdb={tmdb_id}"


def get_jacktorr_url(magnet, url):
    if not is_jacktorr_addon():
        notify(translation(30253))
        return
    if magnet:
        _url = f"plugin://plugin.video.jacktorr/play_magnet?magnet={quote(magnet)}"
    else:
        _url = f"plugin://plugin.video.jacktorr/play_url?url={quote(url)}"
    return _url


def get_torrest_url(magnet, url):
    if not is_torrest_addon():
        notify(translation(30250))
        return
    if magnet:
        _url = f"plugin://plugin.video.torrest/play_magnet?magnet={quote(magnet)}"
    else:
        _url = f"plugin://plugin.video.torrest/play_url?url={quote(url)}"
    return _url
