import os
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
from lib.tmdb import TMDB_BACKDROP_URL, TMDB_POSTER_URL
from lib.utils.utils import (
    Enum,
    add_next_button,
    execute_thread_pool,
    set_media_infotag,
    tmdb_get,
)
from lib.utils.kodi_utils import ADDON_PATH, container_update, url_for
from xbmcgui import ListItem
from xbmcplugin import (
    addDirectoryItem,
)
from lib.utils.paginator import paginator_db


class Trakt(Enum):
    TRENDING = "trakt_trending"
    TRENDING_RECENT = "trakt_trending_recent"
    ANIME_TRENDING = "Anime_Trending"
    ANIME_MOST_WATCHED = "Anime_Most_Watched"
    TOP10 = "trakt_top10"
    WATCHED = "trakt_watched"
    FAVORITED = "trakt_favorited"
    RECOMENDATIONS = "trakt_recommendations"
    TRENDING_LISTS = "trakt_trending_lists"
    WATCHLIST = "trakt_watchlist"


def handle_trakt_query(query, category, mode, page):
    if mode == "movies":
        return handle_trakt_movie_query(query, mode, page)
    elif mode == "tv":
        return handle_trakt_tv_query(query, mode, page)
    elif mode == "anime":
        return handle_trakt_anime_query(category, page)


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
    elif query in Trakt.WATCHLIST:
        return trakt_watchlist(mode)


def handle_trakt_anime_query(query, page):
    kodilog("trakt::handle_trakt_anime_query")
    if query == Trakt.ANIME_TRENDING:
        return trakt_anime_trending(page)
    elif query == Trakt.ANIME_MOST_WATCHED:
        return trakt_anime_most_watched(page)


def process_trakt_result(results, query, category, mode, submode, api, page, plugin):
    if (
        query == Trakt.TRENDING
        or query == Trakt.WATCHED
        or query == Trakt.FAVORITED
        or query == Trakt.TOP10
    ):
        execute_thread_pool(results, show_common_categories, mode, plugin)
    elif query == Trakt.RECOMENDATIONS:
        execute_thread_pool(results, show_recommendations, mode, plugin)
    elif query == Trakt.TRENDING_LISTS:
        execute_thread_pool(results, show_trending_lists, mode, plugin)
    elif query == Trakt.WATCHLIST:
        execute_thread_pool(results, show_watchlist, mode, plugin)

    if category == Trakt.ANIME_TRENDING or category == Trakt.ANIME_MOST_WATCHED:
        kodilog("trakt::process_trakt_result")
        execute_thread_pool(results, show_anime_common, submode, plugin)

    add_next_button(
        "next_page_trakt",
        plugin,
        page,
        query=query,
        category=category,
        mode=mode,
        submode=submode,
        api=api,
    )


def show_anime_common(res, mode, plugin):
    kodilog("trakt::show_anime_common")
    kodilog(mode)
    ids = extract_ids(res)
    title = res["show"]["title"]

    tmdb_id = ids.split(",")[0]
    if mode == "tv":
        details = tmdb_get("tv_details", tmdb_id)
    else:
        details = tmdb_get("movie_details", tmdb_id)

    poster_path = TMDB_POSTER_URL + details.poster_path if details.poster_path else ""
    backdrop_path = (
        TMDB_BACKDROP_URL + details.backdrop_path if details.backdrop_path else ""
    )

    list_item = ListItem(title)
    list_item.setArt(
        {
            "poster": poster_path,
            "fanart": backdrop_path,
        }
    )
    list_item.setProperty("IsPlayable", "false")
    overview = details.get("overview", "")

    set_media_infotag(
        list_item,
        mode,
        title,
        overview,
        air_date="",
        duration="",
        ids=ids,
    )

    add_dir_item(mode, list_item, ids, title, plugin)


def show_common_categories(res, mode, plugin):
    if mode == "tv":
        title = res["show"]["title"]
        ids = extract_ids(res, mode)
        tmdb_id = ids.split(",")[0]
        details = tmdb_get("tv_details", tmdb_id)
    else:
        title = res["movie"]["title"]
        ids = extract_ids(res, mode)
        tmdb_id = ids.split(",")[0]
        details = tmdb_get("movie_details", tmdb_id)

    poster_path = TMDB_POSTER_URL + details.get("poster_path", "")
    backdrop_path = TMDB_BACKDROP_URL + details.get("backdrop_path", "")

    list_item = ListItem(label=title)
    list_item.setArt(
        {
            "poster": poster_path,
            "fanart": backdrop_path,
        }
    )
    list_item.setProperty("IsPlayable", "false")

    overview = details.get("overview", "")

    set_media_infotag(
        list_item,
        mode,
        title,
        overview,
        air_date="",
        duration="",
        ids=ids,
    )

    add_dir_item(mode, list_item, ids, title, plugin)


def show_watchlist(res, mode, plugin):
    tmdb_id = res["media_ids"]["tmdb"]
    tvdb_id = -1
    imdb_id = res["media_ids"]["imdb"]
    ids = f"{tmdb_id}, {tvdb_id}, {imdb_id}"
    title = res["title"]

    if mode == "tv":
        details = tmdb_get("tv_details", tmdb_id)
    else:
        details = tmdb_get("movie_details", tmdb_id)

    poster_path = TMDB_POSTER_URL + details.poster_path if details.poster_path else ""
    backdrop_path = (
        TMDB_BACKDROP_URL + details.backdrop_path if details.backdrop_path else ""
    )

    list_item = ListItem(title)
    list_item.setArt(
        {
            "poster": poster_path,
            "fanart": backdrop_path,
        }
    )

    add_dir_item(mode, list_item, ids, title, plugin)


def show_trending_lists(res, mode, plugin):
    list_title = res["list"]["name"]
    list_item = ListItem(list_title)
    description = res["list"]["description"]

    info_labels = {
        "title": list_title,
        "plot": description,
    }
    list_item.setInfo("video", info_labels)

    addDirectoryItem(
        plugin.handle,
        url_for(
            name="/trakt/list/content",
            list_type=res["list"]["type"],
            mode=mode,
            user=res["list"]["user"]["ids"]["slug"],
            slug=res["list"]["ids"]["slug"],
        ),
        list_item,
        isFolder=True,
    )


def show_recommendations(res, mode, plugin):
    title = res["title"]
    tmdb_id = res["ids"]["tmdb"]
    tvdb_id = -1
    imdb_id = res["ids"]["imdb"]
    ids = f"{tmdb_id}, {tvdb_id}, {imdb_id}"

    if mode == "tv":
        details = tmdb_get("tv_details", tmdb_id)
    else:
        details = tmdb_get("movie_details", tmdb_id)

    poster_path = TMDB_POSTER_URL + details.poster_path if details.poster_path else ""
    backdrop_path = (
        TMDB_BACKDROP_URL + details.backdrop_path if details.backdrop_path else ""
    )

    list_item = ListItem(title)
    list_item.setArt(
        {
            "poster": poster_path,
            "fanart": backdrop_path,
            "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
        }
    )

    set_media_infotag(
        list_item,
        mode,
        title,
        overview="",
        air_date="",
        duration="",
        ids=ids,
    )

    list_item.setProperty("IsPlayable", "false")

    add_dir_item(mode, list_item, ids, title, plugin)


def show_lists_content_items(res, plugin):
    tmdb_id = res["media_ids"]["tmdb"]
    tvdb_id = -1
    imdb_id = res["media_ids"]["imdb"]
    ids = f"{tmdb_id}, {tvdb_id}, {imdb_id}"
    title = res["title"]

    if res["type"] == "show":
        mode = "tv"
        details = tmdb_get("tv_details", tmdb_id)
    else:
        mode = "movies"
        details = tmdb_get("movie_details", tmdb_id)

    poster_path = TMDB_POSTER_URL + details.poster_path if details.poster_path else ""
    backdrop_path = (
        TMDB_BACKDROP_URL + details.backdrop_path if details.backdrop_path else ""
    )

    list_item = ListItem(title)
    list_item.setArt(
        {
            "poster": poster_path,
            "fanart": backdrop_path,
        }
    )

    list_item.setProperty("IsPlayable", "false")

    set_media_infotag(
        list_item,
        mode,
        title,
        overview=details.overview,
        air_date="",
        duration="",
        ids=ids,
    )

    if res["type"] == "show":
        addDirectoryItem(
            plugin.handle,
            url_for(
                name="tv/details",
                ids=ids,
                mode="tv",
            ),
            list_item,
            isFolder=True,
        )
    else:
        addDirectoryItem(
            plugin.handle,
            url_for(
                name="search",
                query=title,
                mode="movies",
                ids=ids,
            ),
            list_item,
            isFolder=True,
        )


def show_trakt_list_content(list_type, mode, user, slug, with_auth, page, plugin):
    data = get_trakt_list_contents(list_type, user, slug, with_auth)
    paginator_db.initialize(data)
    items = paginator_db.get_page(page)
    execute_thread_pool(items, show_lists_content_items, plugin)
    add_next_button("/trakt/paginator", plugin, page, mode=mode)


def show_trakt_list_page(page, mode, plugin):
    items = paginator_db.get_page(page)
    execute_thread_pool(items, show_lists_content_items, plugin)
    add_next_button("/trakt/paginator", plugin, page, mode=mode)


def extract_ids(res, mode="tv"):
    if mode == "tv":
        tmdb_id = res["show"]["ids"]["tmdb"]
        tvdb_id = res["show"]["ids"]["tvdb"]
        imdb_id = res["show"]["ids"]["imdb"]
    else:
        tmdb_id = res["movie"]["ids"]["tmdb"]
        tvdb_id = -1
        imdb_id = res["movie"]["ids"]["imdb"]

    return f"{tmdb_id}, {tvdb_id}, {imdb_id}"


def add_dir_item(mode, list_item, ids, title, plugin):
    if mode == "tv":
        addDirectoryItem(
            plugin.handle,
            url_for(
                name="tv/details",
                ids=ids,
                mode="tv",
            ),
            list_item,
            isFolder=True,
        )
    else:
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
                query=title,
                mode="movies",
                ids=ids,
            ),
            list_item,
            isFolder=False,
        )
