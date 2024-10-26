import os
import threading
from lib.api.tmdbv3api.objs.anime import Anime
from lib.db.main_db import main_db
from lib.tmdb import TMDB_POSTER_URL
from lib.utils.kodi_utils import (
    ADDON_PATH,
    MOVIES_TYPE,
    SHOWS_TYPE,
    Keyboard,
    get_kodi_version,
    notification,
    url_for,
)
from lib.utils.utils import (
    add_next_button,
    execute_thread_pool,
    get_tmdb_movie_data,
    get_tmdb_tv_data,
    run_task,
    set_media_infotag,
    set_video_info,
)
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, setContent


def search_anime(mode, category, page, plugin=None):
    setContent(plugin.handle, SHOWS_TYPE if mode == "tv" else MOVIES_TYPE)
    anime = Anime()
    if category == "Anime_Search":
        if page == 1:
            query = Keyboard(id=30242)
            if not query:
                return
            main_db.set_query("anime_query", query)
        else:
            query = main_db.get_query("anime_query")
        data = anime.anime_search(query, mode, page)
        data = anime_checker(data, mode)
    elif category == "Anime_On_The_Air":
        data = anime.anime_on_the_air(mode, page)
    elif category == "Anime_Popular":
        data = anime.anime_popular(mode, page)

    if data:
        if data.total_results == 0:
            notification("No results found")
            return

        execute_thread_pool(data.results, anime_show_results, mode, plugin)
        add_next_button("anime_next_page", plugin, page, mode=mode, category=category)


def anime_show_results(res, mode, plugin):
    description = res.get("overview", "")
    poster_path = res.get("poster_path", "")

    tmdb_id = res.get("id", -1)
    if mode == "movies":
        title = res.title
        imdb_id, _ = get_tmdb_movie_data(tmdb_id)
        tvdb_id = -1
    elif mode == "tv":
        title = res.name
        title = res["name"]
        imdb_id, tvdb_id = get_tmdb_tv_data(tmdb_id)

    ids = f"{tmdb_id}, {tvdb_id}, {imdb_id}"

    list_item = ListItem(label=title)
    list_item.setArt(
        {
            "poster": TMDB_POSTER_URL + poster_path if poster_path else "",
            "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
        }
    )
    list_item.setProperty("IsPlayable", "false")

    if get_kodi_version() >= 20:
        set_media_infotag(
            list_item,
            mode,
            title,
            description,
        )
    else:
        set_video_info(
            list_item,
            mode,
            title,
            description,
        )

    if mode == "tv":
        addDirectoryItem(
            plugin.handle,
            url_for(
                name="tv/details",
                ids=ids,
                mode=mode,
                media_type="anime",
            ),
            list_item,
            isFolder=True,
        )
    else:
        addDirectoryItem(
            plugin.handle,
            url_for(
                name="search",
                mode=mode,
                query=title,
                ids=ids,
            ),
            list_item,
            isFolder=True,
        )


def anime_checker(results, mode):
    anime_results = []
    anime = Anime()
    list_lock = threading.Lock()
    def task(results, anime_results, list_lock):
        for item in results["results"]:
            results = anime.tmdb_keywords(mode, item["id"])
            if mode == "tv":
                keywords = results["results"]
            else:
                keywords = results["keywords"]
            for i in keywords:
                if i["id"] == 210024:
                    with list_lock:
                        anime_results.append(item)
    run_task(task, results, anime_results, list_lock)            
    results["results"] = anime_results
    results["total_results"] = len(anime_results)
    return results
