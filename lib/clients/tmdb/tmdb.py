from datetime import datetime
from lib.api.trakt.trakt_utils import (
    add_trakt_watched_context_menu,
    add_trakt_watchlist_context_menu,
    is_trakt_auth,
)
from lib.clients.tmdb.utils import (
    add_kodi_dir_item,
    filter_anime_by_keyword,
    get_tmdb_movie_details,
    get_tmdb_show_details,
    tmdb_get,
)
from lib.db.main import main_db
from lib.api.tmdbv3api.objs.search import Search
from lib.utils.general.utils import (
    Animation,
    Anime,
    Cartoons,
    add_next_button,
    execute_thread_pool,
    set_content_type,
    set_media_infoTag,
)

from lib.api.tmdbv3api.objs.anime import TmdbAnime
from lib.db.main import main_db
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    build_url,
    kodilog,
    play_media,
    set_view,
    show_keyboard,
    notification,
)

from xbmcgui import ListItem
from xbmcplugin import endOfDirectory


class BaseTmdbClient:
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
                set_playable=True,
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


class TmdbClient(BaseTmdbClient):
    @staticmethod
    def handle_tmdb_search(params):
        mode = params.get("mode")
        page = int(params.get("page", 1))

        query = (
            show_keyboard(id=30241) if page == 1 else main_db.get_query("search_query")
        )
        if not query:
            return

        if page == 1:
            main_db.set_query("search_query", query)

        data = Search().multi(query, page=page)
        kodilog(f"TMDB Search Results: {data}")

        if not data or data.total_results == 0:
            notification("No results found")
            return

        execute_thread_pool(data.results, TmdbClient.show_tmdb_results, mode)
        add_next_button("handle_tmdb_search", page=page, mode=mode)
        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def handle_tmdb_query(params):
        query = params.get("query", "")
        mode = params["mode"]
        submode = params.get("submode")
        category = params.get("category")
        page = int(params.get("page", 1))

        kodilog(f"Handling TMDB query: mode: {mode}, page: {page}")
        set_content_type(mode)

        handlers = {
            "movies": lambda: TmdbClient.handle_tmdb_movie_query(query, page, mode),
            "tv": lambda: TmdbClient.handle_tmdb_show_query(query, page, mode),
            "anime": lambda: TmdbAnimeClient.handle_tmdb_anime_query(
                category, mode, submode, page
            ),
            "cartoon": lambda: TmdbAnimeClient.handle_tmdb_anime_query(
                category, mode, submode, page
            ),
            "animation": lambda: TmdbAnimeClient.handle_tmdb_anime_query(
                category, mode, submode, page
            ),
        }

        handler = handlers.get(mode)
        if handler:
            handler()
        else:
            notification("Invalid mode")

    @staticmethod
    def handle_tmdb_movie_query(query, page, mode):
        query_handlers = {
            "tmdb_trending": lambda: TmdbClient.handle_trending_movies(page, mode),
            "tmdb_genres": lambda: TmdbClient.show_genres_items(mode, page),
            "tmdb_years": lambda: TmdbClient.show_years_items(mode, page),
        }

        handler = query_handlers.get(query)
        if handler:
            handler()
        else:
            notification("Invalid query")

    @staticmethod
    def handle_trending_movies(page, mode):
        data = tmdb_get("trending_movie", page)
        if not data or data.total_results == 0:
            notification("No results found")
            return
        execute_thread_pool(data.results, TmdbClient.show_tmdb_results, mode)
        add_next_button(
            "handle_tmdb_query", query="tmdb_trending", page=page, mode=mode
        )
        endOfDirectory(ADDON_HANDLE)

    @staticmethod
    def handle_tmdb_show_query(query, page, mode):
        if query == "tmdb_trending":
            data = tmdb_get("trending_tv", page)
            if not data or data.total_results == 0:
                notification("No results found")
                return
            execute_thread_pool(data.results, TmdbClient.show_tmdb_results, mode)
            add_next_button("handle_tmdb_query", query=query, page=page, mode=mode)
            endOfDirectory(ADDON_HANDLE)
        elif query == "tmdb_genres":
            TmdbClient.show_genres_items(mode, page)
        elif query == "tmdb_years":
            TmdbClient.show_years_items(mode, page)

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

        if not data or data.total_results == 0:
            notification("No results found")
            return

        execute_thread_pool(data.results, TmdbClient.show_tmdb_results, mode, submode)

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

        if results.total_results == 0:
            notification("No results found")
            return

        execute_thread_pool(
            results.results, TmdbClient.show_tmdb_results, mode, submode
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

        result = TmdbClient._get_tmdb_result_metadata(
            res, mode, media_type, tmdb_id
        )
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
            setattr(res, "runtime", movie_details.runtime)
            setattr(res, "casts", movie_details.casts)
            imdb_id = movie_details.external_ids.get("imdb_id", "")
        elif mode == "tv":
            title = getattr(res, "name", "")
            label_title = title
            show_details = get_tmdb_show_details(tmdb_id)
            setattr(res, "casts", show_details.credits.get("cast", []))
            imdb_id = show_details.external_ids.get("imdb_id", "")
            tvdb_id = show_details.external_ids.get("tvdb_id", "")
        elif mode == "multi":
            title = getattr(res, "name", "") or getattr(res, "title", "")
            if media_type == "movie":
                mode = "movies"
                movie_details = get_tmdb_movie_details(tmdb_id)
                setattr(res, "runtime", movie_details.runtime)
                setattr(res, "casts", movie_details.casts)
                imdb_id = movie_details.external_ids.get("imdb_id", "")
                label_title = f"[B]MOVIE -[/B] {title}"
            elif media_type == "tv":
                mode = "tv"
                show_details = get_tmdb_show_details(tmdb_id)
                setattr(res, "casts", show_details.credits.get("cast", []))
                imdb_id = show_details.external_ids.get("imdb_id", "")
                tvdb_id = show_details.external_ids.get("tvdb_id", "")
                label_title = f"[B]TV -[/B] {title}"
            else:
                return None  # Not movie or tv, skip

        ids = {"tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id}
        return title, label_title, mode, ids

    @staticmethod
    def show_years_items(mode, page, submode=None):
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
    def show_genres_items(mode, page, submode=None):
        path = (
            "show_genres"
            if mode == "tv" or (mode == "anime" and submode == "tv")
            else "movie_genres"
        )
        genres = tmdb_get(path=path)

        for genre in genres:
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


class TmdbAnimeClient(BaseTmdbClient):
    @staticmethod
    def handle_tmdb_anime_query(category, mode, submode, page):
        tmdb_anime = TmdbAnime()
        data = None

        if category == Anime.SEARCH:
            query = TmdbAnimeClient.handle_anime_search_query(page)
            if query is None:
                return
            data = tmdb_anime.anime_search(query, submode, page)
            data = filter_anime_by_keyword(data, submode)
        elif category in (Anime.AIRING, Anime.POPULAR, Anime.POPULAR_RECENT):
            data = TmdbAnimeClient.handle_anime_category_query(
                tmdb_anime, category, submode, page
            )
        elif category in (Anime.YEARS, Anime.GENRES):
            TmdbAnimeClient.handle_anime_years_or_genres(category, mode, page, submode)
        elif category in (Animation().POPULAR, Cartoons.POPULAR):
            data = TmdbAnimeClient.handle_animation_or_cartoons_query(
                tmdb_anime, category, submode, page
            )

        if data:
            TmdbAnimeClient.process_anime_results(data, submode, page, mode, category)

    @staticmethod
    def handle_anime_search_query(page):
        if page == 1:
            query = show_keyboard(id=30242)
            if query:
                main_db.set_query("anime_query", query)
                return query
            return None
        return main_db.get_query("anime_query")

    @staticmethod
    def handle_anime_category_query(tmdb_anime, category, submode, page):
        if category == Anime.AIRING:
            return tmdb_anime.anime_on_the_air(submode, page)
        elif category == Anime.POPULAR:
            return tmdb_anime.anime_popular(submode, page)
        elif category == Anime.POPULAR_RECENT:
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
            imdb_id = movie_details.external_ids.get("imdb_id", "")
            tvdb_id = ""
        elif mode == "tv":
            title = res.name
            title = res["name"]
            show_details = get_tmdb_show_details(tmdb_id)
            imdb_id = show_details.external_ids.get("imdb_id", "")
            tvdb_id = show_details.external_ids.get("tvdb_id", "")

        ids = {"tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id}

        list_item = ListItem(label=title)

        set_media_infoTag(list_item, metadata=res, mode=mode)

        TmdbClient._add_media_directory_item(list_item, mode, title, ids)
