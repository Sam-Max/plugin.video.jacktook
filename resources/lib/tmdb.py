import os

from resources.lib.kodi import ADDON_PATH, log
from resources.lib.tmdbv3api.objs.movie import Movie

from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory

TMDB_POSTER_URL = "http://image.tmdb.org/t/p/w500"
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


def tmdb_show_results(results, func, func2, next_func, page, plugin, mode, genre_id=0):
    for res in results:
        id = res.id
        duration = ""
        media_type= ""

        if mode == "movie":
            title = res.title
            release_date = res.release_date
            duration = Movie().details(int(id)).runtime
        elif mode == "tv":
            title = res.name
            release_date = res.get("first_air_date", "")
        elif mode == "multi":
            if "name" in res:
                title = res.name
            elif "title" in res:
                title = res.title
            if res["media_type"] == "movie":
                media_type = "movie"
                release_date = res.release_date
                duration = Movie().details(int(id)).runtime
                title= f"[B][MOVIE][/B]- {title}"
            elif res["media_type"] == "tv":
                media_type = "tv"
                release_date = res.get("first_air_date", "")
                title= f"[B][TV][/B]- {title}"

        poster_path = (
            TMDB_POSTER_URL + res.poster_path if res.get("poster_path") else ""
        )
        backdrop_path = (
            TMDB_BACKDROP_URL + res.backdrop_path if res.get("backdrop_path") else ""
        )

        overview = res.overview if res.get("overview") else ""

        list_item = ListItem(label=title)
        list_item.setArt(
            {
                "poster": poster_path,
                "fanart": backdrop_path,
                "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
            }
        )
        list_item.setInfo(
            "video",
            {
                "title": title,
                "mediatype": "video",
                "aired": release_date,
                "duration": duration,
                "plot": overview,
            },
        )
        list_item.setProperty("IsPlayable", "false")

        title = title.replace("/", "")

        if "movie" in [mode, media_type]:
            addDirectoryItem(
                plugin.handle,
                plugin.url_for(func, mode=mode, query=title, id=id),
                list_item,
                isFolder=True,
            )
        else:
            addDirectoryItem(
                plugin.handle,
                plugin.url_for(func2, id=id),
                list_item,
                isFolder=True,
            )

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
