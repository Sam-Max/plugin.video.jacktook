import os
from lib.api.jacktook.kodi import kodilog
from lib.db.anime_db import get_all_ids
from lib.utils.anizip_utils import search_anizip_episodes
from lib.clients.anilist import anilist_client
from lib.utils.simkl_utils import search_simkl_episodes
from lib.utils.utils import (
    add_next_button,
    get_cached,
    get_fanart_details,
    set_cached,
    set_media_infotag,
)
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem
from lib.db.main_db import main_db
from lib.utils.kodi_utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    build_url,
    show_keyboard,
)


def search_anilist(category, page, plugin):
    client = anilist_client()
    if category == "SearchAnime":
        if page == 1:
            text = show_keyboard(id=30242)
            if not text:
                return
            main_db.set_query("query", text)
        else:
            text = main_db.get_query("query")
        data = client.search(str(text), page)
    elif category == "Trending":
        data = search_anilist_api(type="Trending", client=client, page=page)
    elif category == "Popular":
        data = search_anilist_api(type="Popular", client=client, page=page)

    kodilog(category)

    anilist_show_results(
        data,
        category,
        page,
        plugin,
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
            mode = "movies"

        description = res.get("description", "")
        anilist_id = res["id"]
        mal_id = res["idMal"]

        ids = get_all_ids(anilist_id)
        imdb_id = ids.get("imdb", -1)
        tvdb_id = ids.get("tvdb", -1)
        tmdb_id = ids.get("tmdb", -1)

        data = get_fanart_details(tvdb_id=tvdb_id, mode=mode)
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

        set_media_infotag(
            list_item,
            mode,
            title,
            description,
        )

        if format in ["TV", "OVA"]:
            addDirectoryItem(
                ADDON_HANDLE,
                build_url("anilist/episodes", path=f"{title}/{anilist_id}/{mal_id}"),
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
                    ids=f"{tmdb_id}, {tvdb_id}, {imdb_id}",
                ),
                list_item,
                isFolder=True,
            )

    add_next_button("/anilist_next_page", plugin, page, category=category)


def search_episodes(query, anilist_id, mal_id, plugin, symkl=False):
    if symkl:
        search_simkl_episodes(query, anilist_id, mal_id, plugin)
    else:
        search_anizip_episodes(query, anilist_id, plugin)
