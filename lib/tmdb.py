import os
from lib.db.main_db import main_db
from lib.api.tmdbv3api.objs.search import Search

from lib.utils.kodi_utils import (
    ADDON_PATH,
    Keyboard,
    container_update,
    notification,
    url_for,
)
from lib.utils.utils import (
    add_next_button,
    execute_thread_pool,
    get_tmdb_movie_data,
    get_tmdb_tv_data,
    set_media_infotag,
    tmdb_get,
)

from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory

TMDB_POSTER_URL = "http://image.tmdb.org/t/p/w780"
TMDB_BACKDROP_URL = "http://image.tmdb.org/t/p/w1280"


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
            text = Keyboard(id=30241)
            if text:
                main_db.set_query("query", text)
            else:
                return
        else:
            text = main_db.get_query("query")
        return Search().multi(str(text), page=page)
    elif mode == "movie":
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

    if mode == "movie":
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
            release_date = res.release_date
            imdb_id, duration = get_tmdb_movie_data(tmdb_id)
            tvdb_id = -1
            label_title = f"[B][MOVIE][/B]- {title}"
        elif media_type == "tv":
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

    if "movie" in [mode, media_type]:
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


####################################################


def handle_tmdb_query(query, mode, page, plugin):
    if mode == "movie":
        handle_tmdb_movie_query(query, page, mode, plugin)
    else:
        handle_tmdb_tv_query(query, page, mode, plugin)


def handle_tmdb_movie_query(query, page, mode, plugin):
    if query == "tmdb_trending":
        result = search("movie", genre_id=-1, page=page)
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
