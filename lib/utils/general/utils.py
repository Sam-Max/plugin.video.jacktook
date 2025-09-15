import os
import re
import hashlib
import unicodedata
import requests
from typing import Dict, List
from zipfile import ZipFile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from lib.api.fanart.fanart import FanartTv
from lib.clients.aisubtrans.utils import get_language_code
from lib.gui.qr_progress_dialog import QRProgressDialog
from lib.utils.debrid.qrcode_utils import make_qrcode
from lib.utils.general.processors import PostProcessBuilder, PreProcessBuilder
from lib.clients.base import TorrentStream
from lib.api.tvdbapi.tvdbapi import TVDBAPI
from lib.db.cached import cache
from lib.db.pickle_db import PickleDatabase
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    MOVIES_TYPE,
    SHOWS_TYPE,
    TITLES_TYPE,
    build_url,
    container_refresh,
    copy2clip,
    dialog_text,
    get_jacktorr_setting,
    get_setting,
    kodilog,
    notification,
    sleep,
    translatePath,
    translation,
)

from lib.utils.kodi.settings import get_cache_expiration, is_cache_enabled
from lib.vendor.torf._magnet import Magnet

from xbmcgui import ListItem, Dialog
from xbmcgui import DialogProgressBG
from xbmcplugin import addDirectoryItem, setContent, setPluginCategory
from xbmc import getSupportedMedia
import xbmc


pickle_db = PickleDatabase()

PROVIDER_COLOR_MIN_BRIGHTNESS = 128

URL_REGEX = r"^(?!\/)(rtmps?:\/\/|mms:\/\/|rtsp:\/\/|https?:\/\/|ftp:\/\/)?([^\/:]+:[^\/@]+@)?(www\.)?(?=[^\/:\s]+\.[^\/:\s]+)([^\/:\s]+\.[^\/:\s]+)(:\d+)?(\/[^#\s]*[\s\S]*)?(\?[^#\s]*)?(#.*)?$"

USER_AGENT_HEADER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
}

USER_AGENT_STRING = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"

TMDB_POSTER_URL = "http://image.tmdb.org/t/p/w780"

MEDIA_FUSION_DEFAULT_KEY = "eJwBYACf_4hAkZJe85krAoD5hN50-2M0YuyGmgswr-cis3uap4FNnLMvSfOc4e1IcejWJmykujTnWAlQKRi9cct5k3IRqhu-wFBnDoe_QmwMjJI3FnQtFNp2u3jDo23THEEgKXHYqTMrLos="

dialog_update = {"count": -1, "percent": 50}

UNDESIRED_QUALITIES = (
    "SD",
    "CAM",
    "TELE",
    "SYNC",
    "TS",
    "HDTV",
    "HDCAM",
    "HDTS",
    "HDTC",
    "HDTVRip",
)

video_extensions = (
    ".001",
    ".3g2",
    ".3gp",
    ".asf",
    ".asx",
    ".avc",
    ".avi",
    ".avs",
    ".bdm",
    ".bdmv",
    ".bin",
    ".bivx",
    ".dat",
    ".divx",
    ".dv",
    ".dvr-ms",
    ".evo",
    ".f4v",
    ".fli",
    ".flv",
    ".h264",
    ".img",
    ".iso",
    ".m2t",
    ".m2ts",
    ".m2v",
    ".m3u8",
    ".m4v",
    ".mk3d",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mpl",
    ".mpls",
    ".mts",
    ".nrg",
    ".nuv",
    ".ogm",
    ".ogv",
    ".pva",
    ".qt",
    ".rcv",
    ".rec",
    ".rmvb",
    ".sdp",
    ".svq3",
    ".tp",
    ".trp",
    ".ts",
    ".ty",
    ".udf",
    ".vc1",
    ".vdr",
    ".viv",
    ".vob",
    ".vp3",
    ".webm",
    ".wmv",
    ".xvid",
)

non_direct_exts = {
    ".zip",
    ".rar",
    ".001",
    ".002",
    ".strm",
    ".ifo",
    ".vob",
    ".bdat",
    ".pvr",
    ".dvr-ms",
    ".disc",
    ".nrg",
    ".img",
    ".bin",
    ".iso",
}


class Enum:
    @classmethod
    def values(cls):
        return [value for name, value in vars(cls).items() if not name.startswith("_")]


class DebridType(Enum):
    RD = "RealDebrid"
    PM = "Premiumize"
    TB = "Torbox"
    ED = "EasyDebrid"
    DB = "Debrider"


class IndexerType(Enum):
    TORRENT = "Torrent"
    DIRECT = "Direct"
    DEBRID = "Debrid"
    STREMIO_DEBRID = "Stremio"


class Indexer(Enum):
    PROWLARR = "Prowlarr"
    STREMIO = "Stremio"
    JACKETT = "Jackett"
    TORRENTIO = "Torrentio"
    PEERFLIX = "Peerflix"
    MEDIAFUSION = "MediaFusion"
    JACKGRAM = "Jackgram"
    TELEGRAM = "Telegram"
    ELHOSTED = "Elfhosted"
    BURST = "Burst"
    ZILEAN = "Zilean"


class Players(Enum):
    JACKTORR = "Jacktorr"
    TORREST = "Torrest"
    ELEMENTUM = "Elementum"
    JACKGRAM = "Jackgram"


class Anime(Enum):
    SEARCH = "Anime_Search"
    POPULAR = "Anime_Popular"
    POPULAR_RECENT = "Anime_Popular_Recent"
    TRENDING = "Anime_Trending"
    AIRING = "Anime_On_The_Air"
    MOST_WATCHED = "Anime_Most_Watched"
    YEARS = "Anime_Years"
    GENRES = "Anime_Genres"


class Animation(Enum):
    POPULAR = "Animation_Popular"


class Cartoons(Enum):
    SEARCH = "Cartoons_Search"
    POPULAR = "Cartoons_Popular"
    POPULAR_RECENT = "Cartoons_Popular_Recent"
    YEARS = "Cartoons_Years"


torrent_clients = [
    Players.JACKTORR,
    Players.TORREST,
    Players.ELEMENTUM,
]

torrent_indexers = [
    Indexer.PROWLARR,
    Indexer.JACKETT,
    Indexer.TORRENTIO,
    Indexer.PEERFLIX,
    Indexer.ELHOSTED,
    Indexer.BURST,
]


class DialogListener:
    def __init__(self):
        self._dialog = DialogProgressBG()

    @property
    def dialog(self):
        return self._dialog

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self._dialog.close()
        except:
            pass


def is_debrid_activated():
    return (
        get_setting("real_debrid_enabled")
        or get_setting("premiumize_enabled")
        or get_setting("torbox_enabled")
        or get_setting("debrider_enabled")
    )


def check_debrid_enabled(debrid_type):
    if debrid_type == DebridType.RD:
        return is_rd_enabled()
    elif debrid_type == DebridType.PM:
        return is_pm_enabled()
    elif debrid_type == DebridType.TB:
        return is_tb_enabled()
    elif debrid_type == DebridType.DB:
        return is_debrider_enabled()
    else:
        kodilog(f"Unknown debrid type: {debrid_type}", level=xbmc.LOGERROR)


def is_rd_enabled():
    return get_setting("real_debrid_enabled")


def is_pm_enabled():
    return get_setting("premiumize_enabled")


def is_debrider_enabled():
    return get_setting("debrider_enabled")


def is_tb_enabled():
    return get_setting("torbox_enabled")


def is_ed_enabled():
    return get_setting("easydebrid_enabled")


def build_list_item(label, icon="", poster_path=""):
    item = ListItem(label)
    item.setArt(
        {
            "poster": poster_path,
            "icon": os.path.join(ADDON_PATH, "resources", "img", icon),
            "thumb": os.path.join(ADDON_PATH, "resources", "img", icon),
            "fanart": os.path.join(ADDON_PATH, "fanart.png"),
        }
    )
    return item


def make_listing(data):
    title = data.get("title")
    ids = data.get("ids", {})
    tv_data = data.get("tv_data", {})
    mode = data.get("mode", "")

    list_item = ListItem(label=title)
    list_item.setLabel(title)
    list_item.setContentLookup(False)

    data["episode"] = tv_data.get("episode", data.get("episode", ""))
    data["season"] = tv_data.get("season", data.get("season", ""))
    data["name"] = tv_data.get("name", "")
    data["id"] = ids.get("tmdb_id")
    data["imdb_id"] = ids.get("imdb_id")

    set_media_infoTag(list_item, data=data, mode=mode)

    list_item.setProperty("IsPlayable", "true")
    return list_item


def set_media_infoTag(list_item, data, fanart_data={}, mode="video"):
    info_tag = list_item.getVideoInfoTag()

    # General Video Info
    info_tag.setTitle(data.get("title", data.get("name", "")))
    info_tag.setOriginalTitle(
        data.get("original_title", data.get("original_name", data.get("title", "")))
    )
    info_tag.setPlot(data.get("overview") or data.get("biography", "No overview"))

    # Year & Dates
    if "first_air_date" in data:
        first_air_date = data["first_air_date"]
        if first_air_date:
            info_tag.setFirstAired(first_air_date)
            info_tag.setYear(int(first_air_date.split("-")[0]))
    elif "air_date" in data:
        info_tag.setFirstAired(data["air_date"])  # Setting air_date for episodes
    elif "release_date" in data:
        release_date = data["release_date"]
        if release_date:
            info_tag.setPremiered(release_date)
            info_tag.setYear(int(release_date.split("-")[0]))

    if "runtime" in data:
        runtime = data.get("runtime")
        if runtime:
            info_tag.setDuration(runtime * 60)  # Convert to seconds

    # Rating
    info_tag.setRating(
        data.get("vote_average", data.get("rating", 0)),
        votes=data.get("vote_count", data.get("votes", 0)),
    )

    info_tag.setUserRating(int(float(data.get("popularity", 0))))

    # Media Type
    if mode == "movies":
        info_tag.setMediaType("movie")
    elif mode == "tv":
        info_tag.setMediaType("episode")
    else:
        info_tag.setMediaType("video")

    # Classification
    genres = data.get("genre_ids", data.get("genres", []))
    final_genres = extract_genres(genres, mode)
    info_tag.setGenres(final_genres)

    # Countries
    countries = list(data.get("origin_country", data.get("countries", [])))
    if isinstance(countries, str):
        countries = [countries]  # Ensure it's a List
    info_tag.setCountries(countries)

    # Identification
    if "imdb_id" in data:
        info_tag.setIMDBNumber(data["imdb_id"])
    if "id" in data:
        unique_ids = {
            "tmdb": str(data.get("id", "")),
            "imdb": data.get("imdb_id", ""),
        }
        info_tag.setUniqueIDs(unique_ids, "tmdb")

    # Artwork
    set_listitem_artwork(list_item, data, fanart_data)

    if "seasons" in data:
        seasons = list(data["seasons"])
        if isinstance(seasons, list):
            named_seasons = [
                (season.get("season_number", 0), season.get("name", ""))
                for season in seasons
            ]
            info_tag.addSeasons(named_seasons)
        else:
            info_tag.addSeason(seasons.get("season_number", 0), seasons.get("name", ""))

    set_cast_and_actors(info_tag, data)

    # Episode & Season Info (for TV shows/episodes)
    if mode in ["tv", "episode"]:
        info_tag.setTvShowTitle(data.get("tvshow_title", data.get("name", "")))
        info_tag.setSeason(int(data.get("season", data.get("season_number", 0))))
        info_tag.setEpisode(int(data.get("episode", data.get("episode_number", 0))))


def extract_genres(genres, media_type="movies"):
    genre_list = []
    path = "movie_genres" if media_type == "movies" else "show_genres"

    from lib.clients.tmdb.utils.utils import tmdb_get

    genre_response = tmdb_get(path=path)
    if not genre_response or "genres" not in genre_response:
        kodilog(f"Failed to fetch genres for {media_type}", level=xbmc.LOGDEBUG)
        return genre_list

    genre_mapping = {g["id"]: g["name"] for g in genre_response.get("genres", [])}

    for g in genres:
        if isinstance(g, dict) and "name" in g:  # Case: { "id": 28, "name": "Action" }
            genre_list.append(g["name"])
        elif isinstance(g, int):
            genre_list.append(genre_mapping.get(g, str(g)))
        elif isinstance(g, str):
            try:
                genre_id = int(g)
                genre_list.append(genre_mapping.get(genre_id, g))
            except ValueError:
                genre_list.append(g)

    return genre_list


def set_cast_and_actors(info_tag, data):
    cast_list = []
    casts = []

    if "credits" in data:
        credits = data["credits"]
        if "cast" in credits:
            casts = credits["cast"]
    elif "casts" in data:
        casts_obj = data["casts"]
        casts = casts_obj.get("cast", [])
        if not casts:
            kodilog(f"Extracted casts from list: {casts}", level=xbmc.LOGDEBUG)
            try:
                casts = list(casts_obj)
            except Exception:
                casts = []
    elif "cast" in data:
        casts = data["cast"]
    elif "actors" in data:
        casts = data["actors"]

    for cast_member in casts:
        actor = xbmc.Actor(
            name=cast_member.get("name", "Unknown"),
            role=cast_member.get("character", "Unknown"),
            thumbnail=(
                f"http://image.tmdb.org/t/p/w185{cast_member['profile_path']}"
                if cast_member.get("profile_path")
                else ""
            ),
            order=cast_member.get("order", 0),
        )
        cast_list.append(actor)

    if "credits" in data and "crew" in data["credits"]:
        set_cast_and_crew({"crew": data["credits"]["crew"]}, cast_list)
    elif "crew" in data:
        set_cast_and_crew(data, cast_list)

    info_tag.setCast(cast_list)


def set_cast_and_crew(data, cast_list):
    if "crew" in data:
        for crew_member in data["crew"]:
            actor = xbmc.Actor(
                name=crew_member["name"],
                role=crew_member["job"],  # Director, Writer, etc.
                thumbnail=(
                    f"http://image.tmdb.org/t/p/w185{crew_member['profile_path']}"
                    if crew_member.get("profile_path")
                    else ""
                ),
                order=0,  # No specific order for crew members
            )
            cast_list.append(actor)

    if "guest_stars" in data:
        for guest in data["guest_stars"]:
            actor = xbmc.Actor(
                name=guest.get("name", "Unknown"),
                role=guest.get("character", "Unknown"),  # Role = Character name
                thumbnail=(
                    f"http://image.tmdb.org/t/p/w185{guest['profile_path']}"
                    if guest.get("profile_path")
                    else ""
                ),
                order=guest.get("order", 0),  # Preserve the order from TMDB
            )
            cast_list.append(actor)


def set_listitem_artwork(list_item, data, fanart_data):
    def tmdb_url(path, size):
        return f"http://image.tmdb.org/t/p/{size}{path}" if path else ""

    thumb_sources = [
        (data.get("poster_path"), "w780"),
        (data.get("still_path"), "w1280"),
    ]
    poster_sources = [
        (data.get("poster_path"), "w500"),
        (data.get("still_path"), "w1280"),
        (data.get("profile_path"), "w500"),
    ]
    fanart_sources = [
        (data.get("backdrop_path"), "w1280"),
        (data.get("still_path"), "w1280"),
    ]

    def first_valid(sources, fallback_key=""):
        for path, size in sources:
            url = tmdb_url(path, size)
            if url:
                return url
        if fallback_key:
            return data.get(fallback_key, "") or fanart_data.get(fallback_key, "")
        return ""

    list_item.setArt(
        {
            "thumb": first_valid(thumb_sources),
            "poster": first_valid(poster_sources, "poster"),
            "fanart": first_valid(fanart_sources, "fanart"),
            "icon": first_valid(poster_sources),
            "banner": first_valid(fanart_sources, "banner"),
            "clearart": first_valid(fanart_sources, "clearart"),
            "clearlogo": first_valid([], "clearlogo"),
            "tvshow.clearart": first_valid(fanart_sources, "clearart"),
            "tvshow.clearlogo": first_valid([], "clearlogo"),
            "tvshow.landscape": first_valid(fanart_sources, "landscape"),
            "tvshow.banner": first_valid(fanart_sources, "banner"),
        }
    )


def set_watched_file(data):
    title = data.get("title", "")
    is_torrent = data.get("is_torrent", False)
    is_direct = data.get("type", "") == IndexerType.DIRECT

    if title in pickle_db.get_key("jt:lfh"):
        return

    if is_direct:
        color = get_random_color("Direct", formatted=False)
        title = f"[B][COLOR {color}][Direct][/COLOR][/B] - {title}"
    elif is_torrent:
        color = get_random_color("Torrent", formatted=False)
        title = f"[B][COLOR {color}][Torrent][/COLOR][/B] - {title}"
    else:
        color = get_random_color("Cached", formatted=False)
        title = f"[B][COLOR {color}][Cached][/COLOR][/B] - {title}"

    if title not in pickle_db.get_key("jt:watch"):
        pickle_db.set_item(key="jt:watch", subkey=title, value=True)

    data["timestamp"] = datetime.now().strftime("%a, %d %b %Y %I:%M %p")

    pickle_db.set_item(key="jt:lfh", subkey=title, value=data)


def set_watched_title(title, ids, mode, tg_data="", media_type=""):
    kodilog(f"Setting watched title: {title}", level=xbmc.LOGDEBUG)
    current_time = datetime.now()

    if mode == "multi":
        mode = media_type

    pickle_db.set_item(
        key="jt:lth",
        subkey=title,
        value={
            "timestamp": current_time.strftime("%a, %d %b %Y %I:%M %p"),
            "ids": ids,
            "mode": mode,
            "tg_data": tg_data,
        },
    )


def get_fanart_details(tvdb_id="", tmdb_id="", mode="tv"):
    identifier = "{}|{}".format(
        "fanart.tv", tvdb_id if tvdb_id and tvdb_id != "None" else tmdb_id
    )
    data = cache.get(identifier)
    if data:
        return data
    fanart = FanartTv(client_key="fa836e1c874ba95ab08a14ee88e05565")
    if mode == "tv":
        results = fanart.get_show(tvdb_id)
    else:
        results = fanart.get_movie(tmdb_id)
    data = get_fanart_data(results)
    if data:
        cache.set(
            identifier,
            data,
            timedelta(hours=get_cache_expiration() if is_cache_enabled() else 0),
        )
    return data


def get_fanart_data(res):
    fanart_object = res.get("fanart_object")
    if fanart_object is None:
        art = {}
    else:
        art = fanart_object.get("art", {})

    from lib.clients.tmdb.utils.utils import LANGUAGES

    language_index = get_setting("language", 18)
    lang = LANGUAGES[int(language_index)].split("-")[0].strip()

    return {
        "fanart": get_best_image(art.get("fanart", []), lang),
        "clearlogo": get_best_image(art.get("clearlogo", []), lang),
        "poster": get_best_image(art.get("poster", []), lang),
        "clearart": get_best_image(art.get("clearart", []), lang),
        "keyart": get_best_image(art.get("keyart", []), lang),
        "banner": get_best_image(art.get("banner", []), lang),
        "landscape": get_best_image(art.get("landscape", []), lang),
    }


def get_best_image(images, lang="en"):
    if not images:
        return ""
    # Try preferred language first
    lang_matches = [img for img in images if img.get("language") == lang]
    if lang_matches:
        return max(lang_matches, key=lambda x: x.get("rating", 0)).get("url", "")

    # 2. Fallback to English if preferred language not found
    en_matches = [img for img in images if img.get("language") == "en"]
    if en_matches:
        return max(en_matches, key=lambda x: x.get("rating", 0)).get("url", "")

    # 3. Fallback: highest rating overall
    return max(images, key=lambda x: x.get("rating", 0)).get("url", "")


def get_cached_results(query, mode, media_type, episode):
    if mode == "tv" or media_type == "tv" or mode == "anime":
        return get_cached(query, params=(episode, "index"))
    return get_cached(query, params=("index"))


def cache_results(results, query, mode, media_type, episode):
    if mode == "tv" or media_type == "tv" or mode == "anime":
        set_cached(results, query, params=(episode, "index"))
    else:
        set_cached(results, query, params=("index"))


def get_cached(path, params={}):
    identifier = "{}|{}".format(path, params)
    return cache.get(identifier)


def set_cached(data, path, params={}):
    identifier = "{}|{}".format(path, params)
    cache.set(
        identifier,
        data,
        timedelta(hours=get_cache_expiration() if is_cache_enabled() else 0),
    )


def db_get(name, func, path, params):
    identifier = "{}|{}".format(path, params)
    data = cache.get(identifier)
    if not data:
        if name == "search_client":
            data = func()
        cache.set(
            identifier,
            data,
            timedelta(hours=get_cache_expiration() if is_cache_enabled() else 0),
        )
    return data


def tvdb_get(path, params={}):
    identifier = "{}|{}".format(path, params)
    data = cache.get(identifier)
    if data:
        return data
    if path == "get_imdb_id":
        data = TVDBAPI().get_imdb_id(params)
    cache.set(
        identifier,
        data,
        timedelta(hours=get_cache_expiration() if is_cache_enabled() else 0),
    )
    return data


def set_pluging_category(heading: str):
    setPluginCategory(ADDON_HANDLE, heading)


def set_content_type(mode, media_type="movies"):
    if mode in ("tv", "anime") or media_type == "tv":
        setContent(ADDON_HANDLE, SHOWS_TYPE)
    elif mode == "movies" or media_type == "movies":
        setContent(ADDON_HANDLE, MOVIES_TYPE)
    else:
        setContent(ADDON_HANDLE, TITLES_TYPE)


# This method was taken from script.elementum.jackett addon
def get_random_color(provider_name, formatted=True):
    hash = hashlib.sha256(provider_name.encode("utf")).hexdigest()
    colors = []

    spec = 10
    for i in range(0, 3):
        offset = spec * i
        rounded = round(
            int(hash[offset : offset + spec], 16) / int("F" * spec, 16) * 255
        )
        colors.append(int(max(rounded, PROVIDER_COLOR_MIN_BRIGHTNESS)))

    while (sum(colors) / 3) < PROVIDER_COLOR_MIN_BRIGHTNESS:
        for i in range(0, 3):
            colors[i] += 10

    for i in range(0, 3):
        colors[i] = f"{colors[i]:02x}"

    color_format = "FF" + "".join(colors).upper()

    if formatted:
        return f"[B][COLOR {color_format}]{provider_name}[/COLOR][/B]"
    else:
        return color_format


def get_colored_languages(languages):
    if not languages:
        return ""
    return " ".join(get_random_color(lang) for lang in languages)


def execute_thread_pool(results, func, *args, **kwargs):
    thread_number = get_setting("thread_number", 8)
    with ThreadPoolExecutor(max_workers=int(thread_number)) as executor:
        futures = [executor.submit(func, res, *args, **kwargs) for res in results]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                kodilog(f"Thread pool error: {e}")


def paginate_list(data, page_size=10):
    for i in range(0, len(data), page_size):
        yield data[i : i + page_size]


def clear_cache_on_update():
    clear(update=True)


def clear_all_cache():
    cache.clean_all()


def clear(type="all", update=False):
    if update:
        msg = "Do you want to clear your cached history?."
    else:
        msg = "Do you want to clear this history?."
    confirmed = Dialog().yesno("Clear History", msg)
    if confirmed:
        if type == "lth":
            pickle_db.set_key("jt:lth", {})
        elif type == "lfh":
            pickle_db.set_key("jt:lfh", {})
        else:
            pickle_db.set_key("jt:lth", {})
            pickle_db.set_key("jt:lfh", {})
        container_refresh()


def limit_results(results):
    limit = int(get_setting("indexers_total_results", 10))
    return results[:limit]


def get_description_length():
    return int(get_setting("indexers_desc_length", 10))


def remove_duplicate(results):
    seen_values = []
    result_dict = []
    for res in results:
        if res not in seen_values:
            result_dict.append(res)
            seen_values.append(res)
    return result_dict


def unzip(zip_location, destination_location, destination_check):
    try:
        zipfile = ZipFile(zip_location)
        zipfile.extractall(path=destination_location)
        if os.path.exists(destination_check):
            status = True
        else:
            status = False
    except:
        status = False
    return status


def pre_process(
    results: List[TorrentStream],
    mode: str,
    episode_name: str,
    episode: int,
    season: int,
) -> List[TorrentStream]:
    kodilog("Pre-processing results")
    builder = PreProcessBuilder(results).remove_duplicates()
    if get_setting("stremio_enabled") and get_setting("torrent_enable"):
        builder.filter_torrent_sources()
    if mode == "tv":
        builder.filter_sources(episode_name, episode, season)
    builder.filter_by_quality()
    if get_setting("filter_size_enabled"):
        builder.filter_by_size()
    return builder.get_results()


def post_process(results: List[TorrentStream], season: int = 0) -> List[TorrentStream]:
    return (
        PostProcessBuilder(results)
        .check_season_pack(season)
        .sort_results()
        .limit_results()
        .get_results()
    )


def filter_torrent_sources(results):
    filtered_results = []
    for res in results:
        if res.get("infoHash") or res.get("guid"):
            filtered_results.append(res)
    return filtered_results


def filter_debrid_episode(results, episode_num: int, season_num: int) -> List[Dict]:
    episode_fill = f"{int(episode_num):02}"
    season_fill = f"{int(season_num):02}"

    patterns = [
        rf"S{season_fill}E{episode_fill}",  # SXXEXX format
        rf"{season_fill}x{episode_fill}",  # XXxXX format
        rf"\.S{season_fill}E{episode_fill}",  # .SXXEXX format
        rf"E{episode_fill}",  # .EXX format
        rf"\sS{season_fill}E{episode_fill}\s",  # season and episode surrounded by spaces
        rf"Season[\s._-]?{season_fill}[\s._-]?Episode[\s._-]?{episode_fill}",  # Season X Episode Y
        rf"Ep[\s._-]?{episode_fill}",  # EpXX
        r"Cap\.",  # match "Cap."
    ]

    combined_pattern = "|".join(patterns)

    def get_filename(res):
        # Real-Debrid uses 'path', fallback to 'filename' or 'name'
        return res.get("path") or res.get("filename") or res.get("name") or ""

    filtered = [
        res
        for res in results
        if re.search(combined_pattern, get_filename(res), re.IGNORECASE)
    ]

    kodilog("Results after filtering:", level=xbmc.LOGDEBUG)
    kodilog(filtered, level=xbmc.LOGDEBUG)
    return filtered


def clean_auto_play_undesired(results: List[TorrentStream]) -> List[TorrentStream]:
    return [
        r
        for r in results
        if not getattr(r, "isPack", False)
        and not any(u.lower() in r.title.lower() for u in UNDESIRED_QUALITIES)
    ]


def is_torrent_url(uri):
    res = requests.head(uri, timeout=20, headers=USER_AGENT_HEADER)
    if (
        res.status_code == 200
        and res.headers.get("Content-Type") == "application/octet-stream"
    ):
        return True
    else:
        return False


def supported_video_extensions():
    media_types = getSupportedMedia("video").split("|")
    return [ext for ext in media_types if ext not in non_direct_exts]


def add_next_button(func_name, page=1, **kwargs):
    list_item = ListItem(label="Next")
    list_item.setArt(
        {"icon": os.path.join(ADDON_PATH, "resources", "img", "nextpage.png")}
    )

    page += 1
    addDirectoryItem(
        ADDON_HANDLE,
        build_url(func_name, page=page, **kwargs),
        list_item,
        isFolder=True,
    )


def is_video(s):
    return s.lower().endswith(video_extensions)


def get_info_hash_from_magnet(magnet):
    return Magnet.from_string(magnet).infohash


def is_magnet_link(link):
    if link.startswith("magnet:?"):
        return link


def is_url(url):
    return bool(re.match(URL_REGEX, url))


def info_hash_to_magnet(info_hash):
    return f"magnet:?xt=urn:btih:{info_hash}"


def get_state_string(state):
    if 0 <= state <= 9:
        return translation(30650 + state)
    return translation(30660)


def get_service_host():
    return get_jacktorr_setting("service_host")


def get_username():
    return get_jacktorr_setting("service_login")


def get_password():
    return get_jacktorr_setting("service_password")


def ssl_enabled():
    return bool(get_jacktorr_setting("ssl_connection"))


def get_port():
    return get_jacktorr_setting("service_port")


def unicode_flag_to_country_code(unicode_flag):
    if len(unicode_flag) != 2:
        return "Invalid flag Unicode"

    first_letter = unicodedata.name(unicode_flag[0]).replace(
        "REGIONAL INDICATOR SYMBOL LETTER ", ""
    )
    second_letter = unicodedata.name(unicode_flag[1]).replace(
        "REGIONAL INDICATOR SYMBOL LETTER ", ""
    )

    country_code = first_letter.lower() + second_letter.lower()
    return country_code


def debrid_dialog_update(type, total, dialog, lock):
    with lock:
        dialog_update["count"] += 1
        dialog_update["percent"] += 2

        dialog.update(
            dialog_update.get("percent"),
            f"Jacktook [COLOR FFFF6B00]Debrid-{type}[/COLOR]",
            f"Checking: {dialog_update.get('count')}/{total}",
        )


def get_public_ip():
    public_ip = cache.get("public_ip")
    if public_ip:
        return public_ip

    urls = ["https://ipconfig.io/ip", "https://api.ipify.org/"]

    for url in urls:
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            public_ip = response.text.strip()
            cache.set(
                "public_ip",
                public_ip,
                timedelta(hours=get_cache_expiration()),
            )
            return public_ip
        except requests.RequestException as e:
            kodilog(f"Error getting public IP from {url}: {e}")

    return None


def export_to_kodi_paste(log_content):
    try:
        response = requests.post(
            "https://paste.kodi.tv/documents",
            data=log_content,
            headers=USER_AGENT_HEADER,
        )
        kodilog(f"Paste.kodi.tv response: {response.status_code} - {response.text}")
        if response.status_code == 200 and response.text:
            paste_id = response.json().get("key", {})
            if paste_id:
                return f"https://paste.kodi.tv/{paste_id}"
        return None
    except Exception as e:
        kodilog(f"Error exporting logs to paste.kodi.tv: {e}")
        return None


def show_log_export_dialog(params):
    log_file = params.get("log_file")
    kodi_log_path = os.path.join(translatePath("special://logpath"), log_file)
    if os.path.exists(kodi_log_path):
        try:
            with open(kodi_log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            content = "".join(lines[::-1])
            # Ask user if they want to export
            from xbmcgui import Dialog

            dialog = Dialog()
            choice = dialog.select(
                "Kodi Logs", ["Show Logs", "Export to paste.kodi.tv"]
            )
            if choice == 1:
                paste_url = export_to_kodi_paste(content)
                qr_code = make_qrcode(paste_url)
                copy2clip(paste_url)
                progressDialog = QRProgressDialog("qr_dialog.xml", ADDON_PATH)
                progressDialog.setup(
                    "Kodi Logs Exported",
                    qr_code,
                    paste_url,
                    is_debrid=False,
                )
                if paste_url:
                    count = 20
                    progressDialog.show_dialog()
                    while not progressDialog.iscanceled and count >= 0:
                        try:
                            count -= 1
                            progressDialog.update_progress(count)
                        except:
                            pass
                        sleep(1000 * count)
                else:
                    notification("Failed to export logs.")
            else:
                dialog_text("Kodi Logs", content)
        except Exception as e:
            notification(f"Error reading log: {e}")
    else:
        notification("Kodi log file not found.")


def extract_publish_date(date):
    if not date:
        return ""
    match = re.search(r"\d{4}-\d{2}-\d{2}", date)
    return match.group() if match else ""


def translate_weekday(weekday_name, lang="eng"):
    sub_language = str(get_setting("auto_subtitle_lang"))
    if sub_language and sub_language.lower() != "none":
        lang = get_language_code(sub_language)
    return WEEKDAY_TRANSLATIONS.get(lang, WEEKDAY_TRANSLATIONS["eng"]).get(
        weekday_name, weekday_name
    )


WEEKDAY_TRANSLATIONS = {
    "eng": {
        "Monday": "Monday",
        "Tuesday": "Tuesday",
        "Wednesday": "Wednesday",
        "Thursday": "Thursday",
        "Friday": "Friday",
        "Saturday": "Saturday",
        "Sunday": "Sunday",
    },
    "spa": {
        "Monday": "Lunes",
        "Tuesday": "Martes",
        "Wednesday": "Miércoles",
        "Thursday": "Jueves",
        "Friday": "Viernes",
        "Saturday": "Sábado",
        "Sunday": "Domingo",
    },
    "por": {
        "Monday": "Segunda-feira",
        "Tuesday": "Terça-feira",
        "Wednesday": "Quarta-feira",
        "Thursday": "Quinta-feira",
        "Friday": "Sexta-feira",
        "Saturday": "Sábado",
        "Sunday": "Domingo",
    },
}
