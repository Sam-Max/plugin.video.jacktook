from lib.api.jacktook.kodi import kodilog
from lib.api.trakt.trakt_api import (
    get_trakt_list_contents,
    trakt_anime_most_watched,
    trakt_anime_trending,
    trakt_movies_most_favorited,
    trakt_movies_most_watched,
    trakt_movies_top10_boxoffice,
    trakt_movies_trending,
    trakt_recommendations,
    trakt_trending_popular_lists,
    trakt_tv_most_favorited,
    trakt_tv_most_watched,
    trakt_tv_trending,
    trakt_watchlist,
)
from lib.utils.tmdb_utils import tmdb_get
from lib.utils.utils import (
    Anime,
    Enum,
    add_next_button,
    execute_thread_pool,
    set_content_type,
    set_media_infoTag,
)
from lib.utils.kodi_utils import ADDON_HANDLE, build_url, play_media
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
    WATCHLIST = "trakt_watchlist"


def handle_trakt_query(query, category, mode, page, submode, api):
    set_content_type(mode)
    if mode == "movies":
        result = handle_trakt_movie_query(query, mode, page)
    elif mode == "tv":
        result = handle_trakt_tv_query(query, mode, page)
    elif mode == "anime":
        result = handle_trakt_anime_query(category, page)
    if result:
        process_trakt_result(result, query, category, mode, submode, api, page)


def handle_trakt_movie_query(query, mode, page):
    if query == Trakt.TRENDING:
        return trakt_movies_trending(page)
    elif query == Trakt.TOP10:
        return trakt_movies_top10_boxoffice()
    elif query == Trakt.WATCHED:
        return trakt_movies_most_watched(page)
    elif query == Trakt.FAVORITED:
        return trakt_movies_most_favorited(page)
    elif query == Trakt.RECOMENDATIONS:
        return trakt_recommendations("movies")
    elif query in Trakt.TRENDING_LISTS:
        return trakt_trending_popular_lists(list_type="trending", page_no=page)
    elif query in Trakt.POPULAR_LISTS:
        return trakt_trending_popular_lists(list_type="popular", page_no=page)
    elif query in Trakt.WATCHLIST:
        return trakt_watchlist(mode)


def handle_trakt_tv_query(query, mode, page):
    if query == Trakt.TRENDING:
        return trakt_tv_trending(page)
    elif query == Trakt.WATCHED:
        return trakt_tv_most_watched(page)
    elif query == Trakt.FAVORITED:
        return trakt_tv_most_favorited(page)
    elif query == Trakt.RECOMENDATIONS:
        return trakt_recommendations("shows")
    elif query in Trakt.TRENDING_LISTS:
        return trakt_trending_popular_lists(list_type="trending", page_no=page)
    elif query in Trakt.POPULAR_LISTS:
        return trakt_trending_popular_lists(list_type="popular", page_no=page)
    elif query in Trakt.WATCHLIST:
        return trakt_watchlist(mode)


def handle_trakt_anime_query(query, page):
    kodilog("trakt::handle_trakt_anime_query")
    if query == Anime.TRENDING:
        return trakt_anime_trending(page)
    elif query == Anime.MOST_WATCHED:
        return trakt_anime_most_watched(page)


def process_trakt_result(results, query, category, mode, submode, api, page):
    kodilog("trakt::process_trakt_result")
    if (
        query == Trakt.TRENDING
        or query == Trakt.WATCHED
        or query == Trakt.FAVORITED
        or query == Trakt.TOP10
    ):
        execute_thread_pool(results, show_common_categories, mode)
    elif query == Trakt.RECOMENDATIONS:
        execute_thread_pool(results, show_recommendations, mode)
    elif query == Trakt.TRENDING_LISTS or query == Trakt.POPULAR_LISTS:
        execute_thread_pool(results, show_trending_lists, mode)
    elif query == Trakt.WATCHLIST:
        execute_thread_pool(results, show_watchlist, mode)

    if category == Anime.TRENDING or category == Anime.MOST_WATCHED:
        execute_thread_pool(results, show_anime_common, submode)

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
    data = get_trakt_list_contents(list_type, user, slug, with_auth)
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
