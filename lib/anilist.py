import os

from lib.db.anime_db import get_all_ids
from lib.anizip import search_anizip_episodes
from lib.api.anilist_api import anilist_client
from lib.simkl import search_simkl_episodes
from lib.utils.general_utils import (
    get_cached,
    get_fanart,
    set_cached,
    set_video_info,
    set_video_infotag,
)
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory
from lib.db.pickle_db import pickle_db
from lib.utils.kodi_utils import (
    ADDON_PATH,
    Keyboard,
    get_kodi_version,
    url_for,
    url_for_path,
)


def search_anilist(category, page, plugin):
    client = anilist_client()
    if category == "search":
        if page == 1:
            text = Keyboard(id=30242)
            if text:
                pickle_db.set_search_string("query", text)
            else:
                return
        else:
            text = pickle_db.get_search_string("query")
        data = client.search(str(text), page)
    if category == "Trending":
        data = search_anilist_api(type="Trending", client=client, page=page)
    elif category == "Popular":
        data = search_anilist_api(type="Popular", client=client, page=page)

    anilist_show_results(
        data,
        category=category,
        page=page,
        plugin=plugin,
    )


def search_anilist_api(type, client, page):
    cached_results = get_cached(type, params=(page))
    if cached_results:
        return cached_results

    if type == "Trending":
        data = client.get_trending(page=page, perPage=10)
    elif type == "Popular":
        data = client.get_popular(page=page, perPage=10)

    set_cached(data, type, params=(page))
    return data


def anilist_show_results(results, category, page, plugin):
    for res in results["ANIME"]:
        _title = res["title"]
        title = _title.get("english", "")
        if not title:
            title = _title.get("romaji")

        format = res["format"]
        if format not in ["TV", "MOVIE"]:
            continue

        if format in ["TV", "OVA"]:
            mode = "tv"
        else:
            mode = "movie"

        description = res.get("description", "")
        anilist_id = res["id"]
        mal_id = res["idMal"]

        ids = get_all_ids(anilist_id)
        imdb_id = ids.get("imdb", -1)
        tvdb_id = ids.get("tvdb", -1)
        tmdb_id = ids.get("tmdb", -1)

        data = get_fanart(tvdb_id)
        if data:
            poster = data["poster"]
            fanart = data["fanart"]
        else:
            fanart = poster = res["coverImage"]["large"]

        list_item = ListItem(label=f"[B][{format}][/B]-{title}")
        list_item.setArt(
            {
                "poster": poster,
                "fanart": fanart,
                "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
            }
        )
        list_item.setProperty("IsPlayable", "false")

        if get_kodi_version() >= 20:
            set_video_infotag(
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

        if format in ["TV", "OVA"]:
            addDirectoryItem(
                plugin.handle,
                url_for_path(
                    name="anilist/episodes", path=f"{title}/{anilist_id}/{mal_id}"
                ),
                list_item,
                isFolder=True,
            )
        else:
            addDirectoryItem(
                plugin.handle,
                url_for(
                    name="search",
                    mode="movie",
                    query=title,
                    ids=f"{tmdb_id}, {tvdb_id}, {imdb_id}",
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
        url_for_path(name="anilist/next_page", path=f"{category}/{page}"),
        list_item,
        isFolder=True,
    )

    endOfDirectory(plugin.handle)


def search_episodes(query, anilist_id, mal_id, plugin, symkl=False):
    if symkl:
        search_simkl_episodes(query, anilist_id, mal_id, plugin)
    else:
        search_anizip_episodes(query, anilist_id, plugin)
