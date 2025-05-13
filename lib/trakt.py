import json
from lib.api.jacktook.kodi import kodilog
from lib.api.trakt.trakt_api import TraktAPI, TraktLists, TraktMovies, TraktTV
from lib.utils.tmdb_utils import tmdb_get
from lib.utils.utils import (
    Anime,
    Enum,
    add_next_button,
    execute_thread_pool,
    set_content_type,
    set_media_infoTag,
)
from lib.utils.kodi_utils import ADDON_HANDLE, build_url, notification, play_media
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory
from lib.utils.paginator import paginator_db


class Trakt(Enum):
    TRENDING = "trakt_trending"
    TRENDING_RECENT = "trakt_trending_recent"
    TOP10 = "trakt_top10"
    WATCHED = "trakt_watched"
    FAVORITED = "trakt_favorited"
    RECOMENDATIONS = "trakt_recommendations"
    TRENDING_LISTS = "trakt_trending_lists"
    POPULAR_LISTS = "trakt_popular_lists"
    WATCHED_HISTORY = "trakt_watched_history"
    WATCHLIST = "trakt_watchlist"


def handle_trakt_query(query, category, mode, page, submode, api):
    set_content_type(mode)
    handlers = {
        "movies": handle_trakt_movie_query,
        "tv": handle_trakt_tv_query,
        "anime": lambda q, m, p: handle_trakt_anime_query(category, p),
    }
    handler = handlers.get(mode)
    if handler:
        return handler(query, mode, page)


def handle_trakt_movie_query(query, mode, page):
    query_handlers = {
        Trakt.TRENDING: lambda: TraktMovies().trakt_movies_trending(page),
        Trakt.TOP10: lambda: TraktMovies().trakt_movies_top10_boxoffice(),
        Trakt.WATCHED: lambda: TraktMovies().trakt_movies_most_watched(page),
        Trakt.WATCHED_HISTORY: lambda: TraktLists().get_watched_history(mode, page),
        Trakt.FAVORITED: lambda: TraktMovies().trakt_movies_most_favorited(page),
        Trakt.RECOMENDATIONS: lambda: TraktMovies().trakt_recommendations("movies"),
    }

    list_handlers = {
        Trakt.TRENDING_LISTS: lambda: TraktLists().trakt_trending_popular_lists(
            list_type="trending", page_no=page
        ),
        Trakt.POPULAR_LISTS: lambda: TraktLists().trakt_trending_popular_lists(
            list_type="popular", page_no=page
        ),
        Trakt.WATCHLIST: lambda: TraktLists().trakt_watchlist(mode),
    }

    if query in query_handlers:
        return query_handlers[query]()
    elif query in list_handlers:
        return list_handlers[query]()


def handle_trakt_tv_query(query, mode, page):
    query_handlers = {
        Trakt.TRENDING: lambda: TraktTV().trakt_tv_trending(page),
        Trakt.WATCHED: lambda: TraktTV().trakt_tv_most_watched(page),
        Trakt.WATCHED_HISTORY: lambda: TraktLists().get_watched_history(mode, page),
        Trakt.FAVORITED: lambda: TraktTV().trakt_tv_most_favorited(page),
        Trakt.RECOMENDATIONS: lambda: TraktTV().trakt_recommendations("shows"),
    }

    list_handlers = {
        Trakt.TRENDING_LISTS: lambda: TraktLists().trakt_trending_popular_lists(
            list_type="trending", page_no=page
        ),
        Trakt.POPULAR_LISTS: lambda: TraktLists().trakt_trending_popular_lists(
            list_type="popular", page_no=page
        ),
        Trakt.WATCHLIST: lambda: TraktLists().trakt_watchlist(mode),
    }

    if query in query_handlers:
        return query_handlers[query]()
    elif query in list_handlers:
        return list_handlers[query]()


def handle_trakt_anime_query(query, page):
    if query == Anime.TRENDING:
        return TraktAPI().anime.trakt_anime_trending(page)
    elif query == Anime.MOST_WATCHED:
        return TraktAPI().anime.trakt_anime_most_watched(page)


def trakt_add_to_watchlist(params):
    media_type = params.get("media_type")
    ids = json.loads(params.get("ids", "{}"))
    try:
        TraktAPI().lists.add_to_watchlist(media_type, ids)
    except Exception as e:
        kodilog(f"Error adding to Trakt watchlist: {e}")
        notification("Failed to add to Trakt watchlist", time=3000)


def trakt_remove_from_watchlist(params):
    media_type = params.get("media_type")
    ids = json.loads(params.get("ids", "{}"))
    try:
        TraktAPI().lists.remove_from_watchlist(media_type, ids)
    except Exception as e:
        kodilog(f"Error removing from Trakt watchlist: {e}")
        notification("Failed to remove from Trakt watchlist", time=3000)


def process_trakt_result(results, query, category, mode, submode, api, page):
    query_handlers = {
        Trakt.TRENDING: lambda: execute_thread_pool(
            results, show_common_categories, mode
        ),
        Trakt.WATCHED: lambda: execute_thread_pool(
            results, show_common_categories, mode
        ),
        Trakt.FAVORITED: lambda: execute_thread_pool(
            results, show_common_categories, mode
        ),
        Trakt.TOP10: lambda: execute_thread_pool(results, show_common_categories, mode),
        Trakt.RECOMENDATIONS: lambda: execute_thread_pool(
            results, show_recommendations, mode
        ),
        Trakt.TRENDING_LISTS: lambda: execute_thread_pool(
            results, show_trending_lists, mode
        ),
        Trakt.POPULAR_LISTS: lambda: execute_thread_pool(
            results, show_trending_lists, mode
        ),
        Trakt.WATCHLIST: lambda: execute_thread_pool(results, show_watchlist, mode),
        Trakt.WATCHED_HISTORY: lambda: execute_thread_pool(
            results, show_watched_history_content_items
        ),
    }

    anime_handlers = {
        Anime.TRENDING: lambda: execute_thread_pool(
            results, show_anime_common, submode
        ),
        Anime.MOST_WATCHED: lambda: execute_thread_pool(
            results, show_anime_common, submode
        ),
    }

    if query in query_handlers:
        query_handlers[query]()
    if category in anime_handlers:
        anime_handlers[category]()

    add_next_button(
        "search_item",
        page=page,
        query=query,
        category=category,
        mode=mode,
        submode=submode,
        api=api,
    )
    endOfDirectory(ADDON_HANDLE)


def show_anime_common(res, mode):
    ids = extract_ids(res)
    title = res["show"]["title"]

    tmdb_id = ids["tmdb_id"]
    if mode == "tv":
        details = tmdb_get("tv_details", tmdb_id)
    else:
        details = tmdb_get("movie_details", tmdb_id)

    list_item = ListItem(title)

    set_media_infoTag(list_item, metadata=details)

    add_dir_item(mode, list_item, ids, title)


def show_common_categories(res, mode):
    if mode == "tv":
        title = res["show"]["title"]
        ids = extract_ids(res, mode)
        tmdb_id = ids["tmdb_id"]
        details = tmdb_get("tv_details", tmdb_id)
    else:
        title = res["movie"]["title"]
        ids = extract_ids(res, mode)
        tmdb_id = ids["tmdb_id"]
        details = tmdb_get("movie_details", tmdb_id)

    list_item = ListItem(label=title)

    set_media_infoTag(list_item, metadata=details)

    add_dir_item(mode, list_item, ids, title)


def show_watchlist(res, mode):
    title = res["title"]
    tmdb_id = res["media_ids"]["tmdb"]
    imdb_id = res["media_ids"]["imdb"]

    ids = {"tmdb_id": tmdb_id, "tvdb_id": None, "imdb_id": imdb_id}

    if mode == "tv":
        details = tmdb_get("tv_details", tmdb_id)
    else:
        details = tmdb_get("movie_details", tmdb_id)

    list_item = ListItem(title)

    set_media_infoTag(list_item, metadata=details)

    add_dir_item(mode, list_item, ids, title)


def show_trending_lists(res, mode):
    list_title = res["list"]["name"]
    list_item = ListItem(list_title)
    description = res["list"]["description"]

    info_labels = {
        "title": list_title,
        "plot": description,
    }
    list_item.setInfo("video", info_labels)

    addDirectoryItem(
        ADDON_HANDLE,
        build_url(
            "trakt_list_content",
            list_type=res["list"]["type"],
            mode=mode,
            user=res["list"]["user"]["ids"]["slug"],
            slug=res["list"]["ids"]["slug"],
        ),
        list_item,
        isFolder=True,
    )


def show_recommendations(res, mode):
    title = res["title"]
    tmdb_id = res["ids"]["tmdb"]
    imdb_id = res["ids"]["imdb"]
    ids = {"tmdb_id": tmdb_id, "tvdb_id": None, "imdb_id": imdb_id}

    if mode == "tv":
        details = tmdb_get("tv_details", tmdb_id)
    else:
        details = tmdb_get("movie_details", tmdb_id)

    list_item = ListItem(title)

    set_media_infoTag(list_item, metadata=details)

    add_dir_item(mode, list_item, ids, title)


def show_watched_history_content_items(res):
    tmdb_id = res["media_ids"]["tmdb"]
    imdb_id = res["media_ids"]["imdb"]
    ids = {"tmdb_id": tmdb_id, "tvdb_id": None, "imdb_id": imdb_id}
    title = res["title"]

    if res["type"] == "show":
        mode = "tv"
        details = tmdb_get("tv_details", tmdb_id)
    else:
        mode = "movies"
        details = tmdb_get("movie_details", tmdb_id)

    list_item = ListItem(title)

    set_media_infoTag(list_item, metadata=details, mode=mode)

    if res["type"] == "show":
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "search",
                ids=ids,
                mode=mode,
                query=res["show_title"],
                tv_data={
                    "name": res["ep_title"],
                    "episode": res["episode"],
                    "season": res["season"],
                },
            ),
            list_item,
            isFolder=True,
        )
    else:
        list_item.setProperty("IsPlayable", "true")
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "search",
                query=title,
                mode=mode,
                ids=ids,
            ),
            list_item,
            isFolder=False,
        )


def show_lists_content_items(res):
    tmdb_id = res["media_ids"]["tmdb"]
    imdb_id = res["media_ids"]["imdb"]
    ids = {"tmdb_id": tmdb_id, "tvdb_id": None, "imdb_id": imdb_id}
    title = res["title"]

    if res["type"] == "show":
        mode = "tv"
        details = tmdb_get("tv_details", tmdb_id)
    else:
        mode = "movies"
        details = tmdb_get("movie_details", tmdb_id)

    list_item = ListItem(title)

    set_media_infoTag(list_item, metadata=details, mode=mode)

    if res["type"] == "show":
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "tv_seasons_details",
                ids=ids,
                mode="tv",
            ),
            list_item,
            isFolder=True,
        )
    else:
        list_item.setProperty("IsPlayable", "true")
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "search",
                query=title,
                mode="movies",
                ids=ids,
            ),
            list_item,
            isFolder=False,
        )


def show_trakt_list_content(list_type, mode, user, slug, with_auth, page):
    data = TraktAPI().lists.get_trakt_list_contents(list_type, user, slug, with_auth)
    paginator_db.initialize(data)
    items = paginator_db.get_page(page)
    execute_thread_pool(items, show_lists_content_items)
    add_next_button("list_trakt_page", page, mode=mode)
    endOfDirectory(ADDON_HANDLE)


def show_list_trakt_page(page, mode):
    items = paginator_db.get_page(page)
    execute_thread_pool(items, show_lists_content_items)
    add_next_button("list_trakt_page", page, mode=mode)
    endOfDirectory(ADDON_HANDLE)


def extract_ids(res, mode="tv"):
    if mode == "tv":
        tmdb_id = res["show"]["ids"]["tmdb"]
        tvdb_id = res["show"]["ids"]["tvdb"]
        imdb_id = res["show"]["ids"]["imdb"]
    else:
        tmdb_id = res["movie"]["ids"]["tmdb"]
        tvdb_id = None
        imdb_id = res["movie"]["ids"]["imdb"]

    return {"tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id}


def add_dir_item(mode, list_item, ids, title):
    if mode == "tv":
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "tv_seasons_details",
                ids=ids,
                mode="tv",
            ),
            list_item,
            isFolder=True,
        )
    else:
        list_item.setProperty("IsPlayable", "true")
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
                query=title,
                mode="movies",
                ids=ids,
            ),
            list_item,
            isFolder=False,
        )
