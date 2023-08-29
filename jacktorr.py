#!/usr/bin/env python3
import inspect
import os
import sys
from urllib.parse import parse_qsl, quote
from resources.lib.jackett import clear, get_client, history, search_jackett
import xbmc
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory, setResolvedUrl, setPluginCategory
from resources.lib.util import *


routes = {}

def register(f):
    argspec = inspect.getfullargspec(f)
    routes[f.__name__] = {"args": argspec.args, "function": f}
    return f

def main_menu():
    setPluginCategory(HANDLE, "Main Menu")
    
    item = ListItem(label="Jackett - Search")
    item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "search.png")})
    addDirectoryItem(HANDLE, get_url(action="jackett_search"), item, isFolder= True)

    item = ListItem(label="Jackett - TV Search")
    item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "tv.png")})
    addDirectoryItem(HANDLE, get_url(action="jackett_tvsearch"), item,  isFolder= True)

    item = ListItem(label="Jackett - Movie Search")
    item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "movies.png")})
    addDirectoryItem(HANDLE, get_url(action="jackett_moviesearch"), item,  isFolder= True)

    item = ListItem(label="Jackett Nyaa - Search")
    item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "search.png")})
    addDirectoryItem(HANDLE, get_url(action="jackett_nyaa_search"), item, isFolder= True)

    item = ListItem(label="Jackett - History")
    item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "history.png")})
    addDirectoryItem(HANDLE, get_url(action="jackett_history"), item,  isFolder= True)
   
    endOfDirectory(HANDLE)
    
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
    setResolvedUrl(HANDLE, True, listitem=play_item)

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
