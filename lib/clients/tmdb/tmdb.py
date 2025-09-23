from datetime import datetime
import json
import os

from lib.api.tmdbv3api.as_obj import AsObj
from lib.api.tmdbv3api.objs.anime import TmdbAnime
from lib.clients.tmdb.anime_client import TmdbAnimeClient
from lib.clients.tmdb.base import BaseTmdbClient
from lib.clients.tmdb.collections import TmdbCollections
from lib.clients.tmdb.people_client import PeopleClient
from lib.api.tmdbv3api.objs.search import Search
from lib.clients.tmdb.utils.utils import add_kodi_dir_item, tmdb_get
from lib.utils.general.utils import (
    add_next_button,
    execute_thread_pool,
    get_fanart_details,
    set_content_type,
    set_media_infoTag,
    set_pluging_category,
    translate_weekday,
)

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

from lib.utils.general.utils import Anime

from xbmcgui import ListItem
from xbmcplugin import endOfDirectory
import xbmc


class TmdbClient(BaseTmdbClient):
    @staticmethod
    def handle_tmdb_search(params):
        set_pluging_category(translation(90006))
        mode = params.get("mode")
        set_content_type(mode)

        page = int(params.get("page", 1))

        query = (
            show_keyboard(id=30241)
            if page == 1
            else PickleDatabase().get_key("search_query")
        )
        if not query:
            return

        if page == 1:
            PickleDatabase().set_key("search_query", query)

        data = tmdb_get("search_multi", {"query": query, "page": page})
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
        mode = params.get("mode")
        submode = params.get("submode")
        category = params.get("category")
        page = int(params.get("page", 1))

        handlers = {
            "movies": lambda: TmdbClient.handle_tmdb_movie_query(params),
            "tv": lambda: TmdbClient.handle_tmdb_show_query(params),
        }

        anime_modes = {"anime", "cartoon", "animation"}
        if mode in anime_modes:
            handlers[mode] = lambda: TmdbClient.handle_tmdb_anime_query(
                category, mode, submode, page
            )

        handler = handlers.get(mode)
        if handler:
            return handler()
        else:
            notification("Invalid mode")

    @staticmethod
    def handle_tmdb_movie_query(params):
        query = params.get("query", "")
        subquery = params.get("subquery", "")
        mode = params.get("mode")
        page = int(params.get("page", 1))

        query_handlers = {
            "tmdb_trending": lambda: TmdbClient.show_trending_movies(mode, page),
            "tmdb_genres": lambda: TmdbClient.show_genres_items(mode, page),
            "tmdb_popular": lambda: TmdbClient.show_popular_items(mode, page),
            "tmdb_years": lambda: BaseTmdbClient.show_years_items(mode, page),
            "tmdb_lang": lambda: TmdbClient.show_languages(mode, page),
            "tmdb_collections": lambda: TmdbClient.show_collections_menu(mode),
            "tmdb_keywords": lambda: TmdbClient.show_keywords_items(query, page, mode),
            "tmdb_people": lambda: TmdbClient.handle_tmdb_people(subquery, mode, page),
        }

        handler = query_handlers.get(query)
        if handler:
            handler()
        else:
            notification("Invalid query")

    @staticmethod
    def handle_tmdb_people(subquery="", mode="", page=1):
        set_pluging_category("People")
        query_handlers = {
            "search_people": lambda: PeopleClient().search_people(mode, page),
            "popular_people": lambda: PeopleClient().show_popular_people(mode, page),
            "latest_people": lambda: PeopleClient().show_trending_people(mode, page),
        }

        handler = query_handlers.get(subquery)
        if handler:
            handler()
        else:
            notification("Invalid query")

    @staticmethod
    def handle_tmdb_show_query(params):
        query = params.get("query", "")
        subquery = params.get("subquery", "")
        mode = params.get("mode")
        page = int(params.get("page", 1))

        query_handlers = {
            "tmdb_trending": lambda: TmdbClient.show_trending_shows(query, mode, page),
            "tmdb_popular": lambda: TmdbClient.show_popular_items(mode, page),
            "tmdb_lang": lambda: TmdbClient.show_languages(mode, page),
            "tmdb_genres": lambda: TmdbClient.show_genres_items(mode, page),
            "tmdb_calendar": lambda: TmdbClient.show_calendar_items(query, page, mode),
            "tmdb_years": lambda: TmdbClient.show_years_items(mode, page),
            "tmdb_networks": lambda: TmdbClient.show_networks(mode, page),
            "tmdb_people": lambda: TmdbClient.handle_tmdb_people(subquery, mode, page),
        }

        handler = query_handlers.get(query)
        if handler:
            return handler()
        else:
            notification("Invalid query")

    @staticmethod
    def handle_tmdb_anime_query(category, mode, submode, page):
        set_content_type(mode)

        def handle_search():
            return TmdbAnime().anime_search(
                TmdbAnimeClient().handle_anime_search_query(page), submode, page
            )

        def handle_category():
            return TmdbAnimeClient().handle_anime_category_query(
                TmdbAnime(), category, submode, page
            )

        def handle_years_or_genres():
            return TmdbAnimeClient().handle_anime_years_or_genres(
                category, mode, page, submode
            )

        handlers = {
            Anime.SEARCH: handle_search,
            Anime.AIRING: handle_category,
            Anime.POPULAR: handle_category,
            Anime.POPULAR_RECENT: handle_category,
            Anime.YEARS: handle_years_or_genres,
            Anime.GENRES: handle_years_or_genres,
        }

        handler = handlers.get(category)
        if handler:
            data = handler()
            if data:
                TmdbAnimeClient().process_anime_results(
                    data, submode, page, mode, category
                )

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
    def show_tmdb_results(res, mode, submode=""):
        tmdb_id = getattr(res, "id", "")
        tvdb_id = ""
        media_type = res.get("media_type", "") or ""
        number_of_seasons = 1
        title = getattr(res, "title", "") or getattr(res, "name", "")
        label_title = title
        ids = {"tmdb_id": tmdb_id}

        # Adjust mode for anime
        if mode == "anime":
            mode = submode

        tmdb_obj = TmdbClient._get_tmdb_metadata(mode, media_type, tmdb_id)
        if not tmdb_obj:
            return

        # Handle movie-specific
        if (
            mode == "movies"
            or (mode == "multi" and media_type == "movie")
            and "external_ids" in tmdb_obj
        ):
            if mode == "multi":
                mode = "movies"
                label_title = f"[B]MOVIE -[/B] {title}"

            ids["imdb_id"] = tmdb_obj["external_ids"].get("imdb_id", "")
            res.runtime = tmdb_obj.get("runtime", 0)
            res.casts = tmdb_obj.get("casts", [])

        # Handle tv-specific
        elif (
            mode == "tv"
            or (mode == "multi" and media_type == "tv")
            and "external_ids" in tmdb_obj
        ):
            if mode == "multi":
                mode = "tv"
                label_title = f"[B]TV -[/B] {title}"

            ids["imdb_id"] = tmdb_obj["external_ids"].get("imdb_id", "")
            tvdb_id = tmdb_obj["external_ids"].get("tvdb_id", "") or ""
            ids["tvdb_id"] = tvdb_id
            res.casts = tmdb_obj.get("credits", {}).get("cast", [])
            number_of_seasons = tmdb_obj.get("number_of_seasons", 1) or 1

        fanart_details = get_fanart_details(
            tvdb_id=tvdb_id, tmdb_id=tmdb_id, mode=str(mode)
        )

        list_item = ListItem(label=label_title)

        set_media_infoTag(
            list_item, data=tmdb_obj, fanart_data=fanart_details, mode=str(mode)
        )

        TmdbClient.add_media_directory_item(
            list_item,
            mode,
            title,
            ids,
            seasons_number=number_of_seasons,
            media_type=media_type,
        )

    @staticmethod
    def _get_tmdb_metadata(mode, media_type, tmdb_id):
        from lib.clients.tmdb.utils.utils import (
            get_tmdb_movie_details,
            get_tmdb_show_details,
        )

        tmdb_obj = None

        if mode == "movies":
            tmdb_obj = get_tmdb_movie_details(tmdb_id)

        elif mode == "tv":
            tmdb_obj = get_tmdb_show_details(tmdb_id)

        elif mode == "multi":
            if media_type == "movie":
                tmdb_obj = get_tmdb_movie_details(tmdb_id)
            elif media_type == "tv":
                tmdb_obj = get_tmdb_show_details(tmdb_id)
            else:
                kodilog(f"Invalid media type: {media_type}", level=xbmc.LOGERROR)
                return None

        return tmdb_obj

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
        from lib.clients.tmdb.utils.utils import FULL_NAME_LANGUAGES

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
        from lib.clients.tmdb.utils.utils import NETWORKS

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
        from lib.clients.tmdb.utils.utils import NETWORKS

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
    def show_calendar_items(query, page, mode):
        from lib.clients.tmdb.utils.utils import get_tmdb_show_details

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

            set_media_infoTag(list_item, data=details, mode="tv")

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
            results = tmdb_get("tv_recommendations", {"id": tmdb_id, "page": page})
        elif mode == "movies":
            results = tmdb_get("movie_recommendations", {"id": tmdb_id, "page": page})
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
            results = tmdb_get("tv_similar", {"id": tmdb_id, "page": page})
        elif mode == "movies":
            results = tmdb_get("movie_similar", {"id": tmdb_id, "page": page})
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
