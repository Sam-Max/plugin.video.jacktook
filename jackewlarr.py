#!/usr/bin/env python3
import inspect
import os
import sys
from urllib.parse import parse_qsl
from resources.lib.utils import clear, history, play, search_api
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory, setPluginCategory
from resources.lib.kodi import *
from resources.lib.tmdb import search_tmdb, tv_details


routes = {}


def register(f):
    argspec = inspect.getfullargspec(f)
    routes[f.__name__] = {"args": argspec.args, "function": f}
    return f

def main_menu():
    setPluginCategory(HANDLE, "Main Menu")

    item = ListItem(label="Search")
    item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "search.png")})
    addDirectoryItem(HANDLE, get_url(action="tmdb", mode='multi'), item, isFolder= True)

    item = ListItem(label="Search TV")
    item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "tv.png")})
    addDirectoryItem(HANDLE, get_url(action="tmdb", mode='tv'), item, isFolder= True)

    item = ListItem(label="Search Movies")
    item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "movies.png")})
    addDirectoryItem(HANDLE, get_url(action="tmdb", mode='movie'), item, isFolder= True)

    item = ListItem(label="Search by Genre")
    item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "search.png")})
    addDirectoryItem(HANDLE, get_url(action="genre_menu"), item, isFolder= True)

    item = ListItem(label="Direct - Search")
    item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "search.png")})
    addDirectoryItem(HANDLE, get_url(action="search"), item, isFolder= True)

    item = ListItem(label="Direct - TV Search")
    item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "tv.png")})
    addDirectoryItem(HANDLE, get_url(action="search", method='tv'), item,  isFolder= True)

    item = ListItem(label="Direct - Movie Search")
    item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "movies.png")})
    addDirectoryItem(HANDLE, get_url(action="search", method='movie'), item,  isFolder= True)

    item = ListItem(label="Direct - Anime Search")
    item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "search.png")})
    addDirectoryItem(HANDLE, get_url(action="anime_search"), item, isFolder= True)

    item = ListItem(label="Settings")
    item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "settings.png")})
    addDirectoryItem(HANDLE, get_url(action="settings"), item,  isFolder= True)

    item = ListItem(label="History")
    item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "history.png")})
    addDirectoryItem(HANDLE, get_url(action="main_history"), item,  isFolder= True)
   
    endOfDirectory(HANDLE)

@register
def genre_menu():
    item = ListItem(label="TV Shows")
    item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "tv.png")})
    addDirectoryItem(HANDLE, get_url(action="tmb_search_genre", mode="tv_genres"), item,  isFolder= True)

    item = ListItem(label="Movies")
    item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "movies.png")})
    addDirectoryItem(HANDLE, get_url(action="tmb_search_genre", mode="movie_genres"), item,  isFolder= True)

    endOfDirectory(HANDLE)

@register
def play_jackett(title, magnet, url):
    play(title=title, magnet=magnet, url=url)

######Main#######

@register
def tmdb(mode, id=0):
    search_tmdb(mode, genre_id=id)

@register
def tmb_search_genre(mode):
    search_tmdb(mode)

#####Search API TMDB######

@register
def tmdb_search_api(query, mode):
    search_api(query=query, method=mode)

#####Search Direct######

@register
def search(method=''):
    search_api(method=method)

@register
def anime_search():
    search_api(tracker='anime')

######Next#######

@register
def next_page(mode, page, genre_id=0):
    search_tmdb(mode=mode, genre_id=int(genre_id), page=int(page))

#####Others######

@register
def search_tv_details(id):
    tv_details(int(id))

@register
def settings():
    addon_settings()

@register
def main_history():
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
