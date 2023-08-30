
import os
from resources.lib.tmdbv3api.objs.search import Search
from resources.lib.tmdbv3api.objs.season import Season
from resources.lib.tmdbv3api.objs.trending import Trending
from resources.lib.tmdbv3api.tmdb import TMDb
from resources.lib.util import ADDON_PATH, HANDLE, get_setting, get_url, hide_busy_dialog, notify
from xbmc import Keyboard
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory


tmdb_base_image_url= "http://image.tmdb.org/t/p/w500"


def search_tmdb(mode, page=1):
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
                    action='search_jackett_tmdb', 
                    next_action='next_page_multi', 
                    page=page,
                    type='multi')
    elif mode == 'movie':
        trending = Trending()
        movies = trending.movie_week(page=page)
        page += 1
        show_results(movies.results, 
                    action='search_jackett_tmdb_movie', 
                    next_action='next_page_movie', 
                    page=page,
                    type='movie')
    elif mode == 'tv':
        trending = Trending()
        shows= trending.tv_day(page=page)
        page += 1
        show_results(shows.results, 
                    action='search_jackett_tmdb_tv', 
                    next_action='next_page_tv', 
                    page=page,
                    type='tv')

def tv_details(id):
    season = Season()
    show_season = season.details(id, 1)
    for ep in show_season.episodes:
        title= f'Episode {ep.episode_number} - {ep.name}'
        search_title= ep.name
        list_item = ListItem(label=title)
        url= ''
        if ep.still_path:
            url = tmdb_base_image_url + ep.still_path

        list_item.setArt({'poster': url, "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png")})
        list_item.setInfo("video",{"title": title, "mediatype": "video", "plot": f"{ep.overview}"})
        list_item.setProperty("IsPlayable", "false")
        addDirectoryItem(HANDLE, get_url(action='search_jackett_tmdb_tv', query=search_title), list_item, isFolder=True)

    endOfDirectory(HANDLE)

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
        url= ''
        if res.poster_path:
            url = tmdb_base_image_url + res.poster_path

        list_item = ListItem(label=title)
        list_item.setArt({'poster': url, "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png")})
        list_item.setInfo(
            "video",
            {"title": title, "mediatype": "video", "plot": f"{res.overview}"},
        )
        list_item.setProperty("IsPlayable", "false")

        addDirectoryItem(HANDLE, get_url(action=action, query=title), list_item, isFolder=True)

    list_item = ListItem(label='Next')
    list_item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "img", "nextpage.png")})
    addDirectoryItem(HANDLE,
            get_url(action=next_action, page=page),
            list_item,
            isFolder=True,
        )
    
    endOfDirectory(HANDLE)

