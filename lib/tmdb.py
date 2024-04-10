import os
from concurrent.futures import ThreadPoolExecutor
from lib.db.database import get_db
from lib.api.tmdbv3api.objs.search import Search

from lib.utils.kodi import (
    ADDON_PATH,
    Keyboard,
    container_update,
    get_kodi_version,
    url_for,
)
from lib.utils.utils import (
    get_movie_data,
    get_tv_data,
    set_video_info,
    set_video_infotag,
    tmdb_get,
)

from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory

TMDB_POSTER_URL = "http://image.tmdb.org/t/p/w780"
TMDB_BACKDROP_URL = "http://image.tmdb.org/t/p/w1280"


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


def tmdb_search(mode, genre_id, page, func, plugin):
    genre_id = int(genre_id)
    if mode == "movie_genres" or mode == "tv_genres":
        menu_genre(mode, page, func, plugin)
        return {}

    if mode == "multi":
        if page == 1:
            text = Keyboard(id=30241)
            if text:
                get_db().set_search_string("text", text)
            else:
                return
        else:
            text = get_db().get_search_string("text")
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
    else:
        return {}


def tmdb_show_results(results, next_func, page, plugin, mode, genre_id=0):
    with ThreadPoolExecutor(max_workers=len(results)) as executor:
        [executor.submit(tmdb_show_items, res, plugin, mode) for res in results]
        executor.shutdown(wait=True)

    list_item = ListItem(label="Next")
    list_item.setArt(
        {"icon": os.path.join(ADDON_PATH, "resources", "img", "nextpage.png")}
    )
    page += 1
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(next_func, mode=mode, page=page, genre_id=genre_id),
        list_item,
        isFolder=True,
    )

    endOfDirectory(plugin.handle)


def tmdb_show_items(res, plugin, mode):
    tmdb_id = res.id
    duration = ""
    media_type = res.get("media_type", "")

    if mode == "movie":
        title = res.title
        release_date = res.release_date
        imdb_id, tvdb_id, duration = get_movie_data(tmdb_id)
    elif mode == "tv":
        title = res.name
        imdb_id, tvdb_id = get_tv_data(tmdb_id)
        release_date = res.get("first_air_date", "")
    elif mode == "multi":
        if "name" in res:
            title = res.name
        elif "title" in res:
            title = res.title
        if media_type == "movie":
            release_date = res.release_date
            imdb_id, tvdb_id, duration = get_movie_data(tmdb_id)
            title = f"[B][MOVIE][/B]- {title}"
        elif media_type == "tv":
            release_date = res.get("first_air_date", "")
            imdb_id, tvdb_id = get_tv_data(tmdb_id)
            title = f"[B][TV][/B]- {title}"

    poster_path = res.get("poster_path", "")
    if poster_path:
        poster_path = TMDB_POSTER_URL + poster_path

    backdrop_path = res.get("backdrop_path", "")
    if backdrop_path:
        backdrop_path = TMDB_BACKDROP_URL + backdrop_path

    overview = res.get("overview", "")
    ids = f"{tmdb_id}, {tvdb_id}, {imdb_id}"

    list_item = ListItem(label=title)

    if get_kodi_version() >= 20:
        set_video_infotag(
            list_item,
            mode,
            title,
            overview,
            air_date=release_date,
            duration=duration,
            ids=ids,
        )
    else:
        set_video_info(
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


def menu_genre(mode, page, func, plugin):
    if mode == "movie_genres":
        data = tmdb_get(mode)
    elif mode == "tv_genres":
        data = tmdb_get(mode)

    for d in data.genres:
        name = d["name"]
        if name == "TV Movie":
            continue
        item = ListItem(label=name)
        add_icon_genre(item, name)
        addDirectoryItem(
            plugin.handle,
            plugin.url_for(func, mode=mode.split("_")[0], genre_id=d["id"], page=page),
            item,
            isFolder=True,
        )
    endOfDirectory(plugin.handle)
