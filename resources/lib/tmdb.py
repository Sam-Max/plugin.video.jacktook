
import os

from resources.lib.kodi import ADDON_PATH

from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory

TMDB_POSTER_URL = "http://image.tmdb.org/t/p/w500"
TMDB_BACKDROP_URL = "http://image.tmdb.org/t/p/w780"


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
    
def tmdb_show_results(results, action_func, next_action_func, page, plugin, mode, genre_id=0):
    for res in results:
        id = res.id
        release_date = ''
        
        if mode == 'movie':
            title = res.title
            release_date = res.release_date
        elif mode == 'tv':
            title = res.name
            release_date = res.first_air_date
        elif mode == 'multi':
            if 'name' in res:
                title = res.name 
            if 'title' in res:
                title= res.title

        poster_path= res.poster_path if res.get('poster_path') else ''
        backdrop_path= res.backdrop_path if res.get('backdrop_path') else ''

        if poster_path:
            poster_path = TMDB_POSTER_URL + res.poster_path
        if backdrop_path:
            backdrop_path = TMDB_BACKDROP_URL + res.backdrop_path

        overview= res.overview if res.get('overview') else ''

        list_item = ListItem(label=title)
        list_item.setArt({
             "poster": poster_path, 
             "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
             "fanart": backdrop_path,
             })
        list_item.setInfo("video", {"title": title, 
             "mediatype": "video", 
             "aired": release_date,
             "plot": overview
             })
        list_item.setProperty("IsPlayable", "false")

        if action_func.__name__ == "search":
            addDirectoryItem(plugin.handle, plugin.url_for(action_func, mode=mode, query=title, tracker='all'), list_item, isFolder=True)
        else:
            addDirectoryItem(plugin.handle, plugin.url_for(action_func, id=id), list_item, isFolder=True)

    list_item = ListItem(label='Next')
    list_item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "nextpage.png")})
    addDirectoryItem(plugin.handle, plugin.url_for(next_action_func, mode=mode, page=page, genre_id=genre_id), list_item, isFolder=True)
    
    endOfDirectory(plugin.handle)

