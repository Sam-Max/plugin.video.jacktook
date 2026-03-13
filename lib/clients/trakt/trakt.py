import json
from datetime import timedelta
from lib.clients.tmdb.utils.utils import tmdb_get
from lib.api.trakt.trakt import TraktAPI, TraktLists, TraktMovies, TraktTV
from lib.api.trakt.trakt_utils import (
    add_trakt_custom_list_context_menu,
    add_trakt_watched_context_menu,
    add_trakt_watchlist_context_menu,
    is_trakt_auth,
)
from lib.clients.trakt.utils import add_kodi_dir_item, extract_ids
from lib.api.trakt.trakt_utils import add_trakt_collection_context_menu
from lib.utils.general.utils import (
    Anime,
    Enum,
    add_next_button,
    execute_thread_pool,
    set_content_type,
    set_media_infoTag,
)
from lib.utils.kodi.utils import (
    action_url_run,
    build_url,
    dialog_select,
    dialog_text,
    dialogyesno,
    end_of_directory,
    get_datetime,
    get_setting,
    kodilog,
    notification,
    kodi_play_media,
    refresh,
    show_keyboard,
    translation,
)
from .paginator import paginator_db

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
    CALENDAR = "trakt_calendar"
    UP_NEXT = "trakt_up_next"
    COLLECTION = "trakt_collection"
    FAVORITES = "trakt_favorites"
    MY_LISTS = "trakt_my_lists"
    LIKED_LISTS = "trakt_liked_lists"
    SEARCH_LISTS = "trakt_search_lists"
    ACCOUNT_INFO = "trakt_account_info"
    CREATE_LIST = "trakt_create_list"


class BaseTraktClient:
    @staticmethod
    def _add_media_directory_item(list_item, mode, title, ids, media_type=None):
        if mode == "movies":
            list_item.addContextMenuItems(
                [
                    (
                        translation(90049),
                        kodi_play_media(
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
                    + add_trakt_collection_context_menu("movies", ids)
                    + add_trakt_custom_list_context_menu("movies", ids)
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
                    + add_trakt_collection_context_menu("shows", ids)
                    + add_trakt_custom_list_context_menu("shows", ids)
                )
            add_kodi_dir_item(
                list_item=list_item,
                url=build_url(
                    "show_seasons_details",
                    ids=ids,
                    mode=mode,
                    media_type=media_type,
                ),
                is_folder=True,
            )


class TraktClient:
    @staticmethod
    def handle_trakt_query(query, category, mode, page, submode, api, params=None):
        set_content_type(mode)
        params = params or {}
        handlers = {
            "movies": lambda q, m, p: TraktClient.handle_trakt_movie_query(
                q, m, p, params
            ),
            "tv": lambda q, m, p: TraktClient.handle_trakt_show_query(
                q, m, p, params
            ),
            "anime": lambda q, m, p: TraktClient.handle_trakt_anime_query(
                category, p, submode
            ),
        }
        handler = handlers.get(mode)
        if handler:
            return handler(query, mode, page)

    @staticmethod
    def handle_trakt_movie_query(query, mode, page, params=None):
        params = params or {}
        query_handlers = {
            Trakt.TRENDING: lambda: TraktMovies().trakt_movies_trending(page),
            Trakt.TOP10: lambda: TraktMovies().trakt_movies_top10_boxoffice(),
            Trakt.WATCHED: lambda: TraktMovies().trakt_movies_most_watched(page),
            Trakt.WATCHED_HISTORY: lambda: TraktLists().trakt_watched_history(
                mode, page
            ),
            Trakt.FAVORITED: lambda: TraktMovies().trakt_movies_most_favorited(page),
            Trakt.RECOMENDATIONS: lambda: TraktMovies().trakt_recommendations("movies"),
            Trakt.FAVORITES: lambda: TraktLists().trakt_favorites(mode),
            Trakt.MY_LISTS: lambda: TraktLists().trakt_get_lists("my_lists"),
            Trakt.LIKED_LISTS: lambda: TraktLists().trakt_get_lists("liked_lists"),
            Trakt.SEARCH_LISTS: lambda: TraktClient._search_trakt_lists(params, page),
            Trakt.ACCOUNT_INFO: TraktClient.get_account_info,
        }

        list_handlers = {
            Trakt.TRENDING_LISTS: lambda: TraktLists().trakt_trending_popular_lists(
                list_type="trending", page_no=page
            ),
            Trakt.POPULAR_LISTS: lambda: TraktLists().trakt_trending_popular_lists(
                list_type="popular", page_no=page
            ),
            Trakt.WATCHLIST: lambda: TraktLists().trakt_watchlist(mode),
            Trakt.COLLECTION: lambda: TraktMovies().trakt_collection(page),
        }

        if query in query_handlers:
            return query_handlers[query]()
        elif query in list_handlers:
            return list_handlers[query]()

    @staticmethod
    def handle_trakt_show_query(query, mode, page, params=None):
        params = params or {}
        query_handlers = {
            Trakt.TRENDING: lambda: TraktTV().trakt_tv_trending(page),
            Trakt.WATCHED: lambda: TraktTV().trakt_tv_most_watched(page),
            Trakt.WATCHED_HISTORY: lambda: TraktLists().trakt_watched_history(
                mode, page
            ),
            Trakt.FAVORITED: lambda: TraktTV().trakt_tv_most_favorited(page),
            Trakt.RECOMENDATIONS: lambda: TraktTV().trakt_recommendations("shows"),
            Trakt.FAVORITES: lambda: TraktLists().trakt_favorites(mode),
            Trakt.MY_LISTS: lambda: TraktLists().trakt_get_lists("my_lists"),
            Trakt.LIKED_LISTS: lambda: TraktLists().trakt_get_lists("liked_lists"),
            Trakt.SEARCH_LISTS: lambda: TraktClient._search_trakt_lists(params, page),
            Trakt.ACCOUNT_INFO: TraktClient.get_account_info,
        }

        list_handlers = {
            Trakt.TRENDING_LISTS: lambda: TraktLists().trakt_trending_popular_lists(
                list_type="trending", page_no=page
            ),
            Trakt.POPULAR_LISTS: lambda: TraktLists().trakt_trending_popular_lists(
                list_type="popular", page_no=page
            ),
            Trakt.WATCHLIST: lambda: TraktLists().trakt_watchlist(mode),
            Trakt.COLLECTION: lambda: TraktTV().trakt_collection(page),
            Trakt.CALENDAR: lambda: TraktClient.handle_calendar_request(),
            Trakt.UP_NEXT: lambda: TraktTV().trakt_up_next(),
        }

        if query in query_handlers:
            return query_handlers[query]()
        elif query in list_handlers:
            return list_handlers[query]()

    @staticmethod
    def handle_trakt_anime_query(query, page, submode="tv"):
        if query == Anime.TRENDING:
            return TraktAPI().anime.trakt_anime_trending(page, submode)
        elif query == Anime.TRENDING_RECENT:
            return TraktAPI().anime.trakt_anime_trending_recent(page, submode)
        elif query == Anime.MOST_WATCHED:
            return TraktAPI().anime.trakt_anime_most_watched(page, submode)
        elif query == Anime.FAVORITED:
            return TraktAPI().anime.trakt_anime_most_favorited(page, submode)

    @staticmethod
    def _search_trakt_lists(params, page):
        search_term = params.get("search_term", "")
        if not search_term:
            search_term = show_keyboard(id=30243, default="")
        if not search_term:
            params["_trakt_search_cancelled"] = True
            return []
        params.pop("_trakt_search_cancelled", None)
        params["search_term"] = search_term
        return TraktLists().trakt_search_lists(search_term, page)

    @staticmethod
    def get_account_info():
        auth_api = TraktAPI().auth
        settings = auth_api.get_user_settings() or {}
        stats = auth_api.get_account_stats() or {}
        return {"settings": settings, "stats": stats}

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
    def trakt_add_to_collection(params):
        media_type = params.get("media_type")
        ids = json.loads(params.get("ids", "{}"))
        try:
            TraktAPI().lists.add_to_collection(media_type, ids)
            notification("Added to Trakt collection", time=3000)
        except Exception as e:
            kodilog(f"Error adding to Trakt collection: {e}")
            notification("Failed to add to Trakt collection", time=3000)

    @staticmethod
    def trakt_remove_from_collection(params):
        media_type = params.get("media_type")
        ids = json.loads(params.get("ids", "{}"))
        try:
            TraktAPI().lists.remove_from_collection(media_type, ids)
            notification("Removed from Trakt collection", time=3000)
        except Exception as e:
            kodilog(f"Error removing from Trakt collection: {e}")
            notification("Failed to remove from Trakt collection", time=3000)

    @staticmethod
    def trakt_create_list(params):
        name = show_keyboard(id=30924, default="")
        if not name:
            return

        description = show_keyboard(id=30925, default="") or ""
        try:
            TraktAPI().lists.create_list(name=name, description=description)
            notification("Created Trakt list", time=3000)
            refresh()
        except Exception as e:
            kodilog(f"Error creating Trakt list: {e}")
            notification("Failed to create Trakt list", time=3000)

    @staticmethod
    def trakt_delete_list(params):
        trakt_id = params.get("trakt_id")
        if not trakt_id:
            return
        if not dialogyesno("Trakt", "Delete this Trakt list?"):
            return
        try:
            TraktAPI().lists.delete_list(trakt_id)
            notification("Deleted Trakt list", time=3000)
            refresh()
        except Exception as e:
            kodilog(f"Error deleting Trakt list: {e}")
            notification("Failed to delete Trakt list", time=3000)

    @staticmethod
    def trakt_like_list(params):
        trakt_id = params.get("trakt_id")
        user_slug = params.get("user")
        if not trakt_id or not user_slug:
            return
        try:
            TraktAPI().lists.like_list(user_slug, trakt_id)
            notification("Liked Trakt list", time=3000)
            refresh()
        except Exception as e:
            kodilog(f"Error liking Trakt list: {e}")
            notification("Failed to like Trakt list", time=3000)

    @staticmethod
    def trakt_unlike_list(params):
        trakt_id = params.get("trakt_id")
        user_slug = params.get("user")
        if not trakt_id or not user_slug:
            return
        try:
            TraktAPI().lists.unlike_list(user_slug, trakt_id)
            notification("Unliked Trakt list", time=3000)
            refresh()
        except Exception as e:
            kodilog(f"Error unliking Trakt list: {e}")
            notification("Failed to unlike Trakt list", time=3000)

    @staticmethod
    def _select_trakt_list():
        my_lists = TraktAPI().lists.trakt_get_lists("my_lists") or []
        if not my_lists:
            notification("No Trakt lists found", time=3000)
            return None

        options = [item.get("name", "Untitled List") for item in my_lists]
        choice = dialog_select(translation(30927), options)
        if choice < 0:
            return None
        return my_lists[choice]

    @staticmethod
    def trakt_add_item_to_list(params):
        media_type = params.get("media_type")
        ids = json.loads(params.get("ids", "{}"))
        selected_list = TraktClient._select_trakt_list()
        if not selected_list:
            return
        try:
            TraktAPI().lists.add_item_to_list(
                selected_list.get("trakt_id"), media_type, ids
            )
            notification("Added to Trakt list", time=3000)
        except Exception as e:
            kodilog(f"Error adding item to Trakt list: {e}")
            notification("Failed to add to Trakt list", time=3000)

    @staticmethod
    def trakt_remove_item_from_list(params):
        media_type = params.get("media_type")
        ids = json.loads(params.get("ids", "{}"))
        selected_list = TraktClient._select_trakt_list()
        if not selected_list:
            return
        try:
            TraktAPI().lists.remove_item_from_list(
                selected_list.get("trakt_id"), media_type, ids
            )
            notification("Removed from Trakt list", time=3000)
        except Exception as e:
            kodilog(f"Error removing item from Trakt list: {e}")
            notification("Failed to remove from Trakt list", time=3000)

    @staticmethod
    def handle_calendar_request():
        previous_days = int(get_setting("trakt_calendar_previous_days", 0))
        future_days = int(get_setting("trakt_calendar_future_days", 14))

        # Calculate start date
        start_date_obj = get_datetime(string=False) - timedelta(days=previous_days)
        start_date = start_date_obj.strftime("%Y-%m-%d")

        # Calculate total days (past + future + today)
        days = previous_days + future_days + 1

        # Log user identity logic
        try:
            user_settings = TraktAPI().auth.get_user_settings()
            if user_settings and "user" in user_settings:
                username = user_settings.get("user", {}).get("username")
                kodilog(f"Trakt Calendar Request for user: {username}")
        except Exception as e:
            kodilog(f"Error fetching Trakt user profile: {e}")

        if get_setting("trakt_calendar_show_all"):
            return TraktAPI().calendar.trakt_all_shows_calendar(
                start_date=start_date, days=days
            )

        return TraktAPI().calendar.trakt_my_calendar(start_date=start_date, days=days)

    @staticmethod
    def process_trakt_result(
        results, query, category, mode, submode, api, page, search_term=""
    ):
        if query == Trakt.ACCOUNT_INFO:
            TraktPresentation.show_account_info(results)
            end_of_directory()
            return

        if not results:
            if query == Trakt.SEARCH_LISTS and not search_term:
                end_of_directory()
                return
            if query in (Trakt.CALENDAR, Trakt.UP_NEXT, Trakt.SEARCH_LISTS):
                notification("No results found", time=3000)

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
            Trakt.COLLECTION: lambda: execute_thread_pool(
                results, TraktPresentation.show_common_categories, mode
            ),
            Trakt.CALENDAR: lambda: execute_thread_pool(
                results, TraktPresentation.show_calendar_items
            ),
            Trakt.UP_NEXT: lambda: execute_thread_pool(
                results, TraktPresentation.show_up_next_items
            ),
            Trakt.FAVORITES: lambda: execute_thread_pool(
                results, TraktPresentation.show_watchlist, mode
            ),
            Trakt.MY_LISTS: lambda: execute_thread_pool(
                results, TraktPresentation.show_user_lists, mode
            ),
            Trakt.LIKED_LISTS: lambda: execute_thread_pool(
                results, TraktPresentation.show_user_lists, mode
            ),
            Trakt.SEARCH_LISTS: lambda: execute_thread_pool(
                results, TraktPresentation.show_user_lists, mode
            ),
        }

        anime_handlers = {
            Anime.TRENDING: lambda: execute_thread_pool(
                results, TraktPresentation.show_anime_common, submode
            ),
            Anime.TRENDING_RECENT: lambda: execute_thread_pool(
                results, TraktPresentation.show_anime_common, submode
            ),
            Anime.MOST_WATCHED: lambda: execute_thread_pool(
                results, TraktPresentation.show_anime_common, submode
            ),
            Anime.FAVORITED: lambda: execute_thread_pool(
                results, TraktPresentation.show_anime_common, submode
            ),
        }

        if query in query_handlers:
            query_handlers[query]()
            if query == Trakt.MY_LISTS:
                TraktPresentation.show_create_list_entry(mode)
        if category in anime_handlers:
            anime_handlers[category]()

        if TraktClient._should_add_next_button(query, category):
            next_kwargs = {
                "query": query,
                "category": category,
                "mode": mode,
                "submode": submode,
                "api": api,
            }
            if search_term:
                next_kwargs["search_term"] = search_term
            add_next_button("search_item", page=page, **next_kwargs)
        end_of_directory()

    @staticmethod
    def _should_add_next_button(query, category):
        paginated_queries = {
            Trakt.TRENDING,
            Trakt.WATCHED,
            Trakt.FAVORITED,
            Trakt.TRENDING_LISTS,
            Trakt.POPULAR_LISTS,
            Trakt.WATCHED_HISTORY,
            Trakt.COLLECTION,
            Trakt.SEARCH_LISTS,
        }
        paginated_categories = {
            Anime.TRENDING,
            Anime.TRENDING_RECENT,
            Anime.MOST_WATCHED,
            Anime.FAVORITED,
        }
        return query in paginated_queries or category in paginated_categories

    @staticmethod
    def show_trakt_list_content(list_type, mode, user, slug, with_auth, page, trakt_id=None):
        data = TraktAPI().lists.get_trakt_list_contents(
            list_type, user, slug, with_auth, trakt_id
        )
        if not data:
            notification("No results found", time=3000)
            end_of_directory()
            return
        paginator_db.initialize(data)
        items = paginator_db.get_page(page)
        execute_thread_pool(items, TraktPresentation.show_lists_content_items)
        add_next_button("list_trakt_page", page, mode=mode)
        end_of_directory()

    @staticmethod
    def show_list_trakt_page(page, mode):
        items = paginator_db.get_page(page)
        execute_thread_pool(items, TraktPresentation.show_lists_content_items)
        add_next_button("list_trakt_page", page, mode=mode)
        end_of_directory()


class TraktPresentation:
    @staticmethod
    def show_create_list_entry(mode):
        list_item = ListItem(f"[B]+ {translation(30926)}[/B]")
        add_kodi_dir_item(
            list_item=list_item,
            url=build_url("trakt_create_list", mode=mode),
            is_folder=False,
        )

    @staticmethod
    def _format_account_info(results):
        settings = results.get("settings", {}) if isinstance(results, dict) else {}
        stats = results.get("stats", {}) if isinstance(results, dict) else {}
        user = settings.get("user", {})
        account = settings.get("account", {})
        connections = settings.get("connections", {})

        lines = [str(translation(30916)), ""]
        lines.append(f"Username: {user.get('username', '')}")
        lines.append(f"Name: {user.get('name', '')}")
        lines.append(f"Joined: {user.get('joined_at', '')}")
        lines.append(f"Private: {str(account.get('private', False))}")
        lines.append(f"VIP: {str(user.get('vip', False))}")
        lines.append(f"Timezone: {account.get('timezone', '')}")
        lines.append(f"Locale: {account.get('locale', '')}")
        lines.append("")
        lines.append("Stats")
        lines.append(f"Movies Watched: {stats.get('movies', {}).get('watched', 0)}")
        lines.append(f"Shows Watched: {stats.get('shows', {}).get('watched', 0)}")
        lines.append(f"Episodes Watched: {stats.get('episodes', {}).get('watched', 0)}")
        lines.append(f"Movies Collected: {stats.get('movies', {}).get('collected', 0)}")
        lines.append(f"Shows Collected: {stats.get('shows', {}).get('collected', 0)}")
        lines.append(f"Lists: {stats.get('lists', {}).get('count', 0)}")
        lines.append("")
        lines.append("Connections")
        for key in ("facebook", "google", "twitter", "mastodon"):
            connection = connections.get(key, False)
            lines.append(f"{key.title()}: {str(bool(connection))}")
        return "\n".join(lines)

    @staticmethod
    def show_account_info(results):
        content = TraktPresentation._format_account_info(results)
        dialog_text(translation(30916), content)

    @staticmethod
    def show_anime_common(res, mode):
        ids = extract_ids(res, mode)
        # Handle both show and movie responses
        if mode == "movies" and "movie" in res:
            title = res["movie"]["title"]
        else:
            title = res["show"]["title"]

        tmdb_id = ids["tmdb_id"]
        if mode == "tv":
            details = tmdb_get("tv_details", tmdb_id)
        else:
            details = tmdb_get("movie_details", tmdb_id)

        list_item = ListItem(label=title)
        set_media_infoTag(list_item, data=details, mode=mode)

        BaseTraktClient._add_media_directory_item(
            list_item=list_item,
            mode=mode,
            title=title,
            ids=ids,
            media_type=res.get("media_type"),
        )

    @staticmethod
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
        set_media_infoTag(list_item, data=details, mode=mode)

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
        set_media_infoTag(list_item, data=details, mode=mode)

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
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(list_title)
        info_tag.setPlot(description)
        list_item.addContextMenuItems(
            [
                (
                    "Like Trakt List",
                    action_url_run(
                        "trakt_like_list",
                        trakt_id=res["list"]["ids"].get("trakt"),
                        user=res["list"]["user"]["ids"].get("slug", ""),
                    ),
                )
            ]
        )

        add_kodi_dir_item(
            list_item,
            url=url,
            is_folder=True,
        )

    @staticmethod
    def show_user_lists(res, mode):
        list_title = res.get("name", "Untitled List")
        description = res.get("description", "")
        item_count = res.get("item_count")
        username = res.get("username") or res.get("user_slug", "")

        if item_count:
            label = f"{list_title} ({item_count})"
        else:
            label = list_title

        if username:
            label = f"{label} - [I]{username}[/I]"

        list_item = ListItem(label)
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(list_title)
        info_tag.setPlot(description)

        context_menu = []
        if res.get("can_delete"):
            context_menu.append(
                (
                    "Delete Trakt List",
                    action_url_run(
                        "trakt_delete_list",
                        trakt_id=res.get("trakt_id", ""),
                    ),
                )
            )
        if res.get("can_unlike"):
            context_menu.append(
                (
                    "Unlike Trakt List",
                    action_url_run(
                        "trakt_unlike_list",
                        trakt_id=res.get("trakt_id", ""),
                        user=res.get("user_slug", ""),
                    ),
                )
            )
        if res.get("can_like"):
            context_menu.append(
                (
                    "Like Trakt List",
                    action_url_run(
                        "trakt_like_list",
                        trakt_id=res.get("trakt_id", ""),
                        user=res.get("user_slug", ""),
                    ),
                )
            )
        if context_menu:
            list_item.addContextMenuItems(context_menu)

        add_kodi_dir_item(
            list_item=list_item,
            url=build_url(
                "trakt_list_content",
                list_type=res.get("list_type", "user_lists"),
                mode=mode,
                user=res.get("user_slug", ""),
                slug=res.get("slug", ""),
                with_auth=res.get("with_auth", False),
                trakt_id=res.get("trakt_id", ""),
            ),
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
        set_media_infoTag(list_item, data=details, mode=mode)

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
        set_media_infoTag(list_item, data=details, mode=mode)

        add_kodi_dir_item(
            list_item,
            url=url,
            is_folder=is_folder,
            is_playable=is_playable,
        )

    @staticmethod
    def show_lists_content_items(res):
        media_ids = res.get("media_ids", {})
        tmdb_id = media_ids.get("tmdb")
        imdb_id = media_ids.get("imdb", "")
        tvdb_id = media_ids.get("tvdb", "")
        title = res["title"]

        if res["type"] == "show":
            mode = "tv"
            if not tmdb_id and imdb_id:
                found = tmdb_get("find_by_imdb_id", imdb_id)
                if getattr(found, "tv_results", []):
                    tmdb_id = str(found.tv_results[0]["id"])
            if not tmdb_id and tvdb_id:
                found = tmdb_get("find_by_tvdb", tvdb_id)
                if getattr(found, "tv_results", []):
                    tmdb_id = str(found.tv_results[0]["id"])
            if not tmdb_id:
                return
            details = tmdb_get("tv_details", tmdb_id)
        else:
            mode = "movies"
            if not tmdb_id and imdb_id:
                found = tmdb_get("find_by_imdb_id", imdb_id)
                if getattr(found, "movie_results", []):
                    tmdb_id = str(found.movie_results[0]["id"])
            if not tmdb_id:
                return
            details = tmdb_get("movie_details", tmdb_id)

        ids = {"tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id}

        list_item = ListItem(label=title)
        set_media_infoTag(list_item, data=details, mode=mode)

        BaseTraktClient._add_media_directory_item(
            list_item=list_item,
            mode=mode,
            title=title,
            ids=ids,
            media_type=res.get("media_type"),
        )

    @staticmethod
    def show_calendar_items(res):
        show_title = res.get("show", {}).get("title")
        ep_data = res.get("episode", {})
        title = ep_data.get("title")
        season = ep_data.get("season")
        episode = ep_data.get("number")

        first_aired = res.get("first_aired")

        tmdb_id = res.get("show", {}).get("ids", {}).get("tmdb")
        imdb_id = res.get("show", {}).get("ids", {}).get("imdb")
        tvdb_id = res.get("show", {}).get("ids", {}).get("tvdb")

        if not tmdb_id:
            return

        display_title = f"{show_title} - S{season}E{episode} - {title}"
        if first_aired:
            date_part = first_aired.split("T")[0]
            display_title = f"{date_part} | {display_title}"

        ids = {"tmdb_id": tmdb_id, "imdb_id": imdb_id, "tvdb_id": tvdb_id}

        details = tmdb_get("tv_details", tmdb_id) or {}

        list_item = ListItem(label=display_title)
        set_media_infoTag(list_item, data=details, mode="tv")

        # Override title
        list_item.setLabel(display_title)
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(display_title)
        info_tag.setPlot(details.get("overview", ""))

        url = build_url(
            "search",
            ids=ids,
            mode="tv",
            query=show_title,
            tv_data={
                "name": title,
                "episode": episode,
                "season": season,
            },
        )

        add_kodi_dir_item(
            list_item=list_item,
            url=url,
            is_folder=True,
        )

    @staticmethod
    def show_up_next_items(res):
        show_data = res.get("show", {})
        episode = res.get("episode", {})
        show_title = show_data.get("title", "")
        title = episode.get("title", "")
        season = episode.get("season")
        episode_number = episode.get("number")
        progress = res.get("progress", 0)
        tmdb_id = show_data.get("ids", {}).get("tmdb")
        imdb_id = show_data.get("ids", {}).get("imdb")
        tvdb_id = show_data.get("ids", {}).get("tvdb")

        if not tmdb_id or season is None or episode_number is None:
            return

        prefix = "[Resume]" if res.get("type") == "resume" else "[Next]"
        display_title = (
            f"{prefix} {show_title} - S{int(season):02d}E{int(episode_number):02d} - {title}"
        )
        if progress:
            display_title = f"{display_title} ({int(progress)}%)"

        ids = {"tmdb_id": tmdb_id, "imdb_id": imdb_id, "tvdb_id": tvdb_id}
        details = tmdb_get("tv_details", tmdb_id) or {}

        list_item = ListItem(label=display_title)
        set_media_infoTag(list_item, data=details, mode="tv")
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(display_title)
        info_tag.setPlot(details.get("overview", ""))
        if progress:
            list_item.setProperty("PercentPlayed", str(progress))

        url = build_url(
            "search",
            ids=ids,
            mode="tv",
            query=show_title,
            tv_data={
                "name": title,
                "episode": episode_number,
                "season": season,
            },
        )

        add_kodi_dir_item(list_item=list_item, url=url, is_folder=True)
