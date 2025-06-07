import json
from lib.clients.tmdb.utils import tmdb_get
from lib.api.trakt.trakt import TraktAPI, TraktLists, TraktMovies, TraktTV
from lib.api.trakt.trakt_utils import (
    add_trakt_watched_context_menu,
    add_trakt_watchlist_context_menu,
    is_trakt_auth,
)
from lib.clients.trakt.utils import add_kodi_dir_item, extract_ids
from lib.utils.general.utils import (
    Anime,
    Enum,
    add_next_button,
    execute_thread_pool,
    set_content_type,
    set_media_infoTag,
)
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    build_url,
    kodilog,
    notification,
    play_media,
)
from .paginator import paginator_db

from xbmcplugin import endOfDirectory
from xbmcgui import ListItem


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


class BaseTraktClient:
    @staticmethod
    def _add_media_directory_item(list_item, mode, title, ids, media_type=None):
        if mode == "movies":
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
                    ),
                ]
                + (
                    add_trakt_watchlist_context_menu("movies", ids)
                    + add_trakt_watched_context_menu("movies", ids=ids)
                    if is_trakt_auth()
                    else []
                )
            )
            add_kodi_dir_item(
                list_item=list_item,
                url=build_url(
                    "search",
                    mode=mode,
                    query=title,
                    ids=ids,
                ),
                is_folder=False,
                is_playable=True,
            )
        else:
            if is_trakt_auth():
                list_item.addContextMenuItems(
                    add_trakt_watchlist_context_menu("shows", ids)
                    + add_trakt_watched_context_menu("shows", ids=ids)
                )
            add_kodi_dir_item(
                list_item=list_item,
                url=build_url(
                    "tv_seasons_details",
                    ids=ids,
                    mode=mode,
                    media_type=media_type,
                ),
                is_folder=True,
            )


class TraktClient:
    @staticmethod
    def handle_trakt_query(query, category, mode, page, submode, api):
        set_content_type(mode)
        handlers = {
            "movies": TraktClient.handle_trakt_movie_query,
            "tv": TraktClient.handle_trakt_show_query,
            "anime": lambda q, m, p: TraktClient.handle_trakt_anime_query(category, p),
        }
        handler = handlers.get(mode)
        if handler:
            return handler(query, mode, page)

    @staticmethod
    def handle_trakt_movie_query(query, mode, page):
        query_handlers = {
            Trakt.TRENDING: lambda: TraktMovies().trakt_movies_trending(page),
            Trakt.TOP10: lambda: TraktMovies().trakt_movies_top10_boxoffice(),
            Trakt.WATCHED: lambda: TraktMovies().trakt_movies_most_watched(page),
            Trakt.WATCHED_HISTORY: lambda: TraktLists().trakt_watched_history(
                mode, page
            ),
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

    @staticmethod
    def handle_trakt_show_query(query, mode, page):
        query_handlers = {
            Trakt.TRENDING: lambda: TraktTV().trakt_tv_trending(page),
            Trakt.WATCHED: lambda: TraktTV().trakt_tv_most_watched(page),
            Trakt.WATCHED_HISTORY: lambda: TraktLists().trakt_watched_history(
                mode, page
            ),
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

    @staticmethod
    def handle_trakt_anime_query(query, page):
        if query == Anime.TRENDING:
            return TraktAPI().anime.trakt_anime_trending(page)
        elif query == Anime.MOST_WATCHED:
            return TraktAPI().anime.trakt_anime_most_watched(page)

    @staticmethod
    def trakt_add_to_watchlist(params):
        media_type = params.get("media_type")
        ids = json.loads(params.get("ids", "{}"))
        try:
            TraktAPI().lists.add_to_watchlist(media_type, ids)
            notification("Added to Trakt watchlist", time=3000)
        except Exception as e:
            kodilog(f"Error adding to Trakt watchlist: {e}")
            notification("Failed to add to Trakt watchlist", time=3000)

    @staticmethod
    def trakt_remove_from_watchlist(params):
        media_type = params.get("media_type")
        ids = json.loads(params.get("ids", "{}"))
        try:
            TraktAPI().lists.remove_from_watchlist(media_type, ids)
            notification("Removed from Trakt watchlist", time=3000)
        except Exception as e:
            kodilog(f"Error removing from Trakt watchlist: {e}")
            notification("Failed to remove from Trakt watchlist", time=3000)

    @staticmethod
    def trakt_mark_as_watched(params):
        media_type = params.get("media_type")
        season = json.loads(params.get("season"))
        episode = json.loads(params.get("episode"))
        ids = json.loads(params.get("ids", "{}"))
        try:
            TraktAPI().lists.mark_as_watched(media_type, season, episode, ids)
        except Exception as e:
            kodilog(f"Error marking as watched on Trakt: {e}")
            notification("Failed to mark as watched on Trakt", time=3000)

    @staticmethod
    def trakt_mark_as_unwatched(params):
        media_type = params.get("media_type")
        season = json.loads(params.get("season"))
        episode = json.loads(params.get("episode"))
        ids = json.loads(params.get("ids", "{}"))
        try:
            TraktAPI().lists.mark_as_unwatched(media_type, season, episode, ids)
            notification("Marked as unwatched on Trakt", time=3000)
        except Exception as e:
            kodilog(f"Error marking as unwatched on Trakt: {e}")
            notification("Failed to mark as unwatched on Trakt", time=3000)

    @staticmethod
    def process_trakt_result(results, query, category, mode, submode, api, page):
        query_handlers = {
            Trakt.TRENDING: lambda: execute_thread_pool(
                results, TraktPresentation.show_common_categories, mode
            ),
            Trakt.WATCHED: lambda: execute_thread_pool(
                results, TraktPresentation.show_common_categories, mode
            ),
            Trakt.FAVORITED: lambda: execute_thread_pool(
                results, TraktPresentation.show_common_categories, mode
            ),
            Trakt.TOP10: lambda: execute_thread_pool(
                results, TraktPresentation.show_common_categories, mode
            ),
            Trakt.RECOMENDATIONS: lambda: execute_thread_pool(
                results, TraktPresentation.show_recommendations, mode
            ),
            Trakt.TRENDING_LISTS: lambda: execute_thread_pool(
                results, TraktPresentation.show_trending_lists, mode
            ),
            Trakt.POPULAR_LISTS: lambda: execute_thread_pool(
                results, TraktPresentation.show_trending_lists, mode
            ),
            Trakt.WATCHLIST: lambda: execute_thread_pool(
                results, TraktPresentation.show_watchlist, mode
            ),
            Trakt.WATCHED_HISTORY: lambda: execute_thread_pool(
                results, TraktPresentation.show_watched_history
            ),
        }

        anime_handlers = {
            Anime.TRENDING: lambda: execute_thread_pool(
                results, TraktPresentation.show_anime_common, submode
            ),
            Anime.MOST_WATCHED: lambda: execute_thread_pool(
                results, TraktPresentation.show_anime_common, submode
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

    @staticmethod
    def show_trakt_list_content(list_type, mode, user, slug, with_auth, page):
        data = TraktAPI().lists.get_trakt_list_contents(
            list_type, user, slug, with_auth
        )
        paginator_db.initialize(data)
        items = paginator_db.get_page(page)
        execute_thread_pool(items, TraktPresentation.show_lists_content_items)
        add_next_button("list_trakt_page", page, mode=mode)
        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def show_list_trakt_page(page, mode):
        items = paginator_db.get_page(page)
        execute_thread_pool(items, TraktPresentation.show_lists_content_items)
        add_next_button("list_trakt_page", page, mode=mode)
        endOfDirectory(ADDON_HANDLE)


class TraktPresentation:
    @staticmethod
    def show_anime_common(res, mode):
        ids = extract_ids(res)
        title = res["show"]["title"]

        tmdb_id = ids["tmdb_id"]
        if mode == "tv":
            details = tmdb_get("tv_details", tmdb_id)
        else:
            details = tmdb_get("movie_details", tmdb_id)

        list_item = ListItem(label=title)
        set_media_infoTag(list_item, metadata=details, mode=mode)

        BaseTraktClient._add_media_directory_item(
            list_item=list_item,
            mode=mode,
            title=title,
            ids=ids,
            media_type=res.get("media_type"),
        )

    @staticmethod
    def show_common_categories(res, mode):
        kodilog(f"Processing common categories for mode: {mode}")
        kodilog(f"Result: {res}")

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
        set_media_infoTag(list_item, metadata=details, mode=mode)

        BaseTraktClient._add_media_directory_item(
            list_item=list_item,
            mode=mode,
            title=title,
            ids=ids,
            media_type=res.get("media_type"),
        )

    @staticmethod
    def show_watchlist(res, mode):
        title = res["title"]
        tmdb_id = res["media_ids"]["tmdb"]
        imdb_id = res["media_ids"]["imdb"]

        ids = {"tmdb_id": tmdb_id, "tvdb_id": "", "imdb_id": imdb_id}

        if mode == "tv":
            details = tmdb_get("tv_details", tmdb_id)
        else:
            details = tmdb_get("movie_details", tmdb_id)

        list_item = ListItem(label=title)
        set_media_infoTag(list_item, metadata=details, mode=mode)

        BaseTraktClient._add_media_directory_item(
            list_item=list_item,
            mode=mode,
            title=title,
            ids=ids,
            media_type=res.get("media_type"),
        )

    @staticmethod
    def show_trending_lists(res, mode):
        list_title = res["list"]["name"]
        description = res["list"]["description"]

        info_labels = {
            "title": list_title,
            "plot": description,
        }

        url = build_url(
            "trakt_list_content",
            list_type=res["list"]["type"],
            mode=mode,
            user=res["list"]["user"]["ids"]["slug"],
            slug=res["list"]["ids"]["slug"],
        )

        list_item = ListItem(list_title)
        list_item.setInfo("video", info_labels)

        add_kodi_dir_item(
            list_item,
            url=url,
            is_folder=True,
        )

    @staticmethod
    def show_recommendations(res, mode):
        title = res["title"]
        tmdb_id = res["ids"]["tmdb"]
        imdb_id = res["ids"]["imdb"]
        ids = {"tmdb_id": tmdb_id, "tvdb_id": "", "imdb_id": imdb_id}

        if mode == "tv":
            details = tmdb_get("tv_details", tmdb_id)
        else:
            details = tmdb_get("movie_details", tmdb_id)

        list_item = ListItem(label=title)
        set_media_infoTag(list_item, metadata=details, mode=mode)

        BaseTraktClient._add_media_directory_item(
            list_item=list_item,
            mode=mode,
            title=title,
            ids=ids,
            media_type=res.get("media_type"),
        )

    @staticmethod
    def show_watched_history(res):
        tmdb_id = res["media_ids"]["tmdb"]
        imdb_id = res["media_ids"]["imdb"]
        ids = {"tmdb_id": tmdb_id, "tvdb_id": "", "imdb_id": imdb_id}
        title = res["title"]

        if res["type"] == "show":
            mode = "tv"
            details = tmdb_get("tv_details", tmdb_id)
            url = build_url(
                "search",
                ids=ids,
                mode=mode,
                query=res["show_title"],
                tv_data={
                    "name": res["ep_title"],
                    "episode": res["episode"],
                    "season": res["season"],
                },
            )
            is_folder = True
            is_playable = False
        else:
            mode = "movies"
            details = tmdb_get("movie_details", tmdb_id)
            url = build_url(
                "search",
                query=title,
                mode=mode,
                ids=ids,
            )
            is_folder = False
            is_playable = True

        list_item = ListItem(title)
        set_media_infoTag(list_item, metadata=details, mode=mode)

        add_kodi_dir_item(
            list_item,
            url=url,
            is_folder=is_folder,
            is_playable=is_playable,
        )

    @staticmethod
    def show_lists_content_items(res):
        tmdb_id = res["media_ids"]["tmdb"]
        imdb_id = res["media_ids"]["imdb"]
        ids = {"tmdb_id": tmdb_id, "tvdb_id": "", "imdb_id": imdb_id}
        title = res["title"]

        if res["type"] == "show":
            mode = "tv"
            details = tmdb_get("tv_details", tmdb_id)
        else:
            mode = "movies"
            details = tmdb_get("movie_details", tmdb_id)

        list_item = ListItem(label=title)
        set_media_infoTag(list_item, metadata=details, mode=mode)

        BaseTraktClient._add_media_directory_item(
            list_item=list_item,
            mode=mode,
            title=title,
            ids=ids,
            media_type=res.get("media_type"),
        )
