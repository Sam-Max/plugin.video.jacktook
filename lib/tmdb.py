import os
import threading
from lib.db.main_db import main_db
from lib.api.tmdbv3api.objs.search import Search
from lib.utils.utils import (
    TMDB_BACKDROP_URL,
    TMDB_POSTER_URL,
    Anime,
    add_next_button,
    execute_thread_pool,
    get_tmdb_movie_data,
    get_tmdb_tv_data,
    set_media_infotag,
    tmdb_get,
)

from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory

from lib.api.jacktook.kodi import kodilog
from lib.api.tmdbv3api.objs.anime import TmdbAnime
from lib.db.main_db import main_db
from lib.utils.kodi_utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    MOVIES_TYPE,
    SHOWS_TYPE,
    build_url,
    play_media,
    show_keyboard,
    notification,
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
        return handle_multi_search(page)
    elif mode == "movies":
        return handle_movie_search(genre_id, page)
    elif mode == "tv":
        return handle_tv_search(genre_id, page)


def handle_multi_search(page):
    if page == 1:
        query = show_keyboard(id=30241)
        if not query:
            return
        main_db.set_query("search_query", query)
    else:
        query = main_db.get_query("search_query")
    return Search().multi(query, page=page)


def handle_movie_search(genre_id, page):
    if genre_id != -1:
        return tmdb_get(
            "discover_movie",
            {
                "with_genres": genre_id,
                "append_to_response": "external_ids",
                "page": page,
            },
        )
    return tmdb_get("trending_movie", page)


def handle_tv_search(genre_id, page):
    if genre_id != -1:
        return tmdb_get("discover_tv", {"with_genres": genre_id, "page": page})
    return tmdb_get("trending_tv", page)


def handle_tmdb_query(query, category, mode, submode, page):
    if mode == "movies":
        handle_tmdb_movie_query(query, page, mode)
    elif mode == "tv":
        handle_tmdb_tv_query(query, page, mode)
    elif mode == "anime":
        handle_tmdb_anime_query(category, submode, page)


def handle_tmdb_movie_query(query, page, mode):
    if query == "tmdb_trending":
        result = search("movies", genre_id=-1, page=page)
        process_tmdb_result(result, mode, page)
    elif query == "tmdb_genres":
        result = get_genre_items(mode="movie_genres")
        process_genres_results(result, mode, page)


def handle_tmdb_tv_query(query, page, mode):
    if query == "tmdb_trending":
        result = search(mode="tv", genre_id=-1, page=page)
        process_tmdb_result(result, mode, page)
    elif query == "tmdb_genres":
        result = get_genre_items(mode="tv_genres")
        process_genres_results(result, mode, page)


def handle_tmdb_anime_query(category, mode, page):
    kodilog("handle_tmdb_anime_query")
    setContent(ADDON_HANDLE, SHOWS_TYPE if mode == "tv" else MOVIES_TYPE)
    anime = TmdbAnime()
    if category == Anime.SEARCH:
        if page == 1:
            query = show_keyboard(id=30242)
            if not query:
                return
            main_db.set_query("anime_query", query)
        else:
            query = main_db.get_query("anime_query")
        data = anime.anime_search(query, mode, page)
        data = anime_checker(data, mode)
    elif category == Anime.AIRING:
        data = anime.anime_on_the_air(mode, page)
    elif category == Anime.POPULAR:
        data = anime.anime_popular(mode, page)
        kodilog(data)
    process_anime_result(data, mode, category, page)


def process_anime_result(data, mode, category, page):
    kodilog("process_anime_result")
    if data:
        if data.total_results == 0:
            notification("No results found")
            return
        show_anime_results(data, mode, category, page)


def process_tmdb_result(data, mode, page):
    if data:
        if data.total_results == 0:
            notification("No results found")
            return
        show_tmdb_results(
            data.results,
            page=page,
            genre_id=-1,
            mode=mode,
        )


def show_anime_results(data, mode, category, page):
    kodilog("show_anime_results")
    execute_thread_pool(data.results, anime_show_results, mode)
    add_next_button("next_page_anime", page=page, mode=mode, category=category)


def show_tmdb_results(results, page, mode, genre_id=0):
    execute_thread_pool(results, show_items, mode)
    add_next_button("search_tmdb", page=page, mode=mode, genre_id=genre_id)


def show_items(res, mode):
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
   
    list_item.setProperty("IsPlayable", "true")

    if mode == "movies":
        list_item.addContextMenuItems(
            [
                (
                    "Rescrape item",
                    play_media(
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
            ADDON_HANDLE,
            build_url(
                "search",
                mode=mode,
                query=title,
                ids=ids,
            ),
            list_item,
            isFolder=False,
        )
    else:
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "tv_seasons_details",
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


def process_genres_results(data, mode, page):
    for g in data.genres:
        name = g["name"]
        if name == "TV Movie":
            continue
        list_item = ListItem(label=name)
        list_item.setProperty("IsPlayable", "false")
        add_icon_genre_single(list_item)
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "search_tmdb", mode=mode.split("_")[0], genre_id=g["id"], page=page
            ),
            list_item,
            isFolder=True,
        )
    endOfDirectory(ADDON_HANDLE)


def anime_show_results(res, mode):
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
    list_item.setProperty("IsPlayable", "true")

    set_media_infotag(
        list_item,
        mode,
        title,
        description,
    )

    if mode == "tv":
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "tv_seasons_details",
                ids=ids,
                mode=mode,
            ),
            list_item,
            isFolder=True,
        )
    else:
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "search",
                mode=mode,
                query=title,
                ids=ids,
            ),
            list_item,
            isFolder=False,
        )


def anime_checker(results, mode):
    anime_results = []
    anime = TmdbAnime()
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


def get_tmdb_media_details(tmdb_id, mode):
    if not tmdb_id:
        return
    if mode == "tv":
        details = tmdb_get("tv_details", tmdb_id)
    elif mode == "movies":
        details = tmdb_get("movie_details", tmdb_id)
    return details