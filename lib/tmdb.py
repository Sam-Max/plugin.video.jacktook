import os
import threading
from lib.db.main_db import main_db
from lib.api.tmdbv3api.objs.search import Search
from lib.utils.utils import (
    TMDB_BACKDROP_URL,
    TMDB_POSTER_URL,
    add_next_button,
    execute_thread_pool,
    get_tmdb_movie_data,
    get_tmdb_tv_data,
    set_media_infotag,
    tmdb_get,
    set_video_info,
)

from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory

from lib.api.jacktook.kodi import kodilog
from lib.api.tmdbv3api.objs.anime import Anime
from lib.db.main_db import main_db
from lib.utils.kodi_utils import (
    ADDON_PATH,
    MOVIES_TYPE,
    SHOWS_TYPE,
    Keyboard,
    get_kodi_version,
    notification,
    url_for,
    container_update,
)
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, setContent


def add_icon_genre_single(item, icon_path="tmdb.png"):
    item.setArt(
        {
            "icon": os.path.join(ADDON_PATH, "resources", "img", icon_path),
            "thumb": os.path.join(ADDON_PATH, "resources", "img", icon_path),
        }
    )


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
        "News": "genre_news.png",
        "Reality": "genre_reality.png",
        "Soap": "genre_soap.png",
        "Talk": "genre_talk.png",
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
        "Western": "genre_western.png",
    }
    icon_path = genre_icons.get(name)
    if icon_path:
        item.setArt(
            {
                "icon": os.path.join(ADDON_PATH, "resources", "img", icon_path),
                "thumb": os.path.join(ADDON_PATH, "resources", "img", icon_path),
            }
        )


def search(mode, genre_id, page):
    if mode == "multi":
        if page == 1:
            query = Keyboard(id=30241)
            if not query:
                return
            main_db.set_query("search_query", query)
        else:
            query = main_db.get_query("search_query")
        return Search().multi(str(query), page=page)
    elif mode == "movies":
        if genre_id != -1:
            return tmdb_get(
                "discover_movie",
                {
                    "with_genres": genre_id,
                    "append_to_response": "external_ids",
                    "page": page,
                },
            )
        else:
            return tmdb_get("trending_movie", page)
    elif mode == "tv":
        if genre_id != -1:
            return tmdb_get("discover_tv", {"with_genres": genre_id, "page": page})
        else:
            return tmdb_get("trending_tv", page)


def show_results(results, page, plugin, mode, genre_id=0):
    execute_thread_pool(results, show_items, plugin, mode)
    add_next_button("next_page_tmdb", plugin, page, mode=mode, genre_id=genre_id)


def show_items(res, plugin, mode):
    tmdb_id = res.id
    duration = ""
    media_type = res.get("media_type", "")

    if mode == "movies":
        title = res.title
        label_title = title
        release_date = res.release_date
        imdb_id, duration = get_tmdb_movie_data(tmdb_id)
        tvdb_id = -1
    elif mode == "tv":
        title = res.name
        label_title = title
        imdb_id, tvdb_id = get_tmdb_tv_data(tmdb_id)
        release_date = res.get("first_air_date", "")
    elif mode == "multi":
        if "name" in res:
            title = res.name
        elif "title" in res:
            title = res.title

        if media_type == "movie":
            mode = "movies"
            release_date = res.release_date
            imdb_id, duration = get_tmdb_movie_data(tmdb_id)
            tvdb_id = -1
            label_title = f"[B][MOVIE][/B]- {title}"
        elif media_type == "tv":
            mode = media_type
            release_date = res.get("first_air_date", "")
            imdb_id, tvdb_id = get_tmdb_tv_data(tmdb_id)
            label_title = f"[B][TV][/B]- {title}"

    poster_path = res.get("poster_path", "")
    if poster_path:
        poster_path = TMDB_POSTER_URL + poster_path

    backdrop_path = res.get("backdrop_path", "")
    if backdrop_path:
        backdrop_path = TMDB_BACKDROP_URL + backdrop_path

    overview = res.get("overview", "")
    ids = f"{tmdb_id}, {tvdb_id}, {imdb_id}"

    list_item = ListItem(label=label_title)

    set_media_infotag(
        list_item,
        mode,
        title,
        overview,
        air_date=release_date,
        duration=duration,
        ids=ids,
    )

    list_item.setArt(
        {
            "poster": poster_path,
            "fanart": backdrop_path,
            "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
        }
    )
    list_item.setProperty("IsPlayable", "false")

    if mode == "movies":
        list_item.addContextMenuItems(
            [
                (
                    "Rescrape item",
                    container_update(
                        name="search",
                        mode=mode,
                        query=title,
                        ids=ids,
                        rescrape=True,
                    ),
                )
            ]
        )
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
    else:
        addDirectoryItem(
            plugin.handle,
            url_for(
                name="tv/details",
                ids=ids,
                mode=mode,
                media_type=media_type,
            ),
            list_item,
            isFolder=True,
        )


def get_genre_items(mode):
    if mode == "movie_genres":
        return tmdb_get(mode)
    else:
        return tmdb_get(mode)


def handle_tmdb_query(query, category, mode, submode, page, plugin):
    if mode == "movies":
        handle_tmdb_movie_query(query, page, mode, plugin)
    elif mode == "tv":
        handle_tmdb_tv_query(query, page, mode, plugin)
    elif mode == "anime":
        handle_tmdb_anime_query(category, submode, page, plugin)


def handle_tmdb_anime_query(category, mode, page, plugin):
    kodilog("tmdb_anime::search_anime")
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


def handle_tmdb_movie_query(query, page, mode, plugin):
    if query == "tmdb_trending":
        result = search("movies", genre_id=-1, page=page)
        process_tmdb_result(result, mode, page, plugin)
    elif query == "tmdb_genres":
        result = get_genre_items(mode="movie_genres")
        process_genres_results(result, mode, page, plugin)


def handle_tmdb_tv_query(query, page, mode, plugin):
    if query == "tmdb_trending":
        result = search(mode="tv", genre_id=-1, page=page)
        process_tmdb_result(result, mode, page, plugin)
    elif query == "tmdb_genres":
        result = get_genre_items(mode="tv_genres")
        process_genres_results(result, mode, page, plugin)


def process_tmdb_result(data, mode, page, plugin):
    if data:
        if data.total_results == 0:
            notification("No results found")
            return
        show_results(
            data.results,
            page=page,
            plugin=plugin,
            genre_id=-1,
            mode=mode,
        )


def process_genres_results(data, mode, page, plugin):
    for g in data.genres:
        name = g["name"]
        if name == "TV Movie":
            continue
        list_item = ListItem(label=name)
        list_item.setProperty("IsPlayable", "false")
        add_icon_genre_single(list_item)
        addDirectoryItem(
            plugin.handle,
            url_for(
                name="search_tmdb", mode=mode.split("_")[0], genre_id=g["id"], page=page
            ),
            list_item,
            isFolder=True,
        )
    endOfDirectory(plugin.handle)


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

    def task(res, anime_results, list_lock):
        results = anime.tmdb_keywords(mode, res["id"])
        if mode == "tv":
            keywords = results["results"]
        else:
            keywords = results["keywords"]
        for i in keywords:
            if i["id"] == 210024:
                with list_lock:
                    anime_results.append(res)

    execute_thread_pool(results, task, anime_results, list_lock)
    results["results"] = anime_results
    results["total_results"] = len(anime_results)
    return results
