from datetime import datetime
import json
import os
from lib.api.tmdbv3api.as_obj import AsObj
from lib.api.trakt.trakt_utils import (
    add_trakt_watched_context_menu,
    add_trakt_watchlist_context_menu,
    is_trakt_auth,
)
from lib.clients.tmdb.collections_utils import (
    POPULAR_COLLECTIONS,
    TOP_RATED_COLLECTIONS,
)
from lib.clients.tmdb.utils import (
    FULL_NAME_LANGUAGES,
    NETWORKS,
    add_kodi_dir_item,
    add_tmdb_movie_context_menu,
    add_tmdb_show_context_menu,
    get_tmdb_movie_details,
    get_tmdb_show_details,
    tmdb_get,
)
from lib.api.tmdbv3api.objs.search import Search
from lib.api.tmdbv3api.objs.movie import Movie
from lib.api.tmdbv3api.objs.tv import TV

from lib.utils.general.utils import (
    Animation,
    Anime,
    Cartoons,
    add_next_button,
    execute_thread_pool,
    set_content_type,
    set_media_infoTag,
    set_pluging_category,
    translate_weekday,
)

from lib.api.tmdbv3api.objs.anime import TmdbAnime
from lib.db.pickle_db import PickleDatabase
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    build_url,
    kodilog,
    set_view,
    show_keyboard,
    notification,
    translation,
)

from lib.utils.views.weekly_calendar import is_this_week, parse_date_str
from lib.utils.views.weekly_calendar import get_episodes_for_show

from xbmcgui import ListItem
from xbmcplugin import endOfDirectory
import xbmc


pickle_db = PickleDatabase()


class BaseTmdbClient:
    @staticmethod
    def _add_media_directory_item(list_item, mode, title, ids, media_type=None):
        if mode == "movies":
            context_menu = add_tmdb_movie_context_menu(mode, title=title, ids=ids)
            if is_trakt_auth():
                context_menu += add_trakt_watchlist_context_menu(
                    "movies", ids
                ) + add_trakt_watched_context_menu("movies", ids=ids)
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
                set_playable=True,
            )
        else:
            context_menu = add_tmdb_show_context_menu(mode, ids=ids)
            if is_trakt_auth():
                context_menu += add_trakt_watchlist_context_menu(
                    "shows", ids
                ) + add_trakt_watched_context_menu("shows", ids=ids)
            list_item.addContextMenuItems(context_menu)
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


class TmdbClient(BaseTmdbClient):
    @staticmethod
    def handle_tmdb_search(params):
        set_pluging_category(translation(90006))
        mode = params.get("mode")
        set_content_type(mode)

        page = int(params.get("page", 1))

        query = (
            show_keyboard(id=30241) if page == 1 else pickle_db.get_key("search_query")
        )
        if not query:
            return

        if page == 1:
            pickle_db.set_key("search_query", query)

        data = tmdb_get("search_multi", {"query": query, "page": page})
        kodilog(f"TMDB Search Results: {data}", level=xbmc.LOGDEBUG)
        if not data or getattr(data, "total_results", 0) == 0:
            notification("No results found")
            return

        results = getattr(data, "results", [])
        if results:
            execute_thread_pool(results, TmdbClient.show_tmdb_results, mode)
            add_next_button("handle_tmdb_search", page=page, mode=mode)

        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def handle_tmdb_query(params):
        query = params.get("query", "")
        mode = params.get("mode")
        submode = params.get("submode")
        category = params.get("category")
        page = int(params.get("page", 1))

        handlers = {
            "movies": lambda: TmdbClient.handle_tmdb_movie_query(query, page, mode),
            "tv": lambda: TmdbClient.handle_tmdb_show_query(query, page, mode),
        }

        anime_modes = {"anime", "cartoon", "animation"}
        if mode in anime_modes:
            handlers[mode] = lambda: TmdbAnimeClient.handle_tmdb_anime_query(
                category, mode, submode, page
            )

        handler = handlers.get(mode)
        if handler:
            return handler()
        else:
            notification("Invalid mode")

    @staticmethod
    def handle_tmdb_movie_query(query, page, mode):
        query_handlers = {
            "tmdb_trending": lambda: TmdbClient.show_trending_movies(mode, page),
            "tmdb_genres": lambda: TmdbClient.show_genres_items(mode, page),
            "tmdb_popular": lambda: TmdbClient.show_popular_items(mode, page),
            "tmdb_years": lambda: TmdbClient.show_years_items(mode, page),
            "tmdb_lang": lambda: TmdbClient.show_languages(mode, page),
            "tmdb_collections": lambda: TmdbClient.show_collections_menu(mode),
            "tmdb_keywords": lambda: TmdbClient.show_keywords_items(query, page, mode),
        }

        handler = query_handlers.get(query)
        if handler:
            handler()
        else:
            notification("Invalid query")

    @staticmethod
    def handle_tmdb_show_query(query, page, mode):
        query_handlers = {
            "tmdb_trending": lambda: TmdbClient.show_trending_shows(query, mode, page),
            "tmdb_popular": lambda: TmdbClient.show_popular_items(mode, page),
            "tmdb_lang": lambda: TmdbClient.show_languages(mode, page),
            "tmdb_genres": lambda: TmdbClient.show_genres_items(mode, page),
            "tmdb_calendar": lambda: TmdbClient.show_calendar_items(query, page, mode),
            "tmdb_years": lambda: TmdbClient.show_years_items(mode, page),
            "tmdb_networks": lambda: TmdbClient.show_networks(mode, page),
        }

        handler = query_handlers.get(query)
        if handler:
            return handler()
        else:
            notification("Invalid query")

    @staticmethod
    def tmdb_search_genres(mode, genre_id, page, submode=None):
        path_map = {
            "movies": "discover_movie",
            "tv": "discover_tv",
            "anime": "anime_genres",
        }
        params_map = {
            "movies": {
                "with_genres": genre_id,
                "append_to_response": "external_ids",
                "page": page,
            },
            "tv": {"with_genres": genre_id, "page": page},
            "anime": {"mode": submode, "genre_id": genre_id, "page": page},
        }

        path = path_map.get(mode)
        params = params_map.get(mode)

        if not path or not params:
            notification("Invalid mode")
            return

        data = tmdb_get(path=path, params=params)

        if not data or getattr(data, "total_results", 0) == 0:
            notification("No results found")
            return

        execute_thread_pool(
            getattr(data, "results"), TmdbClient.show_tmdb_results, mode, submode
        )

        add_next_button(
            "search_tmdb_genres",
            mode=mode,
            submode=submode,
            genre_id=genre_id,
            page=page,
        )
        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def tmdb_search_year(mode, submode, year, page):
        set_pluging_category(str(year))
        path_map = {
            "movies": "discover_movie",
            "tv": "discover_tv",
            "anime": "anime_year",
        }
        params_map = {
            "movies": {"primary_release_year": year, "page": page},
            "tv": {"first_air_date_year": year, "page": page},
            "anime": {"mode": submode, "year": year, "page": page},
        }

        path = path_map.get(mode)
        params = params_map.get(mode)

        if not path or not params:
            notification("Invalid mode")
            return

        results = tmdb_get(path=path, params=params)
        if not results:
            return

        if getattr(results, "total_results", 0) == 0:
            notification("No results found")
            return

        execute_thread_pool(
            getattr(results, "results"), TmdbClient.show_tmdb_results, mode, submode
        )

        add_next_button(
            "search_tmdb_year", page=page, mode=mode, submode=submode, year=year
        )
        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def show_tmdb_results(res, mode, submode=None):
        tmdb_id = getattr(res, "id", "")
        media_type = res.get("media_type", "") if hasattr(res, "get") else ""

        # Adjust mode for anime
        if mode == "anime":
            mode = submode

        result = TmdbClient._get_tmdb_result_metadata(res, mode, media_type, tmdb_id)
        if result is None:
            return
        title, label_title, mode, ids = result

        list_item = ListItem(label=label_title)
        set_media_infoTag(list_item, metadata=res, mode=mode)

        TmdbClient._add_media_directory_item(list_item, mode, title, ids, media_type)

    @staticmethod
    def _get_tmdb_result_metadata(res, mode, media_type, tmdb_id):
        imdb_id = tvdb_id = ""
        title = label_title = ""

        if mode == "movies":
            title = getattr(res, "title", "")
            label_title = title
            movie_details = get_tmdb_movie_details(tmdb_id)
            if movie_details:
                setattr(res, "runtime", movie_details.get("runtime"))
                setattr(res, "casts", movie_details.get("casts"))
                imdb_id = getattr(movie_details, "external_ids").get("imdb_id", "")
        elif mode == "tv":
            title = getattr(res, "name", "")
            label_title = title
            show_details = get_tmdb_show_details(tmdb_id)
            if show_details:
                external_ids = getattr(show_details, "external_ids")
                setattr(res, "casts", getattr(show_details, "credits").get("cast", []))
                imdb_id = external_ids.get("imdb_id", "")
                tvdb_id = external_ids.get("tvdb_id", "")
        elif mode == "multi":
            title = getattr(res, "name", "") or getattr(res, "title", "")
            if media_type == "movie":
                mode = "movies"
                movie_details = get_tmdb_movie_details(tmdb_id)
                if movie_details:
                    setattr(res, "runtime", movie_details.get("runtime"))
                    setattr(res, "casts", movie_details.get("casts"))
                    imdb_id = getattr(movie_details, "external_ids").get("imdb_id", "")
                label_title = f"[B]MOVIE -[/B] {title}"
            elif media_type == "tv":
                mode = "tv"
                show_details = get_tmdb_show_details(tmdb_id)
                if show_details:
                    external_ids = getattr(show_details, "external_ids")
                    setattr(
                        res, "casts", getattr(show_details, "credits").get("cast", [])
                    )
                    imdb_id = external_ids.get("imdb_id", "")
                    tvdb_id = external_ids.get("tvdb_id", "")
                label_title = f"[B]TV -[/B] {title}"
            else:
                kodilog(f"Invalid media type: {media_type}", level=xbmc.LOGERROR)
                return None

        ids = {"tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id}
        return title, label_title, mode, ids

    @staticmethod
    def show_years_items(mode, page, submode=None):
        set_pluging_category(translation(90027))
        current_year = datetime.now().year
        for year in range(current_year, 1899, -1):
            list_item = ListItem(label=str(year))
            add_kodi_dir_item(
                list_item=list_item,
                url=build_url(
                    "search_tmdb_year",
                    mode=mode,
                    submode=submode,
                    year=year,
                    page=page,
                ),
                is_folder=True,
                icon_path="status.png",
            )
        endOfDirectory(ADDON_HANDLE)
        set_view("widelist")

    @staticmethod
    def show_trending_shows(query, mode, page):
        set_pluging_category(translation(90028))
        set_content_type(mode)
        data = tmdb_get("trending_tv", page)
        if not data or getattr(data, "total_results", 0) == 0:
            notification("No results found")
            return
        execute_thread_pool(
            getattr(data, "results"), TmdbClient.show_tmdb_results, mode
        )
        add_next_button("handle_tmdb_query", query=query, page=page, mode=mode)
        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def show_trending_movies(mode, page):
        set_pluging_category(translation(90028))
        set_content_type(mode)
        data = tmdb_get("trending_movie", page)
        if not data or getattr(data, "total_results", 0) == 0:
            notification("No results found")
            return
        execute_thread_pool(
            getattr(data, "results"), TmdbClient.show_tmdb_results, mode
        )
        add_next_button(
            "handle_tmdb_query", query="tmdb_trending", page=page, mode=mode
        )
        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def show_popular_items(mode, page):
        set_pluging_category(translation(90037))
        set_content_type(mode)
        path = "popular_shows" if mode == "tv" else "popular_movie"
        data = tmdb_get(path, page)
        if not data or getattr(data, "total_results", 0) == 0:
            notification("No results found")
            return
        execute_thread_pool(
            getattr(data, "results"), TmdbClient.show_tmdb_results, mode
        )
        add_next_button("handle_tmdb_query", query="tmdb_popular", page=page, mode=mode)
        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def show_languages(mode, page):
        set_pluging_category(translation(90065))
        for lang in FULL_NAME_LANGUAGES:
            list_item = ListItem(label=lang["name"])
            list_item.setArt(
                {
                    "icon": os.path.join(ADDON_PATH, "resources", "img", "lang.png"),
                }
            )
            add_kodi_dir_item(
                list_item=list_item,
                url=build_url(
                    "search_tmdb_lang",
                    mode=mode,
                    lang=lang["id"],
                    page=page,
                ),
            )
        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def show_lang_items(params):
        lang = params.get("lang")
        set_pluging_category(lang)

        mode = params.get("mode")
        set_content_type(mode)
        page = int(params.get("page", 1))

        route_map = {
            "movies": "discover_movie",
            "tv": "discover_tv",
        }

        path = route_map.get(mode)
        if not path:
            notification("Invalid mode")
            return

        route_params = {"with_original_language": lang, "page": page}

        data = tmdb_get(path=path, params=route_params)
        if not data or getattr(data, "total_results", 0) == 0:
            notification("No results found")
            return

        execute_thread_pool(
            getattr(data, "results"), TmdbClient.show_tmdb_results, mode
        )

        add_next_button(
            "search_tmdb_lang",
            mode=mode,
            lang=lang,
            page=page,
        )
        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def show_networks(mode, page):
        set_pluging_category(translation(90066))
        for network in NETWORKS:
            list_item = ListItem(label=network["name"])
            list_item.setArt(
                {
                    "icon": network["icon"],
                    "thumb": network["icon"],
                    "poster": network["icon"],
                }
            )
            add_kodi_dir_item(
                list_item=list_item,
                url=build_url(
                    "search_tmbd_network",
                    mode=mode,
                    id=network["id"],
                    page=page,
                ),
            )
        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def show_network_items(params):
        network_id = int(params.get("id"))
        network_name = next(
            (net["name"] for net in NETWORKS if net["id"] == network_id), ""
        )
        set_pluging_category(network_name)

        mode = params.get("mode")
        set_content_type(mode)

        page = int(params.get("page", 1))

        route_map = {
            "movies": "discover_movie",
            "tv": "discover_tv",
        }

        path = route_map.get(mode)
        if not path:
            notification("Invalid mode")
            return

        route_params = {"page": page}
        if mode == "tv":
            route_params["with_networks"] = network_id
        elif mode == "movies":
            route_params["with_companies"] = network_id

        data = tmdb_get(path=path, params=route_params)
        if not data or getattr(data, "total_results", 0) == 0:
            notification("No results found")
            return

        execute_thread_pool(
            getattr(data, "results"), TmdbClient.show_tmdb_results, mode
        )

        add_next_button(
            "search_tmbd_network",
            mode=mode,
            id=network_id,
            page=page,
        )
        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def show_genres_items(mode, page, submode=None):
        set_pluging_category(translation(90025))
        path = (
            "show_genres"
            if mode == "tv" or (mode == "anime" and submode == "tv")
            else "movie_genres"
        )
        genres = tmdb_get(path=path)
        if genres is None or len(genres) == 0:
            notification("No genres found")
            endOfDirectory(ADDON_HANDLE)
            return

        for genre in genres:
            if isinstance(genre, AsObj):
                if genre.get("name") == "TV Movie":
                    continue
                list_item = ListItem(label=genre["name"])
                add_kodi_dir_item(
                    list_item=list_item,
                    url=build_url(
                        "search_tmdb_genres",
                        mode=mode,
                        submode=submode,
                        genre_id=genre["id"],
                        page=page,
                    ),
                    is_folder=True,
                    icon_path=None,
                )
        endOfDirectory(ADDON_HANDLE)
        set_view("widelist")

    @staticmethod
    def show_calendar_items(query, page, mode):
        set_pluging_category(translation(90021))
        trending_data = tmdb_get("tv_week", page)
        if not trending_data or getattr(trending_data, "total_results") == 0:
            notification("No TV shows found")
            endOfDirectory(ADDON_HANDLE)
            return

        results = []

        def fetch_episodes_for_trending_show(show):
            tmdb_id = getattr(show, "id", None)
            if not tmdb_id:
                return
            ids = {"tmdb_id": tmdb_id}
            episodes, details = get_episodes_for_show(ids)
            for ep in episodes:
                air_date = ep.get("air_date")
                if air_date and is_this_week(air_date):
                    results.append((getattr(show, "name", ""), show, ep, details))

        execute_thread_pool(
            getattr(trending_data, "results"), fetch_episodes_for_trending_show
        )

        # Add fixed item showing current date at the top
        current_date = datetime.now().strftime("%A, %d %B %Y")
        date_item = ListItem(
            label=f"[UPPERCASE][COLOR=orange]Today: {current_date}[/COLOR][/UPPERCASE]"
        )
        date_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "history.png")}
        )
        add_kodi_dir_item(date_item, "", is_folder=False)

        today_str = datetime.now().strftime("%Y-%m-%d")

        results_today = [r for r in results if r[2].get("air_date") == today_str]
        results_other = [r for r in results if r[2].get("air_date") != today_str]

        results = sorted(
            results_today, key=lambda x: x[2].get("air_date", "")
        ) + sorted(results_other, key=lambda x: x[2].get("air_date", ""))

        for title, show, ep, details in results:
            tv_data = {"name": title, "episode": ep["number"], "season": ep["season"]}

            air_date_obj = parse_date_str(ep["air_date"])
            weekday_name = air_date_obj.strftime("%A")
            weekday_name_translated = translate_weekday(weekday_name)

            # Mark if episode is released today
            is_today = ep["air_date"] == today_str
            mark = (
                f"[UPPERCASE][COLOR=orange]TODAY- [/COLOR][/UPPERCASE]"
                if is_today
                else ""
            )

            ep_title = f"{mark}{weekday_name_translated} - ({ep['air_date']}) - {title} - S{ep['season']:02}E{ep['number']:02}"

            tmdb_id = getattr(show, "id")
            show_details = get_tmdb_show_details(tmdb_id)
            if show_details is None:
                kodilog(f"Show details not found for TMDB ID: {tmdb_id}")
                continue

            external_ids = getattr(show_details, "external_ids")
            imdb_id = external_ids.get("imdb_id", "")
            tvdb_id = external_ids.get("tvdb_id", "")

            ids = {"tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id}

            list_item = ListItem(label=ep_title)
            list_item.setProperty("IsPlayable", "true")

            set_media_infoTag(list_item, metadata=details, mode="tv")

            add_kodi_dir_item(
                list_item=list_item,
                url=build_url(
                    "search",
                    mode="tv",
                    media_type="tv",
                    query=title,
                    ids=ids,
                    tv_data=tv_data,
                ),
                is_folder=False,
            )

        if getattr(trending_data, "total_pages", 0) > page:
            add_next_button(
                "handle_tmdb_query",
                query=query,
                page=page + 1,
                mode=mode,
            )
        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def show_collections_menu(mode):
        set_pluging_category(translation(90067))
        collections_menu = [
            ("Search Collections", "search", "search.png"),
            ("Popular Collections", "popular", "tmdb.png"),
            ("Top Rated Collections", "top_rated", "tmdb.png"),
        ]

        for label, submode, icon_path in collections_menu:
            list_item = ListItem(label=label)
            add_kodi_dir_item(
                list_item=list_item,
                url=build_url(
                    "handle_collection_query",
                    mode=mode,
                    submode=submode,
                    page=1,
                ),
                is_folder=True,
                icon_path=icon_path,
            )
        endOfDirectory(ADDON_HANDLE)
        set_view("widelist")

    @staticmethod
    def handle_collection_query(params):
        mode = params.get("mode")
        submode = params.get("submode")
        page = int(params.get("page", 1))

        set_content_type(mode)

        if submode == "popular":
            TmdbCollections.get_popular_collections(mode, page)
        elif submode == "top_rated":
            TmdbCollections.get_top_rated_collections(mode, page)
        elif submode == "search":
            TmdbCollections.search_collections(mode, page)
        else:
            notification("Invalid collection query")

    @staticmethod
    def show_keywords_items(query, page, mode):
        keywords_data = Search().keywords(query, page=page)
        if not keywords_data or len(keywords_data) == 0:
            notification("No keywords found")
            endOfDirectory(ADDON_HANDLE)
            return

        for keyword in keywords_data:
            if isinstance(keyword, AsObj):
                keyword_id = keyword.get("id")
                keyword_name = keyword.get("name")
                if not keyword_id or not keyword_name:
                    continue

                list_item = ListItem(label=keyword_name)
                add_kodi_dir_item(
                    list_item=list_item,
                    url=build_url(
                        "search_tmdb_keywords",
                        mode=mode,
                        keyword_id=keyword_id,
                        page=1,
                    ),
                    is_folder=True,
                    icon_path=None,
                )
        add_next_button(
            "handle_tmdb_movie_query", query="tmdb_keywords", page=page + 1, mode=mode
        )
        endOfDirectory(ADDON_HANDLE)
        set_view("widelist")

    @staticmethod
    def search_tmdb_recommendations(params):
        ids = json.loads(params.get("ids", "{}"))
        mode = params.get("mode", "tv")
        tmdb_id = ids.get("tmdb_id")
        page = int(params.get("page", 1))

        if not tmdb_id:
            notification("No TMDB ID found")
            return

        if mode == "tv":
            results = TV().recommendations(tmdb_id, page=page)
        elif mode == "movies":
            results = Movie().recommendations(tmdb_id, page=page)
        else:
            notification("Invalid mode")
            return

        if not results:
            notification("No recommendations found")
            endOfDirectory(ADDON_HANDLE)
            return

        execute_thread_pool(
            getattr(results, "results"), TmdbClient.show_tmdb_results, mode
        )

        if getattr(results, "total_pages") > page:
            add_next_button(
                "search_tmdb_recommendations",
                ids=ids,
                mode=mode,
                page=page,
            )
        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def search_tmdb_similar(params):
        ids = json.loads(params.get("ids", "{}"))
        mode = params.get("mode", "tv")
        tmdb_id = ids.get("tmdb_id")
        page = int(params.get("page", 1))

        if not tmdb_id:
            notification("No TMDB ID found")
            return

        if mode == "tv":
            results = TV().similar(tmdb_id, page=page)
        elif mode == "movies":
            results = Movie().similar(tmdb_id, page=page)
        else:
            notification("Invalid mode")
            return

        if not results:
            notification("No similar items found")
            endOfDirectory(ADDON_HANDLE)
            return

        execute_thread_pool(
            getattr(results, "results"), TmdbClient.show_tmdb_results, mode
        )

        if getattr(results, "total_pages") > page:
            add_next_button(
                "search_tmdb_similar",
                ids=ids,
                mode=mode,
                page=page,
            )
        endOfDirectory(ADDON_HANDLE)


class TmdbCollections(BaseTmdbClient):
    PAGE_SIZE = 10

    @staticmethod
    def add_collection_details(params):
        collection = tmdb_get("collection_details", params.get("collection_id"))
        if not collection:
            notification("Collection details not found.")
            endOfDirectory(ADDON_HANDLE)
            return

        parts = collection.get("parts", [])
        for movie in parts:
            movie_item = ListItem(label=movie.get("title", "Untitled"))
            set_media_infoTag(movie_item, metadata=movie, mode="movie")

            tmdb_id = movie.get("id")
            imdb_id = ""
            details = get_tmdb_movie_details(tmdb_id)
            if details:
                imdb_id = getattr(details, "external_ids").get("imdb_id", "")

            add_kodi_dir_item(
                list_item=movie_item,
                url=build_url(
                    "search",
                    mode="movies",
                    media_type="movies",
                    query=movie.get("title", "Untitled"),
                    ids={"tmdb_id": tmdb_id, "imdb_id": imdb_id},
                ),
                is_folder=False,
            )

        endOfDirectory(ADDON_HANDLE)
        set_view("widelist")

    @staticmethod
    def _add_collection_item(collection):
        collection_id = collection.get("id")
        images_data = tmdb_get("collection_images", collection_id)
        if images_data:
            posters = images_data.get("posters") or []
            if posters:
                file_path = posters[0].get("file_path")
                collection["poster_path"] = file_path

        list_item = ListItem(label=collection.get("name"))
        set_media_infoTag(list_item, metadata=collection, mode="movies")
        add_kodi_dir_item(
            list_item=list_item,
            url=build_url("handle_collection_details", collection_id=collection_id),
            is_folder=True,
        )

    @staticmethod
    def fetch_and_add_collection(collection_data):
        collection_id = collection_data["id"]
        collection_details = tmdb_get("collection_details", collection_id)
        kodilog(f"Fetching collection details for ID: {collection_details}")
        if collection_details:
            TmdbCollections._add_collection_item(collection_details)

    @staticmethod
    def get_popular_collections(mode, page):
        set_pluging_category(translation(90064))
        kodilog(f"Displaying popular collections, page: {page}")

        start_index = (page - 1) * TmdbCollections.PAGE_SIZE
        end_index = start_index + TmdbCollections.PAGE_SIZE

        current_page_collections = POPULAR_COLLECTIONS[start_index:end_index]

        if not current_page_collections:
            notification("No more popular collections to display.")
            endOfDirectory(ADDON_HANDLE)
            return

        execute_thread_pool(
            current_page_collections, TmdbCollections.fetch_and_add_collection
        )

        # Add "Next" button
        if end_index < len(POPULAR_COLLECTIONS):
            add_next_button(
                "handle_collection_query", submode="popular", page=page + 1, mode=mode
            )

        endOfDirectory(ADDON_HANDLE)
        set_view("widelist")

    @staticmethod
    def get_top_rated_collections(mode, page):
        set_pluging_category(translation(90042))
        kodilog(f"Fetching top rated collections for mode: {mode}, page: {page}")

        start_index = (page - 1) * TmdbCollections.PAGE_SIZE
        end_index = start_index + TmdbCollections.PAGE_SIZE

        current_page_collections = TOP_RATED_COLLECTIONS[start_index:end_index]

        if not current_page_collections:
            notification("No more collections to display.")
            endOfDirectory(ADDON_HANDLE)
            return

        execute_thread_pool(
            current_page_collections, TmdbCollections.fetch_and_add_collection
        )

        # Add "Next" button
        if end_index < len(TOP_RATED_COLLECTIONS):
            add_next_button(
                "handle_collection_query", submode="top_rated", page=page + 1, mode=mode
            )

        endOfDirectory(ADDON_HANDLE)
        set_view("widelist")

    @staticmethod
    def search_collections(mode, page):
        query = (
            show_keyboard(id=90068)
            if page == 1
            else pickle_db.get_key("collection_search_query")
        )
        if not query:
            return

        if page == 1:
            pickle_db.set_key("collection_search_query", query)

        results = tmdb_get("search_collections", params={"query": query, "page": page})
        if not results or getattr(results, "total_results", 0) == 0:
            notification("No results found for your search.")
            endOfDirectory(ADDON_HANDLE)
            return

        execute_thread_pool(
            getattr(results, "results"), TmdbCollections._add_collection_item
        )

        add_next_button(
            "handle_collection_query",
            submode="search",
            query=query,
            page=page + 1,
            mode=mode,
        )
        endOfDirectory(ADDON_HANDLE)
        set_view("widelist")

    @staticmethod
    def _extract_collection_id(movie, collection_ids_set):
        """
        Helper function to extract collection ID from movie details.
        Designed to be used with execute_thread_pool.
        """
        movie_details = get_tmdb_movie_details(getattr(movie, "id"))
        if movie_details and getattr(movie_details, "belongs_to_collection"):
            collection_ids_set.add(movie_details.get("belongs_to_collection").get("id"))


class TmdbAnimeClient(BaseTmdbClient):
    @staticmethod
    def handle_tmdb_anime_query(category, mode, submode, page):
        tmdb_anime = TmdbAnime()
        set_content_type(mode)

        handlers = {
            Anime.SEARCH: lambda: tmdb_anime.anime_search(
                TmdbAnimeClient.handle_anime_search_query(page), submode, page
            ),
            Anime.AIRING: lambda: TmdbAnimeClient.handle_anime_category_query(
                tmdb_anime, category, submode, page
            ),
            Anime.POPULAR: lambda: TmdbAnimeClient.handle_anime_category_query(
                tmdb_anime, category, submode, page
            ),
            Anime.POPULAR_RECENT: lambda: TmdbAnimeClient.handle_anime_category_query(
                tmdb_anime, category, submode, page
            ),
            Anime.YEARS: lambda: TmdbAnimeClient.handle_anime_years_or_genres(
                category, mode, page, submode
            ),
            Anime.GENRES: lambda: TmdbAnimeClient.handle_anime_years_or_genres(
                category, mode, page, submode
            ),
            Animation().POPULAR: lambda: TmdbAnimeClient.handle_animation_or_cartoons_query(
                tmdb_anime, category, submode, page
            ),
            Cartoons.POPULAR: lambda: TmdbAnimeClient.handle_animation_or_cartoons_query(
                tmdb_anime, category, submode, page
            ),
        }

        handler = handlers.get(category)
        if handler:
            data = handler()
            if data:
                TmdbAnimeClient.process_anime_results(
                    data, submode, page, mode, category
                )

    @staticmethod
    def handle_anime_search_query(page):
        if page == 1:
            query = show_keyboard(id=30242)
            if query:
                pickle_db.set_key("anime_query", query)
                return query
            return None
        return pickle_db.get_key("anime_query")

    @staticmethod
    def handle_anime_category_query(tmdb_anime, category, submode, page):
        if category == Anime.AIRING:
            set_pluging_category(translation(90039))
            return tmdb_anime.anime_on_the_air(submode, page)
        elif category == Anime.POPULAR:
            set_pluging_category(translation(90064))
            return tmdb_anime.anime_popular(submode, page)
        elif category == Anime.POPULAR_RECENT:
            set_pluging_category(translation(90038))
            return tmdb_anime.anime_popular_recent(submode, page)

    @staticmethod
    def handle_anime_years_or_genres(category, mode, page, submode):
        if category == Anime.YEARS:
            TmdbClient.show_years_items(mode, page, submode)
        elif category == Anime.GENRES:
            TmdbClient.show_genres_items(mode, page, submode)

    @staticmethod
    def handle_animation_or_cartoons_query(tmdb_anime, category, submode, page):
        if category == Animation().POPULAR:
            return tmdb_anime.animation_popular(submode, page)
        elif category == Cartoons.POPULAR:
            return tmdb_anime.cartoons_popular(submode, page)

    @staticmethod
    def process_anime_results(data, submode, page, mode, category):
        if data.total_results == 0:
            notification("No results found")
            return
        execute_thread_pool(data.results, TmdbAnimeClient.show_anime_results, submode)
        add_next_button(
            "next_page_anime", page=page, mode=mode, submode=submode, category=category
        )
        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def show_anime_results(res, mode):
        tmdb_id = res.get("id", "")
        if mode == "movies":
            title = res.title
            movie_details = get_tmdb_movie_details(tmdb_id)
            imdb_id = getattr(movie_details, "external_ids").get("imdb_id", "")
            tvdb_id = ""
        elif mode == "tv":
            title = res.name
            title = res["name"]
            show_details = get_tmdb_show_details(tmdb_id)
            external_ids = getattr(show_details, "external_ids")
            imdb_id = external_ids.get("imdb_id", "")
            tvdb_id = external_ids.get("tvdb_id", "")
        else:
            kodilog(f"Invalid mode: {mode}")
            return

        ids = {"tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id}
        list_item = ListItem(label=title)
        set_media_infoTag(list_item, metadata=res, mode=mode)
        TmdbClient._add_media_directory_item(list_item, mode, title, ids)
