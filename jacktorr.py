#!/usr/bin/env python3
import inspect
import sys
from urllib.parse import parse_qsl, quote
from resources.lib.jackett import clear, get_client, history, search_jackett
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.util import *


routes = {}

def register(f):
    argspec = inspect.getfullargspec(f)
    routes[f.__name__] = {"args": argspec.args, "function": f}
    return f

def main_menu():
    xbmcplugin.setPluginCategory(HANDLE, "Main Menu")

    xbmcplugin.setContent(HANDLE, "videos")
    item = xbmcgui.ListItem(label="Jackett - Search")
    is_folder = True
    xbmcplugin.addDirectoryItem(
        HANDLE, get_url(action="jackett_search"), item, is_folder
    )

    item = xbmcgui.ListItem(label="Jackett - TV Search")
    is_folder = True
    xbmcplugin.addDirectoryItem(
        HANDLE, get_url(action="jackett_tvsearch"), item, is_folder
    )

    item = xbmcgui.ListItem(label="Jackett - Movie Search")
    is_folder = True
    xbmcplugin.addDirectoryItem(
        HANDLE, get_url(action="jackett_moviesearch"), item, is_folder
    )

    item = xbmcgui.ListItem(label="Jackett Nyaa - Search")
    is_folder = True
    xbmcplugin.addDirectoryItem(
        HANDLE, get_url(action="jackett_nyaa_search"), item, is_folder
    )

    item = xbmcgui.ListItem(label="Jackett - History")
    is_folder = True
    xbmcplugin.addDirectoryItem(
        HANDLE, get_url(action="jackett_history"), item, is_folder
    )

    xbmcplugin.endOfDirectory(HANDLE)
    
def _play(magnet, url):
    if magnet == "None":
        magnet = None
    elif url == "None":
        url = None

    torrent_client = get_setting('torrent_clients', default='Torrest')
    if torrent_client == 'Torrest':
        if xbmc.getCondVisibility('System.HasAddon("plugin.video.torrest")'):
            if magnet:
                plugin_url = "plugin://plugin.video.torrest/play_magnet?magnet="
                encoded_url = quote(magnet)
            elif url:
                plugin_url = "plugin://plugin.video.torrest/play_url?url="
                encoded_url = quote(url)
            play_item = xbmcgui.ListItem(path=plugin_url + encoded_url)
        else:
            dialog_ok("jacktorr", 'You need to install the Torrent Engine/Client: Torrest (plugin.video.torrest)')
            return 
    xbmcplugin.setResolvedUrl(HANDLE, True, listitem=play_item)

@register
def play_jackett(title, magnet, url):
    jackett= get_client()
    jackett.set_watched(title=title, magnet=magnet, url=url)
    return _play(magnet, url)

@register
def jackett_search():
    search_jackett()

@register
def jackett_tvsearch():
    search_jackett(method='tv')

@register
def jackett_moviesearch():
    search_jackett(method='movie')

@register
def jackett_nyaa_search():
    search_jackett(tracker='nyaa')

@register
def jackett_history():
    history()

@register
def clear_history():
    clear()

def router(paramstring):
    params = dict(parse_qsl(paramstring))

    if params:
        if routes[params["action"]]:
            route = routes[params["action"]]
            filtered_args = {k: v for (k, v) in params.items() if k in route["args"]}
            route["function"](**filtered_args)
        else:
            raise ValueError("Invalid paramstring: {}!".format(paramstring))
    else:
        main_menu()


if __name__ == "__main__":
    router(sys.argv[2][1:])
