from datetime import datetime
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

from lib.api.jacktook.kodi import kodilog
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
    mode = params["mode"]
    page = int(params["page"])

    if page == 1:
        query = show_keyboard(id=30241)
        if not query:
            return
        main_db.set_query("search_query", query)
    else:
        query = main_db.get_query("search_query")

    data = Search().multi(query, page=page)

    if data.total_results == 0:
        notification("No results found")
        return

    execute_thread_pool(data.results, show_tmdb_results, mode)

    add_next_button("search_tmdb", page=page, mode=mode)
    endOfDirectory(ADDON_HANDLE)


def handle_tmdb_query(params):
    query = params.get("query", "")
    mode = params["mode"]
    submode = params.get("submode", None)
    category = params.get("category", None)
    page = int(params.get("page", 1))

    set_content_type(mode)

    if mode == "movies":
        handle_tmdb_movie_query(query, page, mode)
    elif mode == "tv":
        handle_tmdb_tv_query(query, page, mode)
    elif mode == "anime" or mode == "cartoon" or mode == "animation":
        handle_tmdb_anime_query(category, mode, submode, page)


def handle_tmdb_movie_query(query, page, mode):
    if query == "tmdb_trending":
        data = tmdb_get("trending_movie", page)
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
    if category == Anime.SEARCH:
        if page == 1:
            query = show_keyboard(id=30242)
            if not query:
                return
            main_db.set_query("anime_query", query)
        else:
            query = main_db.get_query("anime_query")
        data = tmdb_anime.anime_search(query, submode, page)
        data = anime_checker(data, submode)
    elif category == Anime.AIRING:
        data = tmdb_anime.anime_on_the_air(submode, page)
    elif category == Anime.POPULAR:
        data = tmdb_anime.anime_popular(submode, page)
    elif category == Anime.POPULAR_RECENT:
        data = tmdb_anime.anime_popular_recent(submode, page)
    elif category == Anime.YEARS:
        show_years_items(mode, page, submode)
        return
    elif category == Anime.GENRES:
        show_genres_items(mode, page, submode)
        return
    elif category == Animation().POPULAR:
        data = tmdb_anime.animation_popular(submode, page)
    elif category == Cartoons.POPULAR:
        data = tmdb_anime.cartoons_popular(submode, page)

    if data:
        if data.total_results == 0:
            notification("No results found")
            return

        execute_thread_pool(data.results, show_anime_results, submode)

        add_next_button(
            "next_page_anime", page=page, mode=mode, submode=submode, category=category
        )
        endOfDirectory(ADDON_HANDLE)


def tmdb_search_genres(mode, genre_id, page, submode=None):
    if mode == "movies":
        data = tmdb_get(
            path="discover_movie",
            params={
                "with_genres": genre_id,
                "append_to_response": "external_ids",
                "page": page,
            },
        )
    elif mode == "tv":
        data = tmdb_get(
            path="discover_tv",
            params={"with_genres": genre_id, "page": page},
        )
    if mode == "anime":
        data = tmdb_get(
            path="anime_genres",
            params={"mode": submode, "genre_id": genre_id, "page": page},
        )

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
    if mode == "movies":
        results = tmdb_get(
            path="discover_movie",
            params={"primary_release_year": year, "page": page},
        )
    elif mode == "tv":
        results = tmdb_get(
            path="discover_tv",
            params={"first_air_date_year": year, "page": page},
        )
    if mode == "anime":
        results = tmdb_get(
            path="anime_year",
            params={"mode": submode, "year": year, "page": page},
        )

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
    tmdb_id = res.id
    media_type = res.get("media_type", "")

    if mode == "anime":
        mode = submode

    if mode == "movies":
        title = res.title
        label_title = title
        imdb_id, duration = get_tmdb_movie_data(tmdb_id)
        res.runtime = duration
        tvdb_id = None
    elif mode == "tv":
        title = res.name
        label_title = title
        imdb_id, tvdb_id = get_tmdb_tv_data(tmdb_id)
    elif mode == "multi":
        if "name" in res:
            title = res.name
        elif "title" in res:
            title = res.title

        if media_type == "movie":
            mode = "movies"
            imdb_id, duration = get_tmdb_movie_data(tmdb_id)
            res.runtime = duration
            tvdb_id = None
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
                )
            ]
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
    if mode == "anime":
        if submode == "tv":
            genres = tmdb_get(path="tv_genres")
        else:
            genres = tmdb_get(path="movie_genres")
    else:
        if mode == "tv":
            genres = tmdb_get(path="tv_genres")
        else:
            genres = tmdb_get(path="movie_genres")

    for genre in genres:
        name = genre["name"]
        if name == "TV Movie":
            continue
        list_item = ListItem(label=name)
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
