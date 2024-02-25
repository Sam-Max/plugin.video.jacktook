import os

from resources.lib.utils.kodi import ADDON_PATH, container_update
from resources.lib.utils.utils import tmdb_get

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


def tmdb_show_results(data, func, func2, next_func, page, plugin, mode, genre_id=0):
    for res in data.results:
        id = res.id
        duration = ""
        media_type = ""

        if mode == "movie":
            title = res.title
            release_date = res.release_date
            details = tmdb_get("movie_details", int(id))
            imdb_id = details.external_ids.get("imdb_id")
            tvdb_id = details.external_ids.get("tvdb_id")
            duration = details.runtime
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
                details = tmdb_get("movie_details", int(id))
                imdb_id = details.external_ids.get("imdb_id")
                tvdb_id = details.external_ids.get("tvdb_id")
                duration = details.runtime
                title = f"[B][MOVIE][/B]- {title}"
            elif res["media_type"] == "tv":
                media_type = "tv"
                release_date = res.get("first_air_date", "")
                title = f"[B][TV][/B]- {title}"

        poster_path = res.get("poster_path", "")
        if poster_path:
            poster_path = TMDB_POSTER_URL + poster_path

        backdrop_path = res.get("backdrop_path", "")
        if backdrop_path:
            backdrop_path = TMDB_BACKDROP_URL + backdrop_path

        overview = res.get("overview", "")

        list_item = ListItem(label=title)
        list_item.setArt(
            {
                "poster": poster_path,
                "fanart": backdrop_path,
                "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
            }
        )
        info_tag = list_item.getVideoInfoTag()
        info_tag.setMediaType("video")
        info_tag.setTitle(title)
        info_tag.setPlot(overview)
        info_tag.setFirstAired(release_date)
        if duration:
            info_tag.setDuration(int(duration))

        list_item.setProperty("IsPlayable", "false")

        query = title.replace("/", "").replace("?", "")

        if "movie" in [mode, media_type]:
            list_item.addContextMenuItems(
                [
                    (
                        "Rescrape item",
                        container_update(
                            plugin,
                            func,
                            mode=mode,
                            query=query,
                            ids=f"{id}, {tvdb_id}, {imdb_id}",
                            rescrape=True,
                        ),
                    )
                ]
            )
            addDirectoryItem(
                plugin.handle,
                plugin.url_for(
                    func,
                    mode=mode,
                    query=query,
                    ids=f"{id}, {tvdb_id}, {imdb_id}",
                ),
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
