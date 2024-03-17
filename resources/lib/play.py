import json
from urllib.parse import quote
from resources.lib.player import JacktookPlayer
from resources.lib.utils.kodi import (
    get_setting,
    is_elementum_addon,
    is_torrest_addon,
    log,
    notify,
    set_property,
    translation,
)
from resources.lib.utils.utils import set_watched_file
from xbmcplugin import (
    setResolvedUrl,
)
from xbmcgui import ListItem, Dialog


torrent_clients = ["Torrest", "Elementum"]


def play(
    url,
    magnet,
    ids,
    tvdata,
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
        tvdata,
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

    if _url:
        list_item = ListItem(title, path=_url)
        make_listing(list_item, mode, _url, title, ids, tvdata)
        setResolvedUrl(plugin.handle, True, list_item)

        if is_debrid:
            player = JacktookPlayer()
            player.set_constants(_url)
            player.run(list_item)


def make_listing(listitem, mode, url, title, ids, tvdata):
    listitem.setPath(url)
    listitem.setContentLookup(False)
    listitem.setLabel(title)
    info_tag = listitem.getVideoInfoTag()
    if mode in ["movie", "multi"]:
        info_tag.setMediaType("movie")
        info_tag.setTitle(title)
        info_tag.setOriginalTitle(title)
    else:
        info_tag.setMediaType("episode")
        info_tag.setTvShowTitle(title)
        info_tag.setFilenameAndPath(url)
        if tvdata:
            ep_name, episode, season = tvdata.split(", ")
            info_tag.setTitle(ep_name)
            info_tag.setSeason(int(season)),
            info_tag.setEpisode(int(episode))
    if ids:
        tmdb_id, tvdb_id, imdb_id = ids.split(", ")
        info_tag.setIMDBNumber(imdb_id)
        info_tag.setUniqueIDs({"imdb": imdb_id, "tmdb": tmdb_id, "tvdb": tvdb_id})
        set_windows_property(mode, tmdb_id, imdb_id, tvdb_id)


def set_windows_property(mode, tmdb_id, imdb_id, tvdb_id):
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
   

def get_torrest_url(magnet, url):
    if not is_torrest_addon():
        notify(translation(30250))
        return
    if magnet:
        _url = f"plugin://plugin.video.torrest/play_magnet?magnet={quote(magnet)}"
    else:
        _url = f"plugin://plugin.video.torrest/play_url?url={quote(url)}"
    return _url
