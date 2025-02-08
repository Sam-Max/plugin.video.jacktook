from datetime import timedelta
import os
import threading
from lib.api.jacktook.kodi import kodilog
from lib.api.tmdbv3api.objs.anime import TmdbAnime
from lib.api.tmdbv3api.objs.episode import Episode
from lib.api.tmdbv3api.objs.find import Find
from lib.api.tmdbv3api.objs.genre import Genre
from lib.api.tmdbv3api.objs.movie import Movie
from lib.api.tmdbv3api.objs.search import Search
from lib.api.tmdbv3api.objs.season import Season
from lib.api.tmdbv3api.objs.discover import Discover
from lib.api.tmdbv3api.objs.trending import Trending
from lib.api.tmdbv3api.objs.tv import TV
from lib.utils.kodi_utils import ADDON_PATH
from lib.utils.settings import get_cache_expiration, is_cache_enabled
from lib.db.cached import cache
from lib.utils.utils import execute_thread_pool


def add_icon_genre(item, icon_path="tmdb.png"):
    item.setArt(
        {
            "icon": os.path.join(ADDON_PATH, "resources", "img", icon_path),
            "thumb": os.path.join(ADDON_PATH, "resources", "img", icon_path),
        }
    )


def add_icon_tmdb(item, icon_path="tmdb.png"):
    item.setArt(
        {
            "icon": os.path.join(ADDON_PATH, "resources", "img", icon_path),
            "thumb": os.path.join(ADDON_PATH, "resources", "img", icon_path),
        }
    )


def tmdb_get(path, params=None):
    identifier = f"{path}|{params}"
    data = cache.get(identifier, hashed_key=True)
    if data:
        return data

    handlers = {
        "search_tv": lambda p: Search().tv_shows(p),
        "search_movie": lambda p: Search().movies(p),
        "movie_details": lambda p: Movie().details(p),
        "tv_details": lambda p: TV().details(p),
        "season_details": lambda p: Season().details(p["id"], p["season"]),
        "episode_details": lambda p: Episode().details(
            p["id"], p["season"], p["episode"]
        ),
        "movie_genres": lambda _: Genre().movie_list(),
        "tv_genres": lambda _: Genre().tv_list(),
        "discover_movie": lambda p: Discover().discover_movies(p),
        "discover_tv": lambda p: Discover().discover_tv_shows(p),
        "trending_movie": lambda p: Trending().movie_week(page=p),
        "trending_tv": lambda p: Trending().tv_week(page=p),
        "find_by_tvdb": lambda p: Find().find_by_tvdb_id(p),
        "find_by_imdb_id": lambda p: Find().find_by_imdb_id(p),
        "anime_year": lambda p: TmdbAnime().anime_year(p),
        "anime_genres": lambda p: TmdbAnime().anime_genres(p),
    }

    try:
        data = handlers.get(path, lambda _: None)(params)
    except Exception:
        return {}

    if data is not None:
        cache.set(
            identifier,
            data,
            timedelta(hours=get_cache_expiration() if is_cache_enabled() else 0),
            hashed_key=True,
        )

    return data


def get_tmdb_media_details(id, mode):
    if not id:
        return
    if mode == "tv":
        details = tmdb_get("tv_details", id)
    elif mode == "movies":
        details = tmdb_get("movie_details", id)
    return details


def get_tmdb_movie_data(id):
    details = tmdb_get("movie_details", id)
    imdb_id = details.external_ids.get("imdb_id")
    runtime = details.runtime
    return imdb_id, runtime


def get_tmdb_tv_data(id):
    details = tmdb_get("tv_details", id)
    imdb_id = details.external_ids.get("imdb_id")
    tvdb_id = details.external_ids.get("tvdb_id")
    return imdb_id, tvdb_id


def anime_checker(results, mode):
    anime_results = []
    anime = TmdbAnime()
    list_lock = threading.Lock()

    def task(res, anime_results, list_lock):
        results = anime.tmdb_keywords(mode, res["id"])
        if mode == "tv":
            keywords = results["results"]
        else:
            keywords = results["keywords"]
        for i in keywords:
            if i["id"] == 210024:
                with list_lock:
                    anime_results.append(res)

    execute_thread_pool(results, task, anime_results, list_lock)
    results["results"] = anime_results
    results["total_results"] = len(anime_results)
    return results
