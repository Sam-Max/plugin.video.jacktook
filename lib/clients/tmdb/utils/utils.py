from datetime import timedelta
import os
import threading
from typing import List, Optional

from lib.api.mdblist.mdblist import MDblistAPI
from lib.api.tmdbv3api.as_obj import AsObj
from lib.api.tmdbv3api.objs.anime import TmdbAnime
from lib.api.tmdbv3api.objs.collection import Collection
from lib.api.tmdbv3api.objs.episode import Episode
from lib.api.tmdbv3api.objs.find import Find
from lib.api.tmdbv3api.objs.genre import Genre
from lib.api.tmdbv3api.objs.movie import Movie
from lib.api.tmdbv3api.objs.person import Person
from lib.api.tmdbv3api.objs.search import Search
from lib.api.tmdbv3api.objs.season import Season
from lib.api.tmdbv3api.objs.discover import Discover
from lib.api.tmdbv3api.objs.trending import Trending
from lib.api.tmdbv3api.objs.tv import TV

from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    container_update,
    kodilog,
    play_media,
    translation,
)
from lib.utils.kodi.settings import get_cache_expiration, is_cache_enabled
from lib.utils.general.utils import execute_thread_pool

from lib.db.cached import cache
from xbmcplugin import addDirectoryItem


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

FULL_NAME_LANGUAGES = [
    {"name": "Arabic", "id": "ar"},
    {"name": "Bosnian", "id": "bs"},
    {"name": "Bulgarian", "id": "bg"},
    {"name": "Chinese", "id": "zh"},
    {"name": "Croatian", "id": "hr"},
    {"name": "Dutch", "id": "nl"},
    {"name": "English", "id": "en"},
    {"name": "Finnish", "id": "fi"},
    {"name": "French", "id": "fr"},
    {"name": "German", "id": "de"},
    {"name": "Greek", "id": "el"},
    {"name": "Hebrew", "id": "he"},
    {"name": "Hindi", "id": "hi"},
    {"name": "Hungarian", "id": "hu"},
    {"name": "Icelandic", "id": "is"},
    {"name": "Italian", "id": "it"},
    {"name": "Japanese", "id": "ja"},
    {"name": "Korean", "id": "ko"},
    {"name": "Macedonian", "id": "mk"},
    {"name": "Norwegian", "id": "no"},
    {"name": "Persian", "id": "fa"},
    {"name": "Polish", "id": "pl"},
    {"name": "Portuguese", "id": "pt"},
    {"name": "Punjabi", "id": "pa"},
    {"name": "Romanian", "id": "ro"},
    {"name": "Russian", "id": "ru"},
    {"name": "Serbian", "id": "sr"},
    {"name": "Slovenian", "id": "sl"},
    {"name": "Spanish", "id": "es"},
    {"name": "Swedish", "id": "sv"},
    {"name": "Turkish", "id": "tr"},
    {"name": "Ukrainian", "id": "uk"},
]


NETWORKS = [
    {"id": 129, "name": "A&E", "icon": "https://i.imgur.com/xLDfHjH.png"},
    {"id": 2, "name": "ABC", "icon": "https://i.imgur.com/qePLxos.png"},
    {"id": 174, "name": "AMC", "icon": "https://i.imgur.com/ndorJxi.png"},
    {"id": 2697, "name": "Acorn TV", "icon": "https://i.imgur.com/fSWB5gB.png"},
    {"id": 80, "name": "Adult Swim", "icon": "https://i.imgur.com/jCqbRcS.png"},
    {"id": 1024, "name": "Amazon", "icon": "https://i.imgur.com/ru9DDlL.png"},
    {"id": 91, "name": "Animal Planet", "icon": "https://i.imgur.com/olKc4RP.png"},
    {"id": 2552, "name": "Apple TV +", "icon": "https://i.imgur.com/fAQMVNp.png"},
    {"id": 251, "name": "Audience", "icon": "https://i.imgur.com/5Q3mo5A.png"},
    {"id": 4, "name": "BBC 1", "icon": "https://i.imgur.com/u8x26te.png"},
    {"id": 332, "name": "BBC 2", "icon": "https://i.imgur.com/SKeGH1a.png"},
    {"id": 3, "name": "BBC 3", "icon": "https://i.imgur.com/SDLeLcn.png"},
    {"id": 100, "name": "BBC 4", "icon": "https://i.imgur.com/PNDalgw.png"},
    {"id": 493, "name": "BBC America", "icon": "https://i.imgur.com/TUHDjfl.png"},
    {"id": 24, "name": "BET", "icon": "https://i.imgur.com/ZpGJ5UQ.png"},
    {"id": 74, "name": "Bravo", "icon": "https://i.imgur.com/TmEO3Tn.png"},
    {"id": 23, "name": "CBC", "icon": "https://i.imgur.com/unQ7WCZ.png"},
    {"id": 16, "name": "CBS", "icon": "https://i.imgur.com/8OT8igR.png"},
    {"id": 1709, "name": "CBS All Access", "icon": "https://i.imgur.com/ZvaWMuU.png"},
    {"id": 110, "name": "CTV", "icon": "https://i.imgur.com/qUlyVHz.png"},
    {"id": 56, "name": "Cartoon Network", "icon": "https://i.imgur.com/zmOLbbI.png"},
    {"id": 26, "name": "Channel 4", "icon": "https://i.imgur.com/6ZA9UHR.png"},
    {"id": 99, "name": "Channel 5", "icon": "https://i.imgur.com/5ubnvOh.png"},
    {"id": 359, "name": "Cinemax", "icon": "https://i.imgur.com/zWypFNI.png"},
    {"id": 47, "name": "Comedy Central", "icon": "https://i.imgur.com/ko6XN77.png"},
    {"id": 928, "name": "Crackle", "icon": "https://i.imgur.com/53kqZSY.png"},
    {"id": 2243, "name": "DC Universe", "icon": "https://i.imgur.com/bhWIubn.png"},
    {"id": 64, "name": "Discovery Channel", "icon": "https://i.imgur.com/8UrXnAB.png"},
    {"id": 244, "name": "Discovery ID", "icon": "https://i.imgur.com/07w7BER.png"},
    {"id": 4353, "name": "Discovery+", "icon": "https://i.imgur.com/ukz1nOG.png"},
    {"id": 54, "name": "Disney Channel", "icon": "https://i.imgur.com/ZCgEkp6.png"},
    {"id": 44, "name": "Disney XD", "icon": "https://i.imgur.com/PAJJoqQ.png"},
    {"id": 2739, "name": "Disney+", "icon": "https://i.imgur.com/DVrPgbM.png"},
    {"id": 76, "name": "E!", "icon": "https://i.imgur.com/3Delf9f.png"},
    {"id": 136, "name": "E4", "icon": "https://i.imgur.com/frpunK8.png"},
    {"id": 19, "name": "FOX", "icon": "https://i.imgur.com/6vc0Iov.png"},
    {"id": 88, "name": "FX", "icon": "https://i.imgur.com/aQc1AIZ.png"},
    {"id": 1267, "name": "Freeform", "icon": "https://i.imgur.com/f9AqoHE.png"},
    {"id": 49, "name": "HBO", "icon": "https://i.imgur.com/Hyu8ZGq.png"},
    {"id": 3186, "name": "HBO Max", "icon": "https://i.imgur.com/mmRMG75.png"},
    {"id": 210, "name": "HGTV", "icon": "https://i.imgur.com/INnmgLT.png"},
    {"id": 384, "name": "Hallmark Channel", "icon": "https://i.imgur.com/zXS64I8.png"},
    {"id": 65, "name": "History Channel", "icon": "https://i.imgur.com/LEMgy6n.png"},
    {"id": 453, "name": "Hulu", "icon": "https://i.imgur.com/uSD2Cdw.png"},
    {"id": 9, "name": "ITV", "icon": "https://i.imgur.com/5Hxp5eA.png"},
    {"id": 34, "name": "Lifetime", "icon": "https://i.imgur.com/tvYbhen.png"},
    {"id": 33, "name": "MTV", "icon": "https://i.imgur.com/QM6DpNW.png"},
    {"id": 6, "name": "NBC", "icon": "https://i.imgur.com/yPRirQZ.png"},
    {
        "id": 43,
        "name": "National Geographic",
        "icon": "https://i.imgur.com/XCGNKVQ.png",
    },
    {"id": 213, "name": "Netflix", "icon": "https://i.imgur.com/jI5c3bw.png"},
    {"id": 35, "name": "Nick Junior", "icon": "https://i.imgur.com/leuCWYt.png"},
    {"id": 13, "name": "Nickelodeon", "icon": "https://i.imgur.com/OUVoqYc.png"},
    {"id": 132, "name": "Oxygen", "icon": "https://i.imgur.com/uFCQvbR.png"},
    {"id": 14, "name": "PBS", "icon": "https://i.imgur.com/r9qeDJY.png"},
    {
        "id": 2076,
        "name": "Paramount Network",
        "icon": "https://i.imgur.com/ez3U6NV.png",
    },
    {"id": 4330, "name": "Paramount+", "icon": "https://i.imgur.com/dmUjWmU.png"},
    {"id": 3353, "name": "Peacock", "icon": "https://i.imgur.com/1JXFkSM.png"},
    {"id": 67, "name": "Showtime", "icon": "https://i.imgur.com/SawAYkO.png"},
    {"id": 214, "name": "Sky 1", "icon": "https://i.imgur.com/xbgzhPU.png"},
    {"id": 55, "name": "Spike", "icon": "https://i.imgur.com/BhXYytR.png"},
    {"id": 318, "name": "Starz", "icon": "https://i.imgur.com/Z0ep2Ru.png"},
    {"id": 270, "name": "SundanceTV", "icon": "https://i.imgur.com/qldG5p2.png"},
    {"id": 77, "name": "Syfy", "icon": "https://i.imgur.com/9yCq37i.png"},
    {"id": 68, "name": "TBS", "icon": "https://i.imgur.com/RVCtt4Z.png"},
    {"id": 84, "name": "TLC", "icon": "https://i.imgur.com/c24MxaB.png"},
    {"id": 41, "name": "TNT", "icon": "https://i.imgur.com/WnzpAGj.png"},
    {"id": 397, "name": "TV Land", "icon": "https://i.imgur.com/1nIeDA5.png"},
    {"id": 71, "name": "The CW", "icon": "https://i.imgur.com/Q8tooeM.png"},
    {"id": 21, "name": "The WB", "icon": "https://i.imgur.com/rzfVME6.png"},
    {"id": 209, "name": "Travel Channel", "icon": "https://i.imgur.com/mWXv7SF.png"},
    {"id": 30, "name": "USA Network", "icon": "https://i.imgur.com/Doccw9E.png"},
    {"id": 158, "name": "VH1", "icon": "https://i.imgur.com/IUtHYzA.png"},
    {"id": 202, "name": "WGN America", "icon": "https://i.imgur.com/TL6MzgO.png"},
    {"id": 1436, "name": "YouTube Red", "icon": "https://i.imgur.com/ZfewP1Y.png"},
    {"id": 364, "name": "truTV", "icon": "https://i.imgur.com/HnB3zfc.png"},
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


def tmdb_get(path, params=None) -> Optional[AsObj]:
    identifier = f"{path}|{params}"
    data = cache.get(key=identifier)
    if data:
        return data

    handlers = {
        "search_tv": lambda p: Search().tv_shows(p),
        "search_movie": lambda p: Search().movies(p),
        "search_multi": lambda p: Search().multi(p["query"], page=p["page"]),
        "search_collections": lambda p: Search().collections(p["query"], p["page"]),
        "search_people": lambda p: Search().people(p["query"], p["page"]),
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
        "tv_calendar": lambda p: Discover().discover_tv_calendar(page=p),
        "tv_week": lambda p: Trending().tv_week(page=p),
        "trending_movie": lambda p: Trending().movie_week(page=p),
        "popular_movie": lambda p: Movie().popular(page=p),
        "trending_tv": lambda p: Trending().tv_week(page=p),
        "popular_shows": lambda p: TV().popular(page=p),
        "popular_people": lambda p: Person().popular(page=p),
        "trending_people": lambda p: Trending().person_week(page=p),
        "latest_people": lambda p: Person().latest(),
        "person_details": lambda p: Person().details(p),
        "person_credits": lambda p: Person().combined_credits(p),
        "person_tv_credits": lambda p: Person().tv_credits(p),
        "person_movie_credits": lambda p: Person().movie_credits(p),
        "tv_credits": lambda p: TV().credits(p),
        "movie_credits": lambda p: Movie().credits(p),
        "person_ids": lambda p: Person().external_ids(p),
        "find_by_tvdb": lambda p: Find().find_by_tvdb_id(p),
        "find_by_imdb_id": lambda p: Find().find_by_imdb_id(p),
        "anime_year": lambda p: TmdbAnime().anime_year(p),
        "anime_genres": lambda p: TmdbAnime().anime_genres(p),
        "collection_details": lambda p: Collection().details(p),
        "collection_images": lambda p: Collection().images(p),
    }

    try:
        data = handlers.get(path, lambda _: None)(params)
    except Exception as e:
        kodilog(f"Error in tmdb_get for {path} with params {params}: {e}")
        return None

    if data is not None:
        cache.set(
            key=identifier,
            data=data,
            expires=timedelta(
                hours=get_cache_expiration() if is_cache_enabled() else 0
            ),
        )

    return data


def mdblist_get(path, params=None) -> Optional[List]:
    identifier = f"{path}|{params}"
    data = cache.get(key=identifier)
    if data:
        return data

    handlers = {
        "get_user_lists": lambda _: MDblistAPI().get_user_lists(),
        "get_list_items": lambda p: MDblistAPI().get_list_items(
            list_id=p.get("list_id"),
            limit=p.get("limit"),
            offset=p.get("offset"),
            append_to_response="genre,poster",
            unified=True,
        ),
        "top_mdbd_lists": lambda _: MDblistAPI().get_top_lists(),
        "search_lists": lambda p: MDblistAPI().search_lists(p["query"]),
    }

    try:
        data = handlers.get(path, lambda _: None)(params)
    except Exception as e:
        kodilog(f"Error in mdblist_get for {path} with params {params}: {e}")
        return None

    if data is not None:
        cache.set(
            key=identifier,
            data=data,
            expires=timedelta(
                hours=get_cache_expiration() if is_cache_enabled() else 0
            ),
        )

    return data


def get_tmdb_media_details(tmdb_id, mode):
    if mode == "tv":
        return tmdb_get("tv_details", tmdb_id)
    elif mode == "movies":
        return tmdb_get("movie_details", tmdb_id)


def get_tmdb_movie_details(id: str) -> Optional[AsObj]:
    return tmdb_get("movie_details", id)


def get_tmdb_show_details(id: str) -> Optional[AsObj]:
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


def add_tmdb_movie_context_menu(mode, title=None, ids={}):
    return [
        (
            translation(90049),
            play_media(
                name="search",
                mode=mode,
                query=title,
                ids=ids,
                rescrape=True,
            ),
        ),
        (
            translation(90050),
            container_update(
                name="search_tmdb_recommendations",
                mode=mode,
                ids=ids,
            ),
        ),
        (
            translation(90051),
            container_update(
                name="search_tmdb_similar",
                mode=mode,
                ids=ids,
            ),
        ),
        (
            translation(90081),
            container_update(
                name="search_people_by_id",
                mode=mode,
                ids=ids,
            ),
        ),
    ]


def add_tmdb_show_context_menu(mode, ids={}):
    return [
        (
            translation(90050),
            container_update(
                name="search_tmdb_recommendations",
                mode=mode,
                ids=ids,
            ),
        ),
        (
            translation(90051),
            container_update(
                name="search_tmdb_similar",
                mode=mode,
                ids=ids,
            ),
        ),
        (
            translation(90081),
            container_update(
                name="search_people_by_id",
                mode=mode,
                ids=ids,
            ),
        ),
    ]


def add_tmdb_episode_context_menu(mode, tv_name=None, tv_data=None, ids={}):
    return [
        (
            translation(90049),
            play_media(
                name="search",
                mode=mode,
                query=tv_name,
                ids=ids,
                tv_data=tv_data,
                rescrape=True,
            ),
        ),
        (
            translation(90050),
            container_update(
                name="search_tmdb_recommendations",
                mode=mode,
                ids=ids,
            ),
        ),
        (
            translation(90051),
            container_update(
                name="search_tmdb_similar",
                mode=mode,
                ids=ids,
            ),
        ),
        (
            translation(90081),
            container_update(
                name="search_people_by_id",
                mode=mode,
                ids=ids,
            ),
        ),
    ]
