
import logging
import os
from resources.lib.tmdbv3api.objs.genre import Genre
import routing

from resources.lib.tmdbv3api.objs.discover import Discover
from resources.lib.tmdbv3api.objs.search import Search
from resources.lib.tmdbv3api.objs.trending import Trending
from resources.lib.tmdbv3api.tmdb import TMDb
from resources.lib.tmdb import TMDB_POSTER_URL, add_icon_genre, tmdb_show_results
from resources.lib.anilist import search_anilist
from resources.lib.utils import api_show_results, clear, filter_quality, history, play, search_api, sort_results
from resources.lib.kodi import ADDON_PATH, addon_settings, get_setting, hide_busy_dialog, notify
from resources.lib.tmdbv3api.objs.season import Season
from resources.lib.tmdbv3api.objs.tv import TV

from xbmcgui import ListItem
from xbmc import Keyboard
from xbmcplugin import addDirectoryItem, endOfDirectory, setPluginCategory


plugin = routing.Plugin()


@plugin.route("/")
def main_menu():
    setPluginCategory(plugin.handle, "Main Menu")

    addDirectoryItem(plugin.handle, plugin.url_for(search_tmdb, mode='multi', genre_id=-1, page=1),  list_item("Search", "search.png"), isFolder= True)
    addDirectoryItem(plugin.handle, plugin.url_for(search_tmdb, mode='tv', genre_id=-1, page=1),  list_item("TV Shows", "tv.png"), isFolder= True)
    addDirectoryItem(plugin.handle, plugin.url_for(search_tmdb, mode='movie', genre_id=-1, page=1), list_item("Movies", "movies.png"), isFolder= True)
    addDirectoryItem(plugin.handle, plugin.url_for(anime_menu),  list_item("Anime", "movies.png"), isFolder= True)
    addDirectoryItem(plugin.handle, plugin.url_for(genre_menu), list_item("By Genre", "movies.png"), isFolder= True)
    addDirectoryItem(plugin.handle, plugin.url_for(search, mode='multi', query=None, tracker='all'), list_item("Direct - Search", "search.png"), isFolder= True)
    addDirectoryItem(plugin.handle, plugin.url_for(search, mode='tv', query=None, tracker='all'), list_item("Direct - TV Search", "tv.png"),  isFolder= True)
    addDirectoryItem(plugin.handle, plugin.url_for(search, mode='movie', query=None, tracker='all'), list_item("Direct - Movie Search", "movies.png"),  isFolder= True)
    addDirectoryItem(plugin.handle, plugin.url_for(search, mode='multi', query=None, tracker='anime'), list_item("Direct - Anime Search", "search.png"), isFolder= True)
    addDirectoryItem(plugin.handle, plugin.url_for(settings), list_item("Settings", "settings.png"),  isFolder= True)
    addDirectoryItem(plugin.handle, plugin.url_for(main_history), list_item("History", "history.png"),  isFolder= True)
    endOfDirectory(plugin.handle)

@plugin.route("/anime")
def anime_menu():
    addDirectoryItem(plugin.handle, plugin.url_for(anilist, category='search'), list_item("Search", "search.png"), isFolder= True)
    addDirectoryItem(plugin.handle, plugin.url_for(anilist, category="Popular", ), list_item("Popular", "tv.png"),  isFolder= True)
    addDirectoryItem(plugin.handle, plugin.url_for(anilist, category="Trending"), list_item("Trending", "movies.png"),  isFolder= True)
    endOfDirectory(plugin.handle)

@plugin.route("/genre")
def genre_menu():
    addDirectoryItem(plugin.handle, plugin.url_for(search_tmdb, mode="tv_genres",  genre_id=-1, page=1), list_item("TV Shows", "tv.png"),  isFolder= True)
    addDirectoryItem(plugin.handle, plugin.url_for(search_tmdb, mode="movie_genres", genre_id=-1, page=1), list_item("Movies", "movies.png"),  isFolder= True)
    endOfDirectory(plugin.handle)

@plugin.route("/search/<mode>/<query>/<tracker>")
def search(mode, query, tracker):
    response= search_api(query, mode, tracker)
    if response:
        sorted_res= sort_results(response)
        filtered_res= filter_quality(sorted_res)
        api_show_results(filtered_res, plugin, func=play_torrent)

@plugin.route("/play_torrent")
def play_torrent():
    url, magnet, title = plugin.args['query'][0].split(" ", 2)
    play(url=url, title=title, magnet=magnet)

@plugin.route("/search/tmdb/<mode>/<genre_id>/<page>")
def search_tmdb(mode, genre_id, page):
    page = int(page)
    genre_id= int(genre_id)

    api_key = get_setting('tmdb_apikey')
    if api_key:
        tmdb = TMDb()
        tmdb.api_key = api_key
    else:
        notify("No TMDB api key set")
        return
    
    if mode == 'multi':
        keyboard = Keyboard("", "Search on TMDB:", False)
        keyboard.doModal()
        if keyboard.isConfirmed():
            text = keyboard.getText().strip()
        else:
            hide_busy_dialog()
            return
        search_ = Search()
        results = search_.multi(str(text), page=page)
        tmdb_show_results(results,
                    action_func=search, 
                    next_action_func=next_page, 
                    page=page,
                    plugin=plugin,
                    mode=mode)
    elif mode == 'movie':
        if genre_id != -1:
            discover = Discover()
            movies = discover.discover_movies({'with_genres': genre_id, 'page': page})
            tmdb_show_results(movies.results, 
                        action_func=search, 
                        next_action_func=next_page, 
                        page=page,
                        plugin= plugin,
                        genre_id=genre_id,
                        mode=mode)
        else:
            trending = Trending()
            movies = trending.movie_week(page=page)
            tmdb_show_results(movies.results, 
                        action_func=search, 
                        next_action_func=next_page, 
                        page=page,
                        plugin= plugin,
                        genre_id= genre_id,
                        mode=mode)
    elif mode == 'tv':
        if genre_id != -1:
            discover = Discover()
            tv_shows = discover.discover_tv_shows({'with_genres': genre_id, 'page': page})
            tmdb_show_results(tv_shows.results, 
                        action_func=tv_details, 
                        next_action_func=next_page, 
                        page=page,
                        plugin= plugin,
                        genre_id= genre_id,
                        mode=mode)
        else:
            trending = Trending()
            shows= trending.tv_day(page=page)
            tmdb_show_results(shows.results, 
                        action_func=tv_details, 
                        next_action_func=next_page, 
                        page=page,
                        plugin= plugin,
                        genre_id= genre_id,
                        mode=mode)
    elif mode == 'movie_genres':
       menu_genre(mode, page)
    elif mode == 'tv_genres':
       menu_genre(mode, page)   


@plugin.route("/tv/details/<id>")
def tv_details(id):
    tv = TV()
    details = tv.details(id)

    tv_name= details.original_name
    number_of_seasons= details.number_of_seasons

    for i in range(number_of_seasons):
        number = i+1
        title= f'Season {number}'
        list_item = ListItem(label=title)
        poster_path= ''
        if details.poster_path:
            poster_path = TMDB_POSTER_URL + details.poster_path

        list_item.setArt({'poster': poster_path, "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png")})
        list_item.setInfo("video", {"title": title, "mediatype": "video", "plot": f"{details.overview}"})
        list_item.setProperty("IsPlayable", "false")
        
        addDirectoryItem(plugin.handle, plugin.url_for(tv_season_details, tv_name=tv_name, id=id, season_num=number), list_item, isFolder=True)

    endOfDirectory(plugin.handle)

@plugin.route("/tv/details/season/<tv_name>/<id>/<season_num>")
def tv_season_details(tv_name, id, season_num):    
    season = Season()
    tv_season = season.details(id, season_num)
    for ep in tv_season.episodes:
        title = f"{season_num}x0{ep.episode_number}. {ep.name}"
        air_date = ep.air_date

        list_item = ListItem(label=title)
        url= ''
        if ep.still_path:
            url = TMDB_POSTER_URL + ep.still_path

        list_item.setArt({'poster': url, "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png")})
        list_item.setInfo("video", {"title": title, 
                           "mediatype": "video", 
                           "aired": air_date, 
                           "plot": f"{ep.overview}"})
        list_item.setProperty("IsPlayable", "false")
        
        addDirectoryItem(plugin.handle, plugin.url_for(search, query=tv_name, mode='tv', tracker='all'), list_item, isFolder=True)

    endOfDirectory(plugin.handle)

@plugin.route("/anilist/<category>")
def anilist(category, page=1):
    search_anilist(category, page, plugin, action=search, next_action=next_page_anilist) 

@plugin.route("/next_page/anilist/<category>/<page>")
def next_page_anilist(category, page):
    search_anilist(category, int(page), plugin, action=search, next_action=next_page_anilist)  

@plugin.route("/next_page/<mode>/<page>/<genre_id>")
def next_page(mode, page, genre_id):
    search_tmdb(mode=mode, genre_id=int(genre_id), page=int(page))

@plugin.route("/settings")
def settings():
    addon_settings()

@plugin.route("/history")
def main_history():
    history(plugin, clear_history, play_torrent)

@plugin.route("/history/clear")
def clear_history():
    clear()

def list_item(label, icon):
    item = ListItem(label)
    item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", icon)})
    return item

def menu_genre(mode, page):
    if mode == 'movie_genres':
        movies= Genre().movie_list()
        for gen in movies.genres:
            if gen['name'] == "TV Movie":
                continue
            name = gen['name']
            item = ListItem(label=name)
            add_icon_genre(item, name)
            addDirectoryItem(plugin.handle, plugin.url_for(search_tmdb, mode="movie", genre_id=gen['id'], page=page), item, isFolder=True)
    elif mode == 'tv_genres':
        tv= Genre().tv_list()
        for gen in tv.genres:
            name = gen['name']
            item = ListItem(label=name)
            add_icon_genre(item, name)
            addDirectoryItem(plugin.handle, plugin.url_for(search_tmdb, mode="tv", genre_id=gen['id'], page=page), item, isFolder=True)
    endOfDirectory(plugin.handle)

def run():
    try:
        plugin.run()
    except Exception as e:
        logging.error("Caught exception:", exc_info=True)
        notify(str(e))