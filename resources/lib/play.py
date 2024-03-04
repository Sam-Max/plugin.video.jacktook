from urllib.parse import quote
from resources.lib.player import JacktookPlayer
from resources.lib.utils.kodi import (
    get_setting,
    is_elementum_addon,
    is_torrest_addon,
    notify,
    translation,
)
from resources.lib.utils.utils import set_watched_file
from xbmcplugin import (
    setResolvedUrl,
)
from xbmcgui import ListItem, Dialog


torrent_clients = ["Torrest", "Elementum"]


def play(
    url, magnet, id, title, plugin, debrid_type="", is_debrid=False, is_torrent=False
):
    set_watched_file(title, debrid_type, id, magnet, url)
    if not magnet and not url:
        notify(translation(30251))
        return

    torr_client = get_setting("torrent_client")
    if torr_client == "Torrest":
        _url = get_torrest_url(magnet, url)
    elif torr_client == "Elementum":
        _url = get_elementum_url(magnet)
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
                _url = get_elementum_url(magnet)

    if _url:
        list_item = ListItem(title, path=_url)
        setResolvedUrl(plugin.handle, True, list_item)

        if is_debrid:
            player = JacktookPlayer()
            list_item = player.make_listing(list_item, _url, title, id)
            player.run(list_item)


def get_elementum_url(magnet):
    if not is_elementum_addon():
        notify(translation(30252))
        return
    if magnet:
        return f"plugin://plugin.video.elementum/play?uri={quote(magnet)}"
    else:
        notify("Not a playable url.")


def get_torrest_url(magnet, url):
    if not is_torrest_addon():
        notify(translation(30250))
        return
    if magnet:
        _url = f"plugin://plugin.video.torrest/play_magnet?magnet={quote(magnet)}"
    else:
        _url = f"plugin://plugin.video.torrest/play_url?url={quote(url)}"
    return _url
