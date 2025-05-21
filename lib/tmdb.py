from datetime import datetime
from lib.api.trakt.trakt_utils import add_trakt_watchlist_context_menu
from lib.db.main_db import main_db
from lib.api.tmdbv3api.objs.search import Search
from lib.utils.tmdb_utils import (
    add_icon_genre,
    add_icon_tmdb,
    anime_checker,
    get_tmdb_movie_data,
    get_tmdb_tv_data,
    tmdb_get,
)
from lib.utils.utils import (
    Animation,
    Anime,
    Cartoons,
    add_next_button,
    execute_thread_pool,
    set_content_type,
    set_media_infoTag,
)

from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory

from lib.api.tmdbv3api.objs.anime import TmdbAnime
from lib.db.main_db import main_db
from lib.utils.kodi_utils import (
    ADDON_HANDLE,
    build_url,
    play_media,
    set_view,
    show_keyboard,
    notification,
)
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem


def search_tmdb(params):
    mode = params.get("mode")
    page = int(params.get("page", 1))

    query = show_keyboard(id=30241) if page == 1 else main_db.get_query("search_query")
    if not query:
        return

    if page == 1:
        main_db.set_query("search_query", query)

    data = Search().multi(query, page=page)

    if not data or data.total_results == 0:
        notification("No results found")
        return

    execute_thread_pool(data.results, show_tmdb_results, mode)
    add_next_button("search_tmdb", page=page, mode=mode)
    endOfDirectory(ADDON_HANDLE)


def handle_tmdb_query(params):
    query = params.get("query", "")
    mode = params["mode"]
    submode = params.get("submode")
    category = params.get("category")
    page = int(params.get("page", 1))

    set_content_type(mode)

    handlers = {
        "movies": lambda: handle_tmdb_movie_query(query, page, mode),
        "tv": lambda: handle_tmdb_tv_query(query, page, mode),
        "anime": lambda: handle_tmdb_anime_query(category, mode, submode, page),
        "cartoon": lambda: handle_tmdb_anime_query(category, mode, submode, page),
        "animation": lambda: handle_tmdb_anime_query(category, mode, submode, page),
    }

    handler = handlers.get(mode)
    if handler:
        handler()
    else:
        notification("Invalid mode")


def handle_tmdb_movie_query(query, page, mode):
    query_handlers = {
        "tmdb_trending": lambda: handle_trending_movies(page, mode),
        "tmdb_genres": lambda: show_genres_items(mode, page),
        "tmdb_years": lambda: show_years_items(mode, page),
    }

    handler = query_handlers.get(query)
    if handler:
        handler()
    else:
        notification("Invalid query")


def handle_trending_movies(page, mode):
    data = tmdb_get("trending_movie", page)
    if data:
        if data.total_results == 0:
            notification("No results found")
            return
        execute_thread_pool(data.results, show_tmdb_results, mode)
        add_next_button(
            "handle_tmdb_query", query="tmdb_trending", page=page, mode=mode
        )
        endOfDirectory(ADDON_HANDLE)


def handle_tmdb_tv_query(query, page, mode):
    if query == "tmdb_trending":
        data = tmdb_get("trending_tv", page)
        if data:
            if data.total_results == 0:
                notification("No results found")
                return
            execute_thread_pool(data.results, show_tmdb_results, mode)
            add_next_button("handle_tmdb_query", query=query, page=page, mode=mode)
            endOfDirectory(ADDON_HANDLE)
    elif query == "tmdb_genres":
        show_genres_items(mode, page)
    elif query == "tmdb_years":
        show_years_items(mode, page)


def handle_tmdb_anime_query(category, mode, submode, page):
    tmdb_anime = TmdbAnime()
    data = None

    if category == Anime.SEARCH:
        query = handle_anime_search_query(page)
        if not query:
            return
        data = tmdb_anime.anime_search(query, submode, page)
        data = anime_checker(data, submode)
    elif category in [Anime.AIRING, Anime.POPULAR, Anime.POPULAR_RECENT]:
        data = handle_anime_category_query(tmdb_anime, category, submode, page)
    elif category in [Anime.YEARS, Anime.GENRES]:
        handle_anime_years_or_genres(category, mode, page, submode)
        return
    elif category in [Animation().POPULAR, Cartoons.POPULAR]:
        data = handle_animation_or_cartoons_query(tmdb_anime, category, submode, page)

    if data:
        process_anime_results(data, submode, page, mode, category)


def handle_anime_search_query(page):
    if page == 1:
        query = show_keyboard(id=30242)
        if query:
            main_db.set_query("anime_query", query)
        return query
    return main_db.get_query("anime_query")


def handle_anime_category_query(tmdb_anime, category, submode, page):
    if category == Anime.AIRING:
        return tmdb_anime.anime_on_the_air(submode, page)
    elif category == Anime.POPULAR:
        return tmdb_anime.anime_popular(submode, page)
    elif category == Anime.POPULAR_RECENT:
        return tmdb_anime.anime_popular_recent(submode, page)


def handle_anime_years_or_genres(category, mode, page, submode):
    if category == Anime.YEARS:
        show_years_items(mode, page, submode)
    elif category == Anime.GENRES:
        show_genres_items(mode, page, submode)


def handle_animation_or_cartoons_query(tmdb_anime, category, submode, page):
    if category == Animation().POPULAR:
        return tmdb_anime.animation_popular(submode, page)
    elif category == Cartoons.POPULAR:
        return tmdb_anime.cartoons_popular(submode, page)


def process_anime_results(data, submode, page, mode, category):
    if data.total_results == 0:
        notification("No results found")
        return

    execute_thread_pool(data.results, show_anime_results, submode)
    add_next_button(
        "next_page_anime", page=page, mode=mode, submode=submode, category=category
    )
    endOfDirectory(ADDON_HANDLE)


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

    if data:
        if data.total_results == 0:
            notification("No results found")
            return

        execute_thread_pool(data.results, show_tmdb_results, mode, submode)

        add_next_button(
            "search_tmdb_genres",
            mode=mode,
            submode=submode,
            genre_id=genre_id,
            page=page,
        )
        endOfDirectory(ADDON_HANDLE)


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

    if results:
        if results.total_results == 0:
            notification("No results found")
            return

        execute_thread_pool(results.results, show_tmdb_results, mode, submode)

        add_next_button(
            "search_tmdb_year", page=page, mode=mode, submode=submode, year=year
        )
        endOfDirectory(ADDON_HANDLE)


def show_tmdb_results(res, mode, submode=None):
    tmdb_id = getattr(res, "id", None)
    media_type = res.get("media_type", "") if hasattr(res, "get") else ""

    # Adjust mode for anime
    if mode == "anime":
        mode = submode

    title = ""
    label_title = ""
    imdb_id = tvdb_id =  duration = None

    if mode == "movies":
        title = getattr(res, "title", "")
        label_title = title
        imdb_id, duration = get_tmdb_movie_data(tmdb_id)
        setattr(res, "runtime", duration)
        tvdb_id = ""
    elif mode == "tv":
        title = getattr(res, "name", "")
        label_title = title
        imdb_id, tvdb_id = get_tmdb_tv_data(tmdb_id)
    elif mode == "multi":
        title = getattr(res, "name", "") or getattr(res, "title", "")
        if media_type == "movie":
            mode = "movies"
            imdb_id, duration = get_tmdb_movie_data(tmdb_id)
            setattr(res, "runtime", duration)
            tvdb_id = ""
            label_title = f"[B]MOVIE -[/B] {title}"
        elif media_type == "tv":
            mode = "tv"
            imdb_id, tvdb_id = get_tmdb_tv_data(tmdb_id)
            label_title = f"[B]TV -[/B] {title}"

    ids = {"tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id}
    list_item = ListItem(label=label_title)

    set_media_infoTag(list_item, metadata=res, mode=mode)

    if mode == "movies":
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
                ),
            ]
            + add_trakt_watchlist_context_menu("movies", ids)
        )
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "search",
                mode=mode,
                query=title,
                ids=ids,
            ),
            list_item,
            isFolder=False,
        )
    else:
        list_item.addContextMenuItems(add_trakt_watchlist_context_menu("tv", ids))
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "tv_seasons_details",
                ids=ids,
                mode=mode,
                media_type=media_type,
            ),
            list_item,
            isFolder=True,
        )


def show_years_items(mode, page, submode=None):
    current_year = datetime.now().year
    for year in range(current_year, 1899, -1):
        list_item = ListItem(label=str(year))
        add_icon_tmdb(list_item, icon_path="status.png")
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "search_tmdb_year",
                mode=mode,
                submode=submode,
                year=year,
                page=page,
            ),
            list_item,
            isFolder=True,
        )
    endOfDirectory(ADDON_HANDLE)
    set_view("widelist")


def show_genres_items(mode, page, submode=None):
    path = (
        "tv_genres"
        if mode == "tv" or (mode == "anime" and submode == "tv")
        else "movie_genres"
    )
    genres = tmdb_get(path=path)

    for genre in genres:
        if genre.get("name") == "TV Movie":
            continue
        list_item = ListItem(label=genre["name"])
        add_icon_genre(list_item)
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "search_tmdb_genres",
                mode=mode,
                submode=submode,
                genre_id=genre["id"],
                page=page,
            ),
            list_item,
            isFolder=True,
        )
    endOfDirectory(ADDON_HANDLE)
    set_view("widelist")


def show_anime_results(res, mode):
    tmdb_id = res.get("id", None)
    if mode == "movies":
        title = res.title
        imdb_id, _ = get_tmdb_movie_data(tmdb_id)
        tvdb_id = None
    elif mode == "tv":
        title = res.name
        title = res["name"]
        imdb_id, tvdb_id = get_tmdb_tv_data(tmdb_id)

    ids = {"tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id}

    list_item = ListItem(label=title)

    set_media_infoTag(list_item, metadata=res, mode=mode)

    if mode == "tv":
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "tv_seasons_details",
                ids=ids,
                mode=mode,
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
                mode=mode,
                query=title,
                ids=ids,
            ),
            list_item,
            isFolder=False,
        )
