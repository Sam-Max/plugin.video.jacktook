
import os
from resources.lib.tmdbv3api.objs.discover import Discover
from resources.lib.tmdbv3api.objs.genre import Genre
from resources.lib.tmdbv3api.objs.search import Search
from resources.lib.tmdbv3api.objs.season import Season
from resources.lib.tmdbv3api.objs.trending import Trending
from resources.lib.tmdbv3api.tmdb import TMDb
from resources.lib.kodi import ADDON_PATH, HANDLE, get_setting, get_url, hide_busy_dialog, notify
from xbmc import Keyboard
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory



tmdb_img_url= "http://image.tmdb.org/t/p/"


def search_tmdb(mode, genre_id=0, page=1):
    api_key = get_setting('tmdb_apikey')
    if not api_key:
        notify("No TMDB api key set")
        return
    else:
        tmdb = TMDb()
        tmdb.api_key = api_key
    if mode == 'multi':
        keyboard = Keyboard("", "Search on TMDB:", False)
        keyboard.doModal()
        if keyboard.isConfirmed():
            text = keyboard.getText().strip()
        else:
            hide_busy_dialog()
            return
        search = Search()
        results = search.multi(str(text), page=page)
        show_results(results,
                    action='tmdb_search', 
                    next_action='next_page_multi', 
                    page=page,
                    type='multi')
    elif mode == 'movie':
        if genre_id != 0:
            discover = Discover()
            movies = discover.discover_movies({'with_genres': genre_id})
            show_results(movies.results, 
                        action='search_tmdb_movie', 
                        next_action='next_page_movie', 
                        page=page,
                        type='movie')
        else:
            trending = Trending()
            movies = trending.movie_week(page=page)
            page += 1
            show_results(movies.results, 
                        action='search_tmdb_movie', 
                        next_action='next_page_movie', 
                        page=page,
                        type='movie')
    elif mode == 'tv':
        if genre_id != 0:
            discover = Discover()
            tv_shows = discover.discover_tv_shows({'with_genres': genre_id})
            show_results(tv_shows.results, 
                        action='search_tmdb_tv', 
                        next_action='next_page_tv', 
                        page=page,
                        type='tv')
        else:
            trending = Trending()
            shows= trending.tv_day(page=page)
            page += 1
            show_results(shows.results, 
                        action='search_tmdb_tv', 
                        next_action='next_page_tv', 
                        page=page,
                        type='tv')
    elif mode == 'movie_genres':
        movies= Genre().movie_list()
        for gen in movies.genres:
            if gen['name'] == "TV Movie":
                continue
            name = gen['name']
            item = ListItem(label=name)
            add_icon_genre(item, name)
            addDirectoryItem(HANDLE, get_url(action="tmdb_movie", id=gen['id'], mode="movie"), item, isFolder=True)
        endOfDirectory(HANDLE)
    elif mode == 'tv_genres':
        tv= Genre().tv_list()
        for gen in tv.genres:
            name = gen['name']
            item = ListItem(label=name)
            add_icon_genre(item, name)
            addDirectoryItem(HANDLE, get_url(action="tmdb_tv", id=gen['id'], mode="tv"), item, isFolder=True)
        endOfDirectory(HANDLE)

def tv_details(id):
    season = Season()
    show_season = season.details(id, 1)
    for ep in show_season.episodes:
        title= f'Episode {ep.episode_number} - {ep.name}'
        search_title= ep.name
        list_item = ListItem(label=title)
        url= ''
        if ep.still_path:
            url = tmdb_img_url + 'w500' + ep.still_path

        list_item.setArt({'poster': url, "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png")})
        list_item.setInfo("video",{"title": title, "mediatype": "video", "plot": f"{ep.overview}"})
        list_item.setProperty("IsPlayable", "false")
        addDirectoryItem(HANDLE, get_url(action='search_tmdb_tv', query=search_title), list_item, isFolder=True)

    endOfDirectory(HANDLE)

def add_icon_genre(item, name):
    genre_icons = {
        "Action": "genre_action.png",
        "Adventure": "genre_adventure.png",
        "Action & Adventure": "genre_adventure.png",
        "Science Fiction": "genre_scifi.png",
        "Sci-Fi & Fantasy": "genre_scifi.png",
        "Fantasy": "genre_fantasy.png",
        "Animation": "genre_animation.png",
        "Comedy": "genre_comedy.png",
        "Crime": "genre_crime.png",
        "Documentary": "genre_documentary.png",
        "Kids": "genre_kids.png",
        "News":"genre_news.png",
        "Reality":"genre_reality.png",
        "Soap":"genre_soap.png",
        "Talk":"genre_talk.png",
        "Drama": "genre_drama.png",
        "Family": "genre_family.png",
        "History": "genre_history.png",
        "Horror": "genre_horror.png",
        "Music": "genre_music.png",
        "Mystery": "genre_mystery.png",
        "Romance": "genre_romance.png",
        "Thriller": "genre_thriller.png",
        "War": "genre_war.png",
        "War & Politics": "genre_war.png",
        "Western": "genre_western.png"
    }
    icon_path = genre_icons.get(name)
    if icon_path:
        item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", icon_path)})  

def show_results(results, action, next_action, page, type=''):
    for res in results:
        if type == 'movie':
            title = res.title
        elif type == 'tv':
            title = res.name
        elif type == 'multi':
            if 'name' in res:
                title = res.name 
            if 'title' in res:
                title= res.title

        poster= ''
        backdrop_path= ''
        if res.poster_path:
            poster= tmdb_img_url + 'w500' + res.poster_path
        if res.backdrop_path:
            backdrop_path= tmdb_img_url + 'w780' + res.backdrop_path

        list_item = ListItem(label=title)
        list_item.setArt({'poster': poster, 
             "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
             "fanart": backdrop_path,
             })
        list_item.setInfo("video", {"title": title, 
             "mediatype": "video", 
             "plot": f"{res.overview}"
             })
        list_item.setProperty("IsPlayable", "false")

        addDirectoryItem(HANDLE, get_url(action=action, query=title), list_item, isFolder=True)

    list_item = ListItem(label='Next')
    list_item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "nextpage.png")})
    addDirectoryItem(HANDLE, get_url(action=next_action, page=page),
            list_item,
            isFolder=True,
        )
    
    endOfDirectory(HANDLE)

