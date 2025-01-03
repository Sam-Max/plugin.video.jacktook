from datetime import datetime
import os
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
    TMDB_BACKDROP_URL,
    TMDB_POSTER_URL,
    Anime,
    add_next_button,
    execute_thread_pool,
    set_media_infotag,
)

from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory

from lib.api.jacktook.kodi import kodilog
from lib.api.tmdbv3api.objs.anime import TmdbAnime
from lib.db.main_db import main_db
from lib.utils.kodi_utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    build_url,
    play_media,
    set_view,
    show_keyboard,
    notification,
)
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem


def search(mode, genre_id, page):
    if mode == "multi":
        return handle_multi_search(page)
    elif mode == "movies":
        return handle_movie_search(genre_id, page)
    elif mode == "tv":
        return handle_tv_search(genre_id, page)


def tmdb_search_year(mode, year, page):
    if mode == "movies":
        return tmdb_get(
            path="discover_movie", params={"primary_release_year": year, "page": page}
        )
    elif mode == "tv":
        return tmdb_get(
            path="discover_tv", params={"first_air_date_year": year, "page": page}
        )


def handle_multi_search(page):
    if page == 1:
        query = show_keyboard(id=30241)
        if not query:
            return
        main_db.set_query("search_query", query)
    else:
        query = main_db.get_query("search_query")
    return Search().multi(query, page=page)


def handle_movie_search(genre_id, page):
    if genre_id != -1:
        return tmdb_get(
            path="discover_movie",
            params={
                "with_genres": genre_id,
                "append_to_response": "external_ids",
                "page": page,
            },
        )
    return tmdb_get("trending_movie", page)


def handle_tv_search(genre_id, page):
    if genre_id != -1:
        return tmdb_get(
            path="discover_tv", params={"with_genres": genre_id, "page": page}
        )
    return tmdb_get("trending_tv", page)


def handle_tmdb_query(query, category, mode, submode, page):
    if mode == "movies":
        handle_tmdb_movie_query(query, page, mode)
    elif mode == "tv":
        handle_tmdb_tv_query(query, page, mode)
    elif mode == "anime":
        handle_tmdb_anime_query(category, submode, page)


def handle_tmdb_movie_query(query, page, mode):
    if query == "tmdb_trending":
        result = search("movies", genre_id=-1, page=page)
        if result:
            if result.total_results == 0:
                notification("No results found")
                return
            show_tmdb_results(
                result.results,
                page=page,
                genre_id=-1,
                mode=mode,
            )
    elif query == "tmdb_genres":
        result = tmdb_get(path="movie_genres")
        show_genres_items(result, mode, page)
    elif query == "tmdb_years":
        show_years_items(mode, page)


def handle_tmdb_tv_query(query, page, mode):
    if query == "tmdb_trending":
        result = search(mode="tv", genre_id=-1, page=page)
        if result:
            if result.total_results == 0:
                notification("No results found")
                return
            show_tmdb_results(
                result.results,
                page=page,
                genre_id=-1,
                mode=mode,
            )
    elif query == "tmdb_genres":
        result = tmdb_get(path="tv_genres")
        show_genres_items(result, mode, page)
    elif query == "tmdb_years":
        show_years_items(mode, page)


def handle_tmdb_anime_query(category, mode, page):
    kodilog("handle_tmdb_anime_query")
    anime = TmdbAnime()
    if category == Anime.SEARCH:
        if page == 1:
            query = show_keyboard(id=30242)
            if not query:
                return
            main_db.set_query("anime_query", query)
        else:
            query = main_db.get_query("anime_query")
        data = anime.anime_search(query, mode, page)
        data = anime_checker(data, mode)
    elif category == Anime.AIRING:
        data = anime.anime_on_the_air(mode, page)
    elif category == Anime.POPULAR:
        data = anime.anime_popular(mode, page)

    if data:
        if data.total_results == 0:
            notification("No results found")
            return
        execute_thread_pool(data.results, show_anime_results, mode)
        add_next_button("next_page_anime", page=page, mode=mode, category=category)


def show_tmdb_year_result(results, page, mode, year):
    execute_thread_pool(results, show_items, mode)
    add_next_button("search_tmdb_year", page=page, mode=mode, year=year)


def show_tmdb_results(results, page, mode, genre_id=0):
    execute_thread_pool(results, show_items, mode)
    add_next_button("search_tmdb", page=page, mode=mode, genre_id=genre_id)


def show_items(res, mode):
    tmdb_id = res.id
    media_type = res.get("media_type", "")

    if mode == "movies":
        title = res.title
        label_title = title
        release_date = res.release_date
        imdb_id, duration = get_tmdb_movie_data(tmdb_id)
        tvdb_id = -1
    elif mode == "tv":
        title = res.name
        label_title = title
        imdb_id, tvdb_id = get_tmdb_tv_data(tmdb_id)
        duration = ""
        release_date = res.first_air_date
    elif mode == "multi":
        if "name" in res:
            title = res.name
        elif "title" in res:
            title = res.title

        if media_type == "movie":
            mode = "movies"
            release_date = res.release_date
            imdb_id, duration = get_tmdb_movie_data(tmdb_id)
            tvdb_id = -1
            label_title = f"[B]MOVIE -[/B] {title}"
        elif media_type == "tv":
            mode = media_type
            release_date = res.get("first_air_date", "")
            imdb_id, tvdb_id = get_tmdb_tv_data(tmdb_id)
            duration = ""
            label_title = f"[B]TV -[/B] {title}"
        else:
            return

    poster_path = res.get("poster_path", "")
    if poster_path:
        poster_path = TMDB_POSTER_URL + poster_path

    backdrop_path = res.get("backdrop_path", "")
    if backdrop_path:
        backdrop_path = TMDB_BACKDROP_URL + backdrop_path

    overview = res.get("overview", "")
    ids = f"{tmdb_id}, {tvdb_id}, {imdb_id}"

    list_item = ListItem(label=label_title)

    set_media_infotag(
        list_item,
        mode,
        title,
        overview,
        air_date=release_date,
        duration=duration,
        ids=ids,
    )

    list_item.setArt(
        {
            "poster": poster_path,
            "fanart": backdrop_path,
            "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
        }
    )

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


def show_years_items(mode, page):
    current_year = datetime.now().year
    for year in range(current_year, 1899, -1):
        list_item = ListItem(label=str(year))
        add_icon_tmdb(list_item, icon_path="status.png")
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "search_tmdb_year",
                mode=mode,
                year=year,
                page=page,
            ),
            list_item,
            isFolder=True,
        )
    endOfDirectory(ADDON_HANDLE)
    set_view("widelist")


def show_genres_items(data, mode, page):
    for genre in data.genres:
        name = genre["name"]
        if name == "TV Movie":
            continue
        list_item = ListItem(label=name)
        add_icon_genre(list_item)
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "search_tmdb", mode=mode.split("_")[0], genre_id=genre["id"], page=page
            ),
            list_item,
            isFolder=True,
        )
    endOfDirectory(ADDON_HANDLE)
    set_view("widelist")


def show_anime_results(res, mode):
    description = res.get("overview", "")
    poster_path = res.get("poster_path", "")

    tmdb_id = res.get("id", -1)
    if mode == "movies":
        title = res.title
        imdb_id, duration = get_tmdb_movie_data(tmdb_id)
        tvdb_id = -1
    elif mode == "tv":
        title = res.name
        title = res["name"]
        imdb_id, tvdb_id = get_tmdb_tv_data(tmdb_id)
        duration = ""

    ids = f"{tmdb_id}, {tvdb_id}, {imdb_id}"

    list_item = ListItem(label=title)
    list_item.setArt(
        {
            "poster": TMDB_POSTER_URL + poster_path if poster_path else "",
            "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
        }
    )

    set_media_infotag(
        list_item,
        mode,
        title,
        description,
        duration=duration,
    )

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
