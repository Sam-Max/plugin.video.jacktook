import os
from resources.lib.api.anilist_api import AniList
from resources.lib.db.database import get_db
from resources.lib.utils.utils import get_cached, set_cached, tmdb_get
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory
from resources.lib.utils.kodi import ADDON_PATH, Keyboard, get_setting, log, notify


anilist_client_id = get_setting("anilist_client_id", "14375")
anilist_client_secret = get_setting(
    "anilist_client_secret", "tOJ5CJA9JM2pmJrHM8XaZgnM9XgL7HaLTM3krdML"
)


def anilist_client():
    return AniList(
        anilist_client_id,
        anilist_client_secret,
    )


def search_anilist(category, page, plugin, func, func2, func3):
    client = anilist_client()

    if category == "search":
        if page == 1:
            text = Keyboard(id=30242)
            if text:
                get_db().set_search_string("text", text)
            else:
                return
        else:
            text = get_db().get_search_string("text")
        message, data = client.search(str(text), page)
    if category == "Trending":
        message, data = search_anilist_api(type="Trending", client=client, page=page)
    elif category == "Popular":
        message, data = search_anilist_api(type="Popular", client=client, page=page)

    if "error" in message:
        notify(message)
        return

    anilist_show_results(
        data,
        func=func,
        func2=func2,
        func3=func3,
        category=category,
        page=page,
        plugin=plugin,
    )


def search_anilist_api(type, client, page):
    cached_results = get_cached(type, params=(page))
    if cached_results:
        log("cached search_anilist_api")
        return "", cached_results

    if type == "Trending":
        message, data = client.get_trending(page=page, perPage=10)
    elif type == "Popular":
        message, data = client.get_popular(page=page, perPage=10)

    set_cached(data, type, params=(page))

    return message, data


def anilist_show_results(results, func, func2, func3, category, page, plugin):
    for res in results["ANIME"]:
        _title = res["title"]
        title = _title.get("english")
        if title is None:
            title = _title.get("romaji")

        format = res["format"]
        if format not in ["TV", "OVA", "MOVIE"]:
            continue

        id = res["id"]
        mal_id = res["idMal"]

        imdb_id = "tt0000000"
        if format == "MOVIE":
            search_res = tmdb_get("search_movie", title)
            if search_res["results"]:
                id = search_res["results"][0].get("id")
                details = tmdb_get("movie_details", id)
                imdb_id = details.external_ids.get("imdb_id")

        description = res["description"]
        coverImage = res["coverImage"]["large"]

        list_item = ListItem(label=f"[B][{format}][/B]-{title}")
        list_item.setArt(
            {
                "poster": coverImage,
                "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
                "fanart": coverImage,
            }
        )
        list_item.setProperty("IsPlayable", "false")

        info_tag = list_item.getVideoInfoTag()
        info_tag.setMediaType("video")
        info_tag.setTitle(title)
        info_tag.setPlot(description)

        if format in ["TV", "OVA"]:
            addDirectoryItem(
                plugin.handle,
                plugin.url_for(func2, query=title, id=id, mal_id=mal_id),
                list_item,
                isFolder=True,
            )
        else:
            addDirectoryItem(
                plugin.handle,
                plugin.url_for(
                    func,
                    mode="movie",
                    query=title,
                    ids=f"{id}, {-1}, {imdb_id}",
                ),
                list_item,
                isFolder=True,
            )

    list_item = ListItem(label="Next")
    list_item.setArt(
        {"icon": os.path.join(ADDON_PATH, "resources", "img", "nextpage.png")}
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(func3, category=category, page=page),
        list_item,
        isFolder=True,
    )

    endOfDirectory(plugin.handle)
