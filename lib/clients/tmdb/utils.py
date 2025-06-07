from datetime import timedelta
import os
import threading

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

from lib.utils.kodi.utils import ADDON_HANDLE, ADDON_PATH, kodilog
from lib.utils.kodi.settings import get_cache_expiration, is_cache_enabled
from lib.utils.general.utils import execute_thread_pool

from lib.db.cached import cache
from xbmcplugin import addDirectoryItem
from xbmcgui import ListItem


LANGUAGES = [
    "ar-AE",
    "ar-SA",
    "be-BY",
    "bg-BG",
    "bn-BD",
    "ca-ES",
    "ch-GU",
    "cs-CZ",
    "da-DK",
    "de-AT",
    "de-CH",
    "de-DE",
    "el-GR",
    "en-AU",
    "en-CA",
    "en-GB",
    "en-IE",
    "en-NZ",
    "en-US",
    "eo-EO",
    "es-ES",
    "es-MX",
    "et-EE",
    "eu-ES",
    "fa-IR",
    "fi-FI",
    "fr-CA",
    "fr-FR",
    "gl-ES",
    "he-IL",
    "hi-IN",
    "hu-HU",
    "id-ID",
    "it-IT",
    "ja-JP",
    "ka-GE",
    "kk-KZ",
    "kn-IN",
    "ko-KR",
    "lt-LT",
    "lv-LV",
    "ml-IN",
    "ms-MY",
    "ms-SG",
    "nb-NO",
    "nl-NL",
    "no-NO",
    "pl-PL",
    "pt-BR",
    "pt-PT",
    "ro-RO",
    "ru-RU",
    "si-LK",
    "sk-SK",
    "sl-SI",
    "sr-RS",
    "sv-SE",
    "ta-IN",
    "te-IN",
    "th-TH",
    "tl-PH",
    "tr-TR",
    "uk-UA",
    "vi-VN",
    "zh-CN",
    "zh-HK",
    "zh-TW",
    "zu-ZA",
]


def add_kodi_dir_item(
    list_item, url, is_folder=True, icon_path=None, set_playable=False
):
    if icon_path:
        add_icon_tmdb(list_item, icon_path=icon_path)
    if set_playable:
        list_item.setProperty("IsPlayable", "true")
    addDirectoryItem(ADDON_HANDLE, url, list_item, isFolder=is_folder)


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
    data = cache.get(identifier)
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
        "show_genres": lambda _: Genre().tv_list(),
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
    except Exception as e:
        kodilog(f"Error in tmdb_get for {path} with params {params}: {e}")
        return {}

    if data is not None:
        cache.set(
            identifier,
            data,
            timedelta(hours=get_cache_expiration() if is_cache_enabled() else 0),
        )

    return data


def get_tmdb_media_details(tmdb_id, mode):
    kodilog(f"Fetching TMDB details for ID: {tmdb_id} in mode: {mode}")
    if mode == "tv":
        return tmdb_get("tv_details", tmdb_id)
    elif mode == "movies":
        return tmdb_get("movie_details", tmdb_id)


def get_tmdb_movie_details(id):
    return tmdb_get("movie_details", id)


def get_tmdb_show_details(id):
    return tmdb_get("tv_details", id)


def filter_anime_by_keyword(results, mode):
    filtered_anime = []
    anime_api = TmdbAnime()
    list_lock = threading.Lock()

    def check_and_append(item, filtered_anime, list_lock):
        keywords_data = anime_api.tmdb_keywords(mode, item["id"])
        keywords = (
            keywords_data["results"] if mode == "tv" else keywords_data["keywords"]
        )
        for keyword in keywords:
            if keyword["id"] == 210024:
                with list_lock:
                    filtered_anime.append(item)
                break

    execute_thread_pool(results["results"], check_and_append, filtered_anime, list_lock)
    results["results"] = filtered_anime
    results["total_results"] = len(filtered_anime)
    return results
