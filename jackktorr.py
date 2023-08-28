#!/usr/bin/env python3
import inspect
import logging
import sys
from urllib.parse import parse_qsl, quote
import resolveurl
from resources.lib.jackett import Jackett
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.database import Database
from resources.lib.util import *


routes = {}


def register(f):
    argspec = inspect.getfullargspec(f)
    routes[f.__name__] = {"args": argspec.args, "function": f}
    return f

db = Database()
jackett = Jackett(db)


def main_menu():
    xbmcplugin.setPluginCategory(HANDLE, "Main Menu")
    xbmcplugin.setContent(HANDLE, "videos")

    list_item = xbmcgui.ListItem(label="Nyaa Torrents - Recent")
    is_folder = True
    xbmcplugin.addDirectoryItem(
        HANDLE, get_url(action="nyaa_recent"), list_item, is_folder
    )

    list_item = xbmcgui.ListItem(label="Nyaa Torrents - Search")
    is_folder = True
    xbmcplugin.addDirectoryItem(
        HANDLE, get_url(action="nyaa_search"), list_item, is_folder
    )

    list_item = xbmcgui.ListItem(label="Nyaa Torrents - History")
    is_folder = True
    xbmcplugin.addDirectoryItem(
        HANDLE, get_url(action="nyaa_history"), list_item, is_folder
    )

    list_item = xbmcgui.ListItem(label="Jackett - Search")
    is_folder = True
    xbmcplugin.addDirectoryItem(
        HANDLE, get_url(action="jackett_search"), list_item, is_folder
    )

    xbmcplugin.endOfDirectory(HANDLE)


@register
def settings():
    xbmcplugin.setPluginCategory(HANDLE, "Settings")
    xbmcplugin.setContent(HANDLE, "videos")

    list_item = xbmcgui.ListItem(label="ResolveURL Settings")
    is_folder = False
    xbmcplugin.addDirectoryItem(
        HANDLE, get_url(action="resolveurl_settings"), list_item, is_folder
    )

def _play(url=None, magnet=None):

    torrent_client = get_setting('torrent_clients', default='Debrid')
    if torrent_client == 'Torrest':
        if xbmc.getCondVisibility('System.HasAddon("plugin.video.torrest")'):
            if magnet:
                plugin_url = "plugin://plugin.video.torrest/play_magnet?magnet="
                encoded_url = quote(magnet)
                logging.error("_play")
                logging.debug(plugin_url + encoded_url)
                logging.error(plugin_url + encoded_url)
            else:
                plugin_url = "plugin://plugin.video.torrest/play_url?url="
                encoded_url = quote(magnet)
                logging.error("_play")
                logging.debug(plugin_url + encoded_url)
                logging.error(plugin_url + encoded_url)
            play_item = xbmcgui.ListItem(path=plugin_url + encoded_url)
        else:
            dialog_ok("Haru", 'You need to install the Torrent Engine/Client: Torrest (plugin.video.torrest)')
            return 
    elif torrent_client == 'Debrid':
        if magnet:
            if not selected_file:
                resolved_url = resolveurl.HostedMediaFile(url=magnet).resolve()
            else:
                all_urls = resolveurl.resolve(magnet, return_all=True)
                selected_url = next(filter(lambda x: selected_file in x["name"], all_urls))["link"]
                resolved_url = resolveurl.resolve(selected_url)
            play_item = xbmcgui.ListItem(path=resolved_url)
    xbmcplugin.setResolvedUrl(HANDLE, True, listitem=play_item)

@register
def play_nyaa(name, selected_file, nyaa_url, magnet):
    nyaa.set_watched(torrent_name=name, file_name=selected_file, nyaa_url=nyaa_url)
    return _play(is_nyaa=True, selected_file=selected_file, magnet=magnet)

@register
def play_jackett(magnet, url):
    # jackett.set_watched(torrent_name=name, file_name=selected_file, url=magnet)
    return _play(magnet=magnet, url=url)

@register
def resolveurl_settings():
    resolveurl.display_settings()
    
@register
def nyaa_search():
    nyaa.search()

@register
def jackett_search():
    jackett.search()

@register
def nyaa_recent():
    nyaa.recent()


@register
def nyaa_history():
    nyaa.history()


@register
def toggle_watched_nyaa(torrent_name, file_name, nyaa_url, watched):
    nyaa.set_watched(torrent_name, file_name, nyaa_url, watched)
    xbmc.executebuiltin("Container.Refresh")


@register
def clear_history_nyaa():
    dialog = xbmcgui.Dialog()
    confirmed = dialog.yesno(
        "Clear History",
        "Do you want to clear this history list?\n\nWatched statuses will be preserved.",
    )
    if confirmed:
        db.database["nt:history"] = {}
        db.commit()
        xbmc.executebuiltin("Container.Refresh")

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
