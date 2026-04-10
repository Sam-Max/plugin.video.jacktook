import json
from datetime import datetime, timedelta
from lib.clients.tmdb.utils.utils import build_play_trailer_context_menu_item, tmdb_get
from lib.api.trakt.trakt import TraktAPI, TraktLists, TraktMovies, TraktTV
from lib.api.trakt.trakt_utils import (
    add_trakt_custom_list_context_menu,
    add_trakt_favorites_context_menu,
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
    truncate_text,
)
from lib.utils.kodi.utils import (
    action_url_run,
    add_directory_items_batch,
    build_url,
    container_update,
    dialog_select,
    dialog_text,
    dialogyesno,
    end_of_directory,
    execute_builtin,
    get_datetime,
    get_setting,
    kodilog,
    make_list_item,
    notification,
    kodi_play_media,
    refresh,
    show_keyboard,
    translation,
)
from .paginator import paginator_db


def _normalize_user_slug(value):
    if value in (None, "", "None"):
        return ""
    return str(value)


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
    MOVIES_PROGRESS = "trakt_movies_progress"
    COLLECTION = "trakt_collection"
    FAVORITES = "trakt_favorites"
    MY_LISTS = "trakt_my_lists"
    LIKED_LISTS = "trakt_liked_lists"
    SEARCH_LISTS = "trakt_search_lists"
    ACCOUNT_INFO = "trakt_account_info"
    CREATE_LIST = "trakt_create_list"


class BaseTraktClient:
    @staticmethod
    def _exclusive_context_flags(remove_action):
        flags = {
            "watchlist_add": False,
            "watchlist_remove": False,
            "watched_add": False,
            "watched_remove": False,
            "collection_add": False,
            "collection_remove": False,
            "favorites_add": False,
            "favorites_remove": False,
            "custom_list_add": False,
            "custom_list_remove": False,
        }
        if remove_action == "watchlist":
            flags["watchlist_remove"] = True
        elif remove_action == "watched":
            flags["watched_remove"] = True
        elif remove_action == "collection":
            flags["collection_remove"] = True
        elif remove_action == "favorites":
            flags["favorites_remove"] = True
        elif remove_action == "custom_list":
            flags["custom_list_remove"] = True
        return flags

    @staticmethod
    def _trakt_context_menu(mode, ids, context_flags=None):
        context_flags = context_flags or {}
        media_type = "movies" if mode == "movies" else "shows"
        return (
            add_trakt_watchlist_context_menu(
                media_type,
                ids,
                include_add=context_flags.get("watchlist_add", True),
                include_remove=context_flags.get("watchlist_remove", True),
            )
            + add_trakt_watched_context_menu(
                media_type,
                ids=ids,
                include_add=context_flags.get("watched_add", True),
                include_remove=context_flags.get("watched_remove", True),
            )
            + add_trakt_collection_context_menu(
                media_type,
                ids,
                include_add=context_flags.get("collection_add", True),
                include_remove=context_flags.get("collection_remove", True),
            )
            + add_trakt_favorites_context_menu(
                media_type,
                ids,
                include_add=context_flags.get("favorites_add", True),
                include_remove=context_flags.get("favorites_remove", True),
            )
            + add_trakt_custom_list_context_menu(
                media_type,
                ids,
                include_add=context_flags.get("custom_list_add", True),
                include_remove=context_flags.get("custom_list_remove", True),
            )
        )

    @staticmethod
    def _add_media_directory_item(
        list_item, mode, title, ids, media_type=None, context_flags=None
    ):
        trailer_item = build_play_trailer_context_menu_item(
            ids=ids,
            media_type="movie" if mode == "movies" else "tv",
            title=title,
            title_key="title",
        )
        if mode == "movies":
            context_menu = [
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
            if trailer_item:
                context_menu.append(trailer_item)
            context_menu += (
                    BaseTraktClient._trakt_context_menu(
                        "movies", ids, context_flags=context_flags
                    )
                    if is_trakt_auth()
                    else []
                )
            list_item.addContextMenuItems(context_menu)
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
            context_menu = []
            if trailer_item:
                context_menu.append(trailer_item)
            if is_trakt_auth():
                context_menu += BaseTraktClient._trakt_context_menu(
                    "tv", ids, context_flags=context_flags
                )
            if context_menu:
                list_item.addContextMenuItems(context_menu)
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
    def _refresh_after_list_action(params):
        if params.get("query") == Trakt.SEARCH_LISTS and params.get("search_term"):
            execute_builtin(
                container_update(
                    "search_item",
                    query=params.get("query"),
                    category=params.get("category"),
                    mode=params.get("mode"),
                    submode=params.get("submode", ""),
                    api=params.get("api", "trakt"),
                    page=params.get("page", 1),
                    search_term=params.get("search_term"),
                )
            )
            return
        refresh()

    @staticmethod
    def _trakt_sync_result_count(result, key, media_type):
        if not isinstance(result, dict):
            return 0
        section = result.get(key, {})
        if not isinstance(section, dict):
            return 0
        media_keys = []
        if media_type in ("movie", "movies"):
            media_keys = ["movies", "movie"]
        else:
            media_keys = ["shows", "show"]
        for media_key in media_keys:
            value = section.get(media_key)
            if isinstance(value, int):
                return value
        return 0

    @staticmethod
    def _normalize_trakt_media_type(media_type, ids):
        if media_type in ("tv", "show", "shows", "tvshow", "tvshows", "anime"):
            return "shows"
        if media_type in ("movie", "movies"):
            if ids.get("tvdb") or ids.get("tvdb_id"):
                return "shows"
        if ids.get("tvdb") or ids.get("tvdb_id"):
            return "shows"

        tmdb_id = ids.get("tmdb") or ids.get("tmdb_id")
        if tmdb_id:
            tv_details = tmdb_get("tv_details", tmdb_id)
            tv_name = getattr(tv_details, "name", None)
            if tv_name is None and isinstance(tv_details, dict):
                tv_name = tv_details.get("name")
            if tv_name:
                return "shows"

            movie_details = tmdb_get("movie_details", tmdb_id)
            movie_title = getattr(movie_details, "title", None)
            if movie_title is None and isinstance(movie_details, dict):
                movie_title = movie_details.get("title")
            if movie_title:
                return "movies"

        imdb_id = ids.get("imdb") or ids.get("imdb_id")
        if imdb_id:
            found = tmdb_get("find_by_imdb_id", imdb_id)
            if getattr(found, "tv_results", []):
                return "shows"
            if getattr(found, "movie_results", []):
                return "movies"

        return "movies"

    @staticmethod
    def _build_show_collection_payload(ids):
        resolved_ids = TraktPresentation._resolve_media_ids("tv", ids)
        tmdb_id = resolved_ids.get("tmdb_id")
        show_details = tmdb_get("tv_details", tmdb_id) if tmdb_id else None
        trakt_object = (
            TraktAPI().lists.get_trakt_object_by_tmdb(tmdb_id, media_type="show")
            if tmdb_id
            else None
        )
        normalized_ids = {}
        if resolved_ids.get("tmdb_id"):
            normalized_ids["tmdb"] = int(resolved_ids["tmdb_id"])
            trakt_id = trakt_object.get("ids", {}).get("trakt") if trakt_object else None
            if trakt_id:
                normalized_ids["trakt"] = trakt_id
        if resolved_ids.get("tvdb_id"):
            normalized_ids["tvdb"] = int(resolved_ids["tvdb_id"])
        if resolved_ids.get("imdb_id"):
            normalized_ids["imdb"] = resolved_ids["imdb_id"]
        slug = trakt_object.get("ids", {}).get("slug") if trakt_object else None
        if slug:
            normalized_ids["slug"] = slug
        if not normalized_ids:
            return None

        show_item = {"ids": normalized_ids}
        title = trakt_object.get("title") if trakt_object else None
        if title is None:
            title = getattr(show_details, "name", None)
        if title is None and isinstance(show_details, dict):
            title = show_details.get("name")
        if title:
            show_item["title"] = title
        first_air_date = trakt_object.get("year") if trakt_object else None
        if isinstance(first_air_date, int):
            show_item["year"] = first_air_date
            return {"shows": [show_item]}

        first_air_date = getattr(show_details, "first_air_date", None)
        if first_air_date is None and isinstance(show_details, dict):
            first_air_date = show_details.get("first_air_date")
        if first_air_date:
            try:
                show_item["year"] = int(str(first_air_date)[:4])
            except (TypeError, ValueError):
                pass

        return {"shows": [show_item]}

    @staticmethod
    def _build_show_collection_episode_payload(ids):
        resolved_ids = TraktPresentation._resolve_media_ids("tv", ids)
        tmdb_id = resolved_ids.get("tmdb_id")
        if not tmdb_id:
            return None

        show_details = tmdb_get("tv_details", tmdb_id)
        total_seasons = getattr(show_details, "number_of_seasons", 0) or show_details.get(
            "number_of_seasons", 0
        )
        today = datetime.utcnow().date()
        seasons_payload = []

        for season_number in range(1, int(total_seasons) + 1):
            season_details = tmdb_get(
                "season_details", {"id": tmdb_id, "season": season_number}
            )
            episodes = getattr(season_details, "episodes", None)
            if episodes is None and isinstance(season_details, dict):
                episodes = season_details.get("episodes", [])
            if not episodes:
                continue

            episode_entries = []
            for episode in episodes:
                air_date = getattr(episode, "air_date", None)
                if air_date is None and isinstance(episode, dict):
                    air_date = episode.get("air_date")
                if air_date:
                    try:
                        if datetime.strptime(air_date, "%Y-%m-%d").date() > today:
                            continue
                    except ValueError:
                        pass

                episode_number = getattr(episode, "episode_number", None)
                if episode_number is None and isinstance(episode, dict):
                    episode_number = episode.get("episode_number")
                if not episode_number:
                    continue
                episode_entries.append({"number": int(episode_number)})

            if episode_entries:
                seasons_payload.append(
                    {"number": int(season_number), "episodes": episode_entries}
                )

        if not seasons_payload:
            return None

        trakt_ids = {k: v for k, v in resolved_ids.items() if v}
        trakt_object = TraktAPI().lists.get_trakt_object_by_tmdb(tmdb_id, media_type="show")
        normalized_ids = {}
        if trakt_ids.get("tmdb_id"):
            normalized_ids["tmdb"] = int(trakt_ids["tmdb_id"])
            trakt_id = trakt_object.get("ids", {}).get("trakt") if trakt_object else None
            if trakt_id:
                normalized_ids["trakt"] = trakt_id
        if trakt_ids.get("tvdb_id"):
            normalized_ids["tvdb"] = int(trakt_ids["tvdb_id"])
        if trakt_ids.get("imdb_id"):
            normalized_ids["imdb"] = trakt_ids["imdb_id"]
        slug = trakt_object.get("ids", {}).get("slug") if trakt_object else None
        if slug:
            normalized_ids["slug"] = slug

        show_item = {"ids": normalized_ids, "seasons": seasons_payload}
        if trakt_object and trakt_object.get("title"):
            show_item["title"] = trakt_object.get("title")
        if trakt_object and trakt_object.get("year"):
            show_item["year"] = trakt_object.get("year")
        return {"shows": [show_item]}

    @staticmethod
    def _build_show_collection_season_payload(ids):
        episode_payload = TraktClient._build_show_collection_episode_payload(ids)
        if not episode_payload:
            return None

        show_item = episode_payload["shows"][0]
        seasons = show_item.get("seasons", [])
        if not seasons:
            return None

        season_payload = {
            "shows": [
                {
                    "ids": show_item.get("ids", {}),
                    "seasons": [{"number": season.get("number")} for season in seasons if season.get("number")],
                }
            ]
        }
        if show_item.get("title"):
            season_payload["shows"][0]["title"] = show_item.get("title")
        if show_item.get("year"):
            season_payload["shows"][0]["year"] = show_item.get("year")
        return season_payload

    @staticmethod
    def _result_has_collection_change(result, action):
        if action == "add":
            relevant_keys = ("added", "updated", "existing")
        else:
            relevant_keys = ("deleted",)

        for key in relevant_keys:
            section = result.get(key, {}) if isinstance(result, dict) else {}
            if not isinstance(section, dict):
                continue
            if any(int(section.get(count_key, 0) or 0) > 0 for count_key in ("movies", "episodes")):
                return True
        return False

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
            Trakt.MOVIES_PROGRESS: lambda: TraktMovies().trakt_movies_progress(),
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
        ids = json.loads(params.get("ids", "{}"))
        media_type = TraktClient._normalize_trakt_media_type(
            params.get("media_type"), ids
        )
        try:
            TraktAPI().lists.add_to_watchlist(media_type, ids)
            notification(translation(90434), time=3000)
            refresh()
        except Exception as e:
            kodilog(f"Error adding to Trakt watchlist: {e}")
            notification(translation(90435), time=3000)

    @staticmethod
    def trakt_remove_from_watchlist(params):
        ids = json.loads(params.get("ids", "{}"))
        media_type = TraktClient._normalize_trakt_media_type(
            params.get("media_type"), ids
        )
        try:
            TraktAPI().lists.remove_from_watchlist(media_type, ids)
            notification(translation(90436), time=3000)
            refresh()
        except Exception as e:
            kodilog(f"Error removing from Trakt watchlist: {e}")
            notification(translation(90437), time=3000)

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
            notification(translation(90438), time=3000)

    @staticmethod
    def trakt_mark_as_unwatched(params):
        media_type = params.get("media_type")
        season = json.loads(params.get("season"))
        episode = json.loads(params.get("episode"))
        ids = json.loads(params.get("ids", "{}"))
        try:
            TraktAPI().lists.mark_as_unwatched(media_type, season, episode, ids)
            notification(translation(90439), time=3000)
        except Exception as e:
            kodilog(f"Error marking as unwatched on Trakt: {e}")
            notification(translation(90440), time=3000)

    @staticmethod
    def trakt_add_to_collection(params):
        ids = json.loads(params.get("ids", "{}"))
        media_type = TraktClient._normalize_trakt_media_type(
            params.get("media_type"), ids
        )
        try:
            payload = None
            if media_type not in ("movie", "movies"):
                payload = TraktClient._build_show_collection_payload(ids)
                if payload is None:
                    notification(translation(90465), time=3500)
                    return
            result = TraktAPI().lists.add_to_collection(media_type, ids, payload=payload)
            if media_type not in ("movie", "movies") and not TraktClient._result_has_collection_change(result, "add"):
                payload = TraktClient._build_show_collection_season_payload(ids)
                if payload is not None:
                    result = TraktAPI().lists.add_to_collection(media_type, ids, payload=payload)
            if media_type not in ("movie", "movies") and not TraktClient._result_has_collection_change(result, "add"):
                payload = TraktClient._build_show_collection_episode_payload(ids)
                if payload is not None:
                    result = TraktAPI().lists.add_to_collection(media_type, ids, payload=payload)
            added_count = TraktClient._trakt_sync_result_count(result, "added", media_type)
            existing_count = TraktClient._trakt_sync_result_count(result, "existing", media_type)
            not_found_count = TraktClient._trakt_sync_result_count(result, "not_found", media_type)
            if added_count > 0 or existing_count > 0:
                notification(translation(90441), time=3000)
                refresh()
            elif not_found_count > 0:
                notification(translation(90463), time=3500)
            else:
                notification(translation(90464), time=3500)
        except Exception as e:
            kodilog(f"Error adding to Trakt collection: {e}")
            notification(translation(90443), time=3000)

    @staticmethod
    def trakt_remove_from_collection(params):
        ids = json.loads(params.get("ids", "{}"))
        media_type = TraktClient._normalize_trakt_media_type(
            params.get("media_type"), ids
        )
        try:
            payload = None
            if media_type not in ("movie", "movies"):
                payload = TraktAPI().lists.build_collection_remove_payload(media_type, ids)
                if payload is None:
                    payload = TraktClient._build_show_collection_payload(ids)
                if payload is None:
                    notification(translation(90465), time=3500)
                    return
            result = TraktAPI().lists.remove_from_collection(media_type, ids, payload=payload)
            if media_type not in ("movie", "movies") and not TraktClient._result_has_collection_change(result, "remove"):
                payload = TraktClient._build_show_collection_season_payload(ids)
                if payload is not None:
                    result = TraktAPI().lists.remove_from_collection(media_type, ids, payload=payload)
            if media_type not in ("movie", "movies") and not TraktClient._result_has_collection_change(result, "remove"):
                payload = TraktClient._build_show_collection_episode_payload(ids)
                if payload is not None:
                    result = TraktAPI().lists.remove_from_collection(media_type, ids, payload=payload)
            removed_count = TraktClient._trakt_sync_result_count(result, "deleted", media_type)
            not_found_count = TraktClient._trakt_sync_result_count(result, "not_found", media_type)
            if removed_count > 0:
                notification(translation(90442), time=3000)
                refresh()
            elif not_found_count > 0:
                notification(translation(90462), time=3500)
            else:
                notification(translation(90464), time=3500)
        except Exception as e:
            kodilog(f"Error removing from Trakt collection: {e}")
            notification(translation(90444), time=3000)

    @staticmethod
    def trakt_add_to_favorites(params):
        ids = json.loads(params.get("ids", "{}"))
        media_type = TraktClient._normalize_trakt_media_type(
            params.get("media_type"), ids
        )
        try:
            TraktAPI().lists.add_to_favorites(media_type, ids)
            notification(translation(90445), time=3000)
            refresh()
        except Exception as e:
            kodilog(f"Error adding to Trakt favorites: {e}")
            notification(translation(90447), time=3000)

    @staticmethod
    def trakt_remove_from_favorites(params):
        ids = json.loads(params.get("ids", "{}"))
        media_type = TraktClient._normalize_trakt_media_type(
            params.get("media_type"), ids
        )
        try:
            TraktAPI().lists.remove_from_favorites(media_type, ids)
            notification(translation(90446), time=3000)
            refresh()
        except Exception as e:
            kodilog(f"Error removing from Trakt favorites: {e}")
            notification(translation(90448), time=3000)

    @staticmethod
    def trakt_create_list(params):
        name = show_keyboard(id=30924, default="")
        if not name:
            return

        description = show_keyboard(id=30925, default="") or ""
        try:
            TraktAPI().lists.create_list(name=name, description=description)
            notification(translation(90449), time=3000)
            refresh()
        except Exception as e:
            kodilog(f"Error creating Trakt list: {e}")
            notification(translation(90450), time=3000)

    @staticmethod
    def trakt_delete_list(params):
        trakt_id = params.get("trakt_id")
        if not trakt_id:
            return
        if not dialogyesno(translation(90645), translation(90466)):
            return
        try:
            TraktAPI().lists.delete_list(trakt_id)
            notification(translation(90451), time=3000)
            refresh()
        except Exception as e:
            kodilog(f"Error deleting Trakt list: {e}")
            notification(translation(90452), time=3000)

    @staticmethod
    def trakt_like_list(params):
        trakt_id = params.get("trakt_id")
        user_slug = _normalize_user_slug(params.get("user"))
        if not trakt_id:
            return
        try:
            TraktAPI().lists.like_list(user_slug, trakt_id)
            notification(translation(90453), time=3000)
            TraktClient._refresh_after_list_action(params)
        except Exception as e:
            kodilog(f"Error liking Trakt list: {e}")
            notification(translation(90454), time=3000)

    @staticmethod
    def trakt_unlike_list(params):
        trakt_id = params.get("trakt_id")
        user_slug = _normalize_user_slug(params.get("user"))
        if not trakt_id:
            return
        try:
            TraktAPI().lists.unlike_list(user_slug, trakt_id)
            notification(translation(90455), time=3000)
            TraktClient._refresh_after_list_action(params)
        except Exception as e:
            kodilog(f"Error unliking Trakt list: {e}")
            notification(translation(90456), time=3000)

    @staticmethod
    def _select_trakt_list():
        my_lists = TraktAPI().lists.trakt_get_lists("my_lists") or []
        if not my_lists:
            notification(translation(90461), time=3000)
            return None

        options = [item.get("name", translation(90535)) for item in my_lists]
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
            notification(translation(90457), time=3000)
        except Exception as e:
            kodilog(f"Error adding item to Trakt list: {e}")
            notification(translation(90459), time=3000)

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
            notification(translation(90536), time=3000)
        except Exception as e:
            kodilog(f"Error removing item from Trakt list: {e}")
            notification(translation(90537), time=3000)

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
            end_of_directory(cache=False)
            return

        if not results:
            if query == Trakt.SEARCH_LISTS and not search_term:
                end_of_directory(cache=False)
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
                results, TraktPresentation.show_collection, mode
            ),
            Trakt.CALENDAR: lambda: execute_thread_pool(
                results, TraktPresentation.show_calendar_items
            ),
            Trakt.UP_NEXT: lambda: execute_thread_pool(
                results, TraktPresentation.show_up_next_items
            ),
            Trakt.MOVIES_PROGRESS: lambda: execute_thread_pool(
                results, TraktPresentation.show_movies_progress_items
            ),
            Trakt.FAVORITES: lambda: execute_thread_pool(
                results, TraktPresentation.show_favorites, mode
            ),
            Trakt.MY_LISTS: lambda: execute_thread_pool(
                results,
                TraktPresentation.show_user_lists,
                mode,
                query=query,
                page=page,
                search_term=search_term,
                api=api,
                category=category,
                submode=submode,
            ),
            Trakt.LIKED_LISTS: lambda: execute_thread_pool(
                results,
                TraktPresentation.show_user_lists,
                mode,
                query=query,
                page=page,
                search_term=search_term,
                api=api,
                category=category,
                submode=submode,
            ),
            Trakt.SEARCH_LISTS: lambda: execute_thread_pool(
                results,
                TraktPresentation.show_user_lists,
                mode,
                query=query,
                page=page,
                search_term=search_term,
                api=api,
                category=category,
                submode=submode,
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
        end_of_directory(cache=TraktClient._should_cache_directory(query))

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
    def _should_cache_directory(query):
        non_cached_queries = {
            Trakt.WATCHLIST,
            Trakt.WATCHED_HISTORY,
            Trakt.CALENDAR,
            Trakt.UP_NEXT,
            Trakt.COLLECTION,
            Trakt.FAVORITES,
            Trakt.MY_LISTS,
            Trakt.LIKED_LISTS,
            Trakt.ACCOUNT_INFO,
        }
        return query not in non_cached_queries

    @staticmethod
    def show_trakt_list_content(list_type, mode, user, slug, with_auth, page, trakt_id=None):
        data = TraktAPI().lists.get_trakt_list_contents(
            list_type, user, slug, with_auth, trakt_id
        )
        if not data:
            notification("No results found", time=3000)
            end_of_directory(cache=not bool(with_auth))
            return
        paginator_db.initialize(data)
        items = paginator_db.get_page(page)
        execute_thread_pool(items, TraktPresentation.show_lists_content_items)
        add_next_button("list_trakt_page", page, mode=mode)
        end_of_directory(cache=not bool(with_auth))

    @staticmethod
    def show_list_trakt_page(page, mode):
        items = paginator_db.get_page(page)
        execute_thread_pool(items, TraktPresentation.show_lists_content_items)
        add_next_button("list_trakt_page", page, mode=mode)
        end_of_directory()


class TraktPresentation:
    @staticmethod
    def _format_bool_label(value):
        return "Yes" if value else "No"

    @staticmethod
    def _format_iso_date(value):
        if not value:
            return ""
        if "T" in str(value):
            return str(value).split("T")[0]
        return str(value)

    @staticmethod
    def _resolve_media_ids(mode, media_ids):
        tmdb_id = media_ids.get("tmdb") or media_ids.get("tmdb_id")
        imdb_id = media_ids.get("imdb") or media_ids.get("imdb_id", "")
        tvdb_id = media_ids.get("tvdb") or media_ids.get("tvdb_id", "")

        if mode == "tv":
            if not tmdb_id and imdb_id:
                found = tmdb_get("find_by_imdb_id", imdb_id)
                if getattr(found, "tv_results", []):
                    tmdb_id = str(found.tv_results[0]["id"])
            if not tmdb_id and tvdb_id:
                found = tmdb_get("find_by_tvdb", tvdb_id)
                if getattr(found, "tv_results", []):
                    tmdb_id = str(found.tv_results[0]["id"])
        else:
            if not tmdb_id and imdb_id:
                found = tmdb_get("find_by_imdb_id", imdb_id)
                if getattr(found, "movie_results", []):
                    tmdb_id = str(found.movie_results[0]["id"])

        return {"tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id}

    @staticmethod
    def show_create_list_entry(mode):
        list_item = make_list_item(label=f"[B]+ {translation(30926)}[/B]")
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
        lines.append(
            f"Joined: {TraktPresentation._format_iso_date(user.get('joined_at', ''))}"
        )
        lines.append(
            f"Private: {TraktPresentation._format_bool_label(account.get('private', False))}"
        )
        lines.append(
            f"VIP: {TraktPresentation._format_bool_label(user.get('vip', False))}"
        )
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
        lines.append(f"Ratings: {stats.get('ratings', {}).get('total', 0)}")
        lines.append("")
        lines.append("Connections")
        for key in ("facebook", "google", "twitter", "mastodon"):
            connection = connections.get(key, False)
            lines.append(
                f"{key.title()}: {TraktPresentation._format_bool_label(bool(connection))}"
            )
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

        list_item = make_list_item(label=title)
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

        list_item = make_list_item(label=title)
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
        ids = TraktPresentation._resolve_media_ids(mode, res["media_ids"])
        tmdb_id = ids["tmdb_id"]
        if not tmdb_id:
            return

        if mode == "tv":
            details = tmdb_get("tv_details", tmdb_id)
        else:
            details = tmdb_get("movie_details", tmdb_id)

        list_item = make_list_item(label=title)
        set_media_infoTag(list_item, data=details, mode=mode)

        BaseTraktClient._add_media_directory_item(
            list_item=list_item,
            mode=mode,
            title=title,
            ids=ids,
            media_type=res.get("media_type"),
            context_flags=BaseTraktClient._exclusive_context_flags("watchlist"),
        )

    @staticmethod
    def show_favorites(res, mode):
        title = res["title"]
        ids = TraktPresentation._resolve_media_ids(mode, res["media_ids"])
        tmdb_id = ids["tmdb_id"]
        if not tmdb_id:
            return

        if mode == "tv":
            details = tmdb_get("tv_details", tmdb_id)
        else:
            details = tmdb_get("movie_details", tmdb_id)

        list_item = make_list_item(label=title)
        set_media_infoTag(list_item, data=details, mode=mode)

        BaseTraktClient._add_media_directory_item(
            list_item=list_item,
            mode=mode,
            title=title,
            ids=ids,
            media_type=res.get("media_type"),
            context_flags=BaseTraktClient._exclusive_context_flags("favorites"),
        )

    @staticmethod
    def show_collection(res, mode):
        if mode == "tv":
            title = res["show"]["title"]
            ids = TraktPresentation._resolve_media_ids(mode, res["show"].get("ids", {}))
            tmdb_id = ids["tmdb_id"]
            if not tmdb_id:
                return
            details = tmdb_get("tv_details", tmdb_id)
        else:
            title = res["movie"]["title"]
            ids = TraktPresentation._resolve_media_ids(mode, res["movie"].get("ids", {}))
            tmdb_id = ids["tmdb_id"]
            if not tmdb_id:
                return
            details = tmdb_get("movie_details", tmdb_id)

        list_item = make_list_item(label=title)
        set_media_infoTag(list_item, data=details, mode=mode)

        BaseTraktClient._add_media_directory_item(
            list_item=list_item,
            mode=mode,
            title=title,
            ids=ids,
            media_type=res.get("media_type"),
            context_flags=BaseTraktClient._exclusive_context_flags("collection"),
        )

    @staticmethod
    def show_trending_lists(res, mode):
        list_title = res["list"]["name"]
        description = res["list"]["description"]
        user_data = res["list"].get("user", {})
        user_ids = user_data.get("ids", {})
        user_slug = _normalize_user_slug(
            user_ids.get("slug") or user_data.get("username")
        )

        info_labels = {
            "title": list_title,
            "plot": description,
        }

        url = build_url(
            "trakt_list_content",
            list_type=res["list"]["type"],
            mode=mode,
            user=user_slug,
            slug=res["list"]["ids"]["slug"],
        )

        list_item = make_list_item(label=list_title)
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(list_title)
        info_tag.setPlot(truncate_text(description))
        if user_slug:
            list_item.addContextMenuItems(
                [
                    (
                        "Like Trakt List",
                        action_url_run(
                            "trakt_like_list",
                            trakt_id=res["list"]["ids"].get("trakt"),
                            user=user_slug,
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
    def show_user_lists(res, mode, query=None, page=1, search_term="", api="trakt", category=None, submode=""):
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

        list_item = make_list_item(label=label)
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(list_title)
        info_tag.setPlot(truncate_text(description))

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
                        query=query,
                        category=category,
                        mode=mode,
                        submode=submode,
                        api=api,
                        page=page,
                        search_term=search_term,
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
                        query=query,
                        category=category,
                        mode=mode,
                        submode=submode,
                        api=api,
                        page=page,
                        search_term=search_term,
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

        list_item = make_list_item(label=title)
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
        title = res["title"]

        if res["type"] == "show":
            mode = "tv"
            ids = TraktPresentation._resolve_media_ids(mode, res["media_ids"])
            tmdb_id = ids["tmdb_id"]
            if not tmdb_id:
                return
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
            ids = TraktPresentation._resolve_media_ids(mode, res["media_ids"])
            tmdb_id = ids["tmdb_id"]
            if not tmdb_id:
                return
            details = tmdb_get("movie_details", tmdb_id)
            url = build_url(
                "search",
                query=title,
                mode=mode,
                ids=ids,
            )
            is_folder = False
            is_playable = True

        list_item = make_list_item(label=title)
        set_media_infoTag(list_item, data=details, mode=mode)
        list_item.addContextMenuItems(
            BaseTraktClient._trakt_context_menu(
                mode,
                ids,
                context_flags=BaseTraktClient._exclusive_context_flags("watched"),
            )
        )

        add_kodi_dir_item(
            list_item,
            url=url,
            is_folder=is_folder,
            is_playable=is_playable,
        )

    @staticmethod
    def show_lists_content_items(res):
        title = res["title"]

        if res["type"] == "show":
            mode = "tv"
            ids = TraktPresentation._resolve_media_ids(mode, res.get("media_ids", {}))
            tmdb_id = ids["tmdb_id"]
            if not tmdb_id:
                return
            details = tmdb_get("tv_details", tmdb_id)
        else:
            mode = "movies"
            ids = TraktPresentation._resolve_media_ids(mode, res.get("media_ids", {}))
            tmdb_id = ids["tmdb_id"]
            if not tmdb_id:
                return
            details = tmdb_get("movie_details", tmdb_id)

        list_item = make_list_item(label=title)
        set_media_infoTag(list_item, data=details, mode=mode)

        BaseTraktClient._add_media_directory_item(
            list_item=list_item,
            mode=mode,
            title=title,
            ids=ids,
            media_type=res.get("media_type"),
            context_flags=BaseTraktClient._exclusive_context_flags("custom_list"),
        )

    @staticmethod
    def show_calendar_items(res):
        show_title = res.get("show", {}).get("title")
        ep_data = res.get("episode", {})
        title = ep_data.get("title")
        season = ep_data.get("season")
        episode = ep_data.get("number")
        if not show_title or not title or season is None or episode is None:
            return

        first_aired = res.get("first_aired") or ep_data.get("first_aired")

        ids = TraktPresentation._resolve_media_ids(
            "tv", res.get("show", {}).get("ids", {})
        )
        tmdb_id = ids["tmdb_id"]
        imdb_id = ids["imdb_id"]
        tvdb_id = ids["tvdb_id"]

        if not tmdb_id:
            return

        display_title = f"{show_title} - S{int(season):02d}E{int(episode):02d} - {title}"
        if first_aired:
            date_part = first_aired.split("T")[0]
            display_title = f"{date_part} | {display_title}"

        details = tmdb_get("tv_details", tmdb_id) or {}

        list_item = make_list_item(label=display_title)
        set_media_infoTag(list_item, data=details, mode="tv")

        # Override title
        list_item.setLabel(display_title)
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(display_title)
        info_tag.setPlot(truncate_text(details.get("overview", "")))

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

        list_item = make_list_item(label=display_title)
        set_media_infoTag(list_item, data=details, mode="tv")
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(display_title)
        info_tag.setPlot(truncate_text(details.get("overview", "")))
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

    @staticmethod
    def show_movies_progress_items(res):
        movie_data = res.get("movie", {})
        title = movie_data.get("title", "")
        progress = res.get("progress", 0)
        tmdb_id = movie_data.get("ids", {}).get("tmdb")
        imdb_id = movie_data.get("ids", {}).get("imdb")

        if not tmdb_id:
            return

        display_title = f"[Resume] {title}"
        if progress:
            display_title = f"{display_title} ({int(progress)}%)"

        ids = {"tmdb_id": tmdb_id, "imdb_id": imdb_id}
        details = tmdb_get("movie_details", tmdb_id) or {}

        list_item = make_list_item(label=display_title)
        set_media_infoTag(list_item, data=details, mode="movies")
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(display_title)
        info_tag.setPlot(truncate_text(details.get("overview", "")))
        if progress:
            list_item.setProperty("PercentPlayed", str(progress))

        url = build_url(
            "search",
            ids=ids,
            mode="movies",
            query=title,
        )

        add_kodi_dir_item(list_item=list_item, url=url, is_folder=True)
