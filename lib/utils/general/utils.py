import os
import re
import hashlib
import unicodedata
from urllib.parse import unquote
import requests
from typing import Dict, List
from zipfile import ZipFile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from lib.api.fanart.fanart import get_fanart
from lib.clients.subtitle.utils import get_language_code
from lib.gui.qr_progress_dialog import QRProgressDialog
from lib.api.trakt.trakt_cache import trakt_watched_cache, trakt_cache
from lib.api.trakt.lists_cache import lists_cache
from lib.api.trakt.main_cache import main_cache
from lib.utils.debrid.qrcode_utils import make_qrcode
from lib.utils.general.processors import PostProcessBuilder, PreProcessBuilder
from lib.clients.base import TorrentStream
from lib.api.tvdbapi.tvdbapi import TVDBAPI
from lib.db.cached import cache
from lib.clients.stremio.constants import (
    STREMIO_ADDONS_KEY,
    STREMIO_ADDONS_CATALOGS_KEY,
    STREMIO_TV_ADDONS_KEY,
    STREMIO_USER_ADDONS,
)
from lib.db.pickle_db import PickleDatabase
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    EPISODES_TYPE,
    MOVIES_TYPE,
    SEASONS_TYPE,
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

from collections import deque

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
    AD = "AllDebrid"


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


PROVIDER_COLORS = {
    "debrid": "FF1E90FF",  # dodger blue
    "direct": "FFFFA500",  # orange
    "stremio": "FF8A2BE2",  # blue-violet
    "torrent": "FFFFD700",  # gold
}


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
    elif debrid_type == DebridType.AD:
        return is_ad_enabled()
    else:
        kodilog(f"Unknown debrid type: {debrid_type}", level=xbmc.LOGERROR)


def is_rd_enabled():
    return get_setting("real_debrid_enabled")


def is_ad_enabled():
    return get_setting("alldebrid_enabled")


def is_pm_enabled():
    return get_setting("premiumize_enabled")


def is_debrider_enabled():
    return get_setting("debrider_enabled")


def is_tb_enabled():
    return get_setting("torbox_enabled")


def is_ed_enabled():
    return get_setting("easydebrid_enabled")


def build_list_item(label, icon="", poster_path=""):
    item = ListItem(label=label)
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
    mode = "episode" if mode == "tv" else "movies"

    list_item = ListItem(label=title)
    list_item.setLabel(title)
    list_item.setContentLookup(False)
    list_item.setProperty("IsPlayable", "true")

    data["episode"] = tv_data.get("episode", data.get("episode", ""))
    data["season"] = tv_data.get("season", data.get("season", ""))
    data["name"] = tv_data.get("name", "")
    data["id"] = ids.get("tmdb_id")
    data["imdb_id"] = ids.get("imdb_id")

    set_media_infoTag(list_item, data=data, mode=mode, detailed=True)

    return list_item


def set_media_infoTag(list_item, data, fanart_data={}, mode="video", detailed=False):
    info_tag = list_item.getVideoInfoTag()

    _set_basic_info(info_tag, data)
    _set_media_type(info_tag, mode)
    _set_identification(info_tag, data)
    _set_artwork(list_item, data, fanart_data)
    _set_released_info(info_tag, data)
    _set_watched_status(info_tag, data, mode)

    if mode == "tv" or mode == "season" or mode == "episode":
        _set_show_info(info_tag, data, mode)

    if detailed:
        _set_detailed_info(info_tag, data, mode)


def _set_basic_info(info_tag, data):
    info_tag.setTitle(data.get("title", data.get("name", "")))
    info_tag.setOriginalTitle(
        data.get("original_title", data.get("original_name", data.get("title", "")))
    )
    info_tag.setPlot(data.get("overview") or data.get("biography", "No overview"))


def _set_media_type(info_tag, mode):
    if mode == "movies":
        info_tag.setMediaType("movie")
    elif mode == "tv":
        info_tag.setMediaType("tvshow")
    elif mode == "season":
        info_tag.setMediaType("season")
    elif mode == "episode":
        info_tag.setMediaType("episode")
    else:
        info_tag.setMediaType("video")


def _set_identification(info_tag, data):
    if "imdb_id" in data:
        info_tag.setIMDBNumber(data["imdb_id"])
    if "id" in data:
        unique_ids = {
            "tmdb": str(data.get("id", "")),
            "imdb": data.get("imdb_id", ""),
            "tvdb": data.get("tvdb_id", ""),
        }
        info_tag.setUniqueIDs(unique_ids, "tmdb")


def _set_artwork(list_item, data, fanart_data):
    set_listitem_artwork(list_item, data, fanart_data)


def _set_released_info(info_tag, data):
    if "first_air_date" in data:
        first_air_date = data["first_air_date"]
        if first_air_date:
            info_tag.setFirstAired(first_air_date)
            info_tag.setYear(int(first_air_date.split("-")[0]))
    elif "air_date" in data:
        info_tag.setFirstAired(data["air_date"])
    elif "release_date" in data:
        release_date = data["release_date"]
        if release_date:
            info_tag.setPremiered(release_date)
            info_tag.setYear(int(release_date.split("-")[0]))

    if "runtime" in data:
        runtime = data.get("runtime")
        if runtime:
            info_tag.setDuration(runtime * 60)


def _set_detailed_info(info_tag, data, mode):
    # Rating
    info_tag.setRating(
        data.get("vote_average", data.get("rating", 0)),
        votes=data.get("vote_count", data.get("votes", 0)),
    )
    info_tag.setUserRating(int(float(data.get("popularity", 0))))

    # Classification
    genres = data.get("genre_ids", data.get("genres", []))
    final_genres = extract_genres(genres, mode)
    info_tag.setGenres(final_genres)

    # Countries
    countries = list(data.get("origin_country", data.get("countries", [])))
    if isinstance(countries, str):
        countries = [countries]
    info_tag.setCountries(countries)

    # Cast & crew
    info_tag.setCast(get_cast_and_crew(data))


def _set_watched_status(info_tag, data, mode):
    tmdb_id = str(data.get("id") or data.get("tmdb_id", ""))
    if not tmdb_id:
        return

    is_watched = False
    if mode == "movies":
        is_watched = trakt_watched_cache.get_watched_status("movie", tmdb_id)
    elif mode == "episode":
        season = data.get("season")
        episode = data.get("episode")
        if season is not None and episode is not None:
            is_watched = trakt_watched_cache.get_watched_status(
                "episode", tmdb_id, int(season), int(episode)
            )

    if is_watched:
        info_tag.setPlaycount(1)


def _set_show_info(info_tag, data, mode):
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

    if mode == "tv" or mode == "season":
        info_tag.setTvShowTitle(data.get("title", data.get("name", "")))
        info_tag.setSeason(int(data.get("season", data.get("season_number", 0))))
    elif mode == "episode":
        info_tag.setTvShowTitle(data.get("title", data.get("name", "")))
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


def get_cast_and_crew(data):
    """Return combined list of xbmc.Actor objects for cast and crew."""
    cast_list = []

    casts = extract_cast(data)
    crew = extract_crew(data)

    # Build actors
    cast_list.extend(build_actor(c, is_cast=True) for c in casts)
    cast_list.extend(build_actor(c, is_cast=False) for c in crew)

    return cast_list


def extract_cast(data):
    if hasattr(data, "to_dict"):
        data = data.to_dict()

    credits = data.get("credits", {})
    if isinstance(credits, dict) and "cast" in credits:
        return credits.get("cast", []) or []

    casts = data.get("casts", {})
    if isinstance(casts, dict) and "cast" in casts:
        return casts.get("cast", []) or []

    if "cast" in data:
        return data.get("cast", []) or []

    if "actors" in data:
        return data.get("actors", []) or []

    return []


def extract_crew(data):
    if hasattr(data, "to_dict"):
        data = data.to_dict()

    credits = data.get("credits", {})
    if isinstance(credits, dict) and "crew" in credits:
        return credits.get("crew", []) or []

    if "crew" in data:
        return data.get("crew", []) or []

    return []


def build_actor(member, is_cast=True):
    """Build an xbmc.Actor from a cast or crew member dict."""
    if is_cast:
        return xbmc.Actor(
            name=member.get("name", "Unknown"),
            role=member.get("character", "Unknown"),
            thumbnail=(
                f"http://image.tmdb.org/t/p/w185{member['profile_path']}"
                if member.get("profile_path")
                else ""
            ),
            order=member.get("order", 0),
        )
    else:
        return xbmc.Actor(
            name=member.get("name", "Unknown"),
            role=member.get("job", "Unknown"),
            thumbnail=(
                f"http://image.tmdb.org/t/p/w185{member['profile_path']}"
                if member.get("profile_path")
                else ""
            ),
            order=0,  # Crew usually has no ordering
        )


def set_listitem_artwork(list_item, data, fanart_data):
    thumb_sources = [
        (data.get("poster_path"), "w780"),
        (data.get("still_path"), "w780"),
    ]
    poster_sources = [
        (data.get("poster_path"), "w780"),
        (data.get("still_path"), "w780"),
        (data.get("profile_path"), "w780"),
    ]
    fanart_sources = [
        (data.get("backdrop_path"), "w1280"),
        (data.get("still_path"), "w1280"),
    ]

    clear_logo = [(extract_tmdb_logo_url(data), "original")]

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
            "clearlogo": first_valid(clear_logo, "clearlogo"),
            "tvshow.clearart": first_valid(fanart_sources, "clearart"),
            "tvshow.clearlogo": first_valid(clear_logo, "clearlogo"),
            "tvshow.landscape": first_valid(fanart_sources, "landscape"),
            "tvshow.banner": first_valid(fanart_sources, "banner"),
        }
    )


def extract_tmdb_logo_url(data):
    images = data.get("images", {}) or {}
    logos = images.get("logos", []) or []
    if logos:
        file_path = logos[0].get("file_path")
        if file_path:
            return file_path


def tmdb_url(path, size):
    return f"http://image.tmdb.org/t/p/{size}{path}" if path else ""


def build_media_metadata(ids, mode: str) -> dict:
    metadata = {
        "poster": "",
        "fanart": "",
        "clearlogo": "",
        "overview": "",
        "clearart": "",
        "keyart": "",
        "banner": "",
        "landscape": "",
        "title": "",
        "original_title": "",
        "genres": [],
        "countries": [],
        "year": None,
        "runtime": None,
        "tmdb_id": 0,
        "tvdb_id": 0,
        "vote_average": 0,
        "vote_count": 0,
        "popularity": 0,
        "cast": [],
    }

    tmdb_id = ids.get("tmdb_id", "")
    tvdb_id = ids.get("tvdb_id", "")

    metadata["tmdb_id"] = str(tmdb_id)
    metadata["tvdb_id"] = str(tvdb_id)

    tmdb_logo_path = None

    # TMDB details
    if tmdb_id:
        from lib.clients.tmdb.utils.utils import get_tmdb_media_details

        details = get_tmdb_media_details(tmdb_id, mode)
        poster_path = getattr(details, "poster_path", "")
        metadata["poster"] = f"{TMDB_POSTER_URL}{poster_path}" if poster_path else ""
        metadata["overview"] = getattr(details, "overview", "")
        metadata["title"] = getattr(details, "title", getattr(details, "name", ""))
        metadata["original_title"] = getattr(
            details, "original_title", getattr(details, "original_name", "")
        )
        metadata["year"] = (
            int(str(getattr(details, "release_date", "0"))[:4])
            if getattr(details, "release_date", None)
            else None
        )
        metadata["runtime"] = getattr(details, "runtime", None)
        metadata["vote_average"] = getattr(details, "vote_average", 0)
        metadata["vote_count"] = getattr(details, "vote_count", 0)
        metadata["popularity"] = getattr(details, "popularity", 0)
        metadata["cast"] = extract_cast(details)
        tmdb_logo_path = extract_tmdb_logo_url(details) or ""
        if tmdb_logo_path:
            metadata["clearlogo"] = tmdb_url(tmdb_logo_path, "original")

    # Fanart details
    if tmdb_id or tvdb_id:
        fanart_details = get_fanart_details(tvdb_id=tvdb_id, tmdb_id=tmdb_id, mode=mode)

        if not tmdb_logo_path:
            metadata["clearlogo"] = fanart_details.get("clearlogo")

        for key in ("fanart", "clearart", "keyart", "banner", "landscape"):
            metadata[key] = fanart_details.get(key, "")

    return metadata


def set_watched_file(data):
    title = data.get("title", "")
    is_torrent = data.get("is_torrent", False)
    is_direct = data.get("type", "") == IndexerType.DIRECT

    if is_direct:
        color = get_random_color("Direct", formatted=False)
        title = f"[B][COLOR {color}][Direct][/COLOR][/B] - {title}"
    elif is_torrent:
        color = get_random_color("Torrent", formatted=False)
        title = f"[B][COLOR {color}][Torrent][/COLOR][/B] - {title}"
    else:
        color = get_random_color("Cached", formatted=False)
        title = f"[B][COLOR {color}][Cached][/COLOR][/B] - {title}"

    data["timestamp"] = datetime.now().strftime("%a, %d %b %Y %I:%M %p")

    pickle_db.set_item(key="jt:lfh", subkey=title, value=data)


def set_watched_title(title, ids, mode, tg_data="", media_type=""):
    pickle_db.set_item(
        key="jt:lth",
        subkey=title,
        value={
            "timestamp": datetime.now().strftime("%a, %d %b %Y %I:%M %p"),
            "ids": ids,
            "mode": media_type if mode == "multi" else mode,
            "tg_data": tg_data,
        },
    )


def get_fanart_details(tvdb_id="", tmdb_id="", mode="tv"):
    identifier = "{}|{}".format(
        "fanart.tv", tvdb_id if tvdb_id and tvdb_id != "None" else tmdb_id
    )
    cached = cache.get(identifier)
    if cached:
        return cached

    from lib.clients.tmdb.utils.utils import LANGUAGES

    try:
        language_index = int(get_setting("language", 18))
        lang = LANGUAGES[language_index].split("-")[0].strip()
    except Exception:
        lang = "en"

    if mode == "tv":
        data = get_fanart(mode, lang, tvdb_id)
    else:
        data = get_fanart(mode, lang, tmdb_id)

    if data:
        hours = get_cache_expiration() if is_cache_enabled() else 0
        cache.set(identifier, data, timedelta(hours=hours))

    return data or {}


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
    if mode == "season":
        setContent(ADDON_HANDLE, SEASONS_TYPE)
    elif mode == "episode":
        setContent(ADDON_HANDLE, EPISODES_TYPE)
    elif mode in ("tv", "anime") or media_type == "tv":
        setContent(ADDON_HANDLE, SHOWS_TYPE)
    elif mode == "movies" or media_type == "movies":
        setContent(ADDON_HANDLE, MOVIES_TYPE)
    else:
        setContent(ADDON_HANDLE, TITLES_TYPE)


def get_provider_color(provider_name, formatted=True):
    key = provider_name.lower()

    if key in PROVIDER_COLORS:
        color = PROVIDER_COLORS[key]
    else:
        color = get_random_color(provider_name, formatted=False)

    if formatted:
        return f"[B][COLOR {color}]{provider_name}[/COLOR][/B]"
    else:
        return color


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


def execute_thread_pool_collection(results, func, *args, **kwargs):
    thread_number = get_setting("thread_number", 6)
    collected = []

    def wrapper(res):
        try:
            result = func(res, *args, **kwargs)
            if result is not None:
                collected.append(result)
        except Exception as e:
            kodilog(f"Thread pool error: {e}")

    with ThreadPoolExecutor(max_workers=int(thread_number)) as executor:
        executor.map(wrapper, results)

    return collected


def paginate_list(data, page_size=10):
    for i in range(0, len(data), page_size):
        yield data[i : i + page_size]


def clear_cache_on_update():
    clear_history_by_type(update=True)


def clear_all_cache():
    cache.clean_all()


def clear_trakt_db_cache():
    trakt_cache.clear_all()
    trakt_watched_cache.clear_all()
    lists_cache.delete_all_lists()
    main_cache.delete_all()
    notification(translation(30244))


def clear_tmdb_cache():
    prefixes = [
        "search_%",
        "movie_%",
        "tv_%",
        "season_%",
        "episode_%",
        "discover_%",
        "trending_%",
        "popular_%",
        "person_%",
        "find_%",
        "anime_%",
        "collection_%",
        "get_imdb_id%",
        "latest_%",
    ]
    cache.delete("movie_genres|None")
    cache.delete("show_genres|None")

    for prefix in prefixes:
        cache.delete_like(f"{prefix}|%")
    notification(translation(30240))


def clear_database_cache():
    clear_history_by_type("all")


def clear_stremio_cache():
    cache.delete(STREMIO_ADDONS_KEY)
    cache.delete(STREMIO_ADDONS_CATALOGS_KEY)
    cache.delete(STREMIO_TV_ADDONS_KEY)
    cache.delete(STREMIO_USER_ADDONS)

    cache.delete_like("search_catalog%")
    cache.delete_like("list_catalog%")
    cache.delete_like("list_stremio_%")
    notification(translation(30244))


def clear_debrid_cache():
    cache.delete_like("%|%deb%")
    cache.delete_like("real_debrid%")
    cache.delete_like("premiumize%")
    cache.delete_like("all_debrid%")
    cache.delete_like("torbox%")
    cache.delete_like("debrider%")
    notification(translation(30244))


def clear_mdblist_cache():
    cache.delete("get_user_lists|None")
    cache.delete("top_mdbd_lists|None")

    cache.delete_like("get_user_lists%")
    cache.delete_like("get_list_items%")
    cache.delete_like("top_mdbd_lists%")
    cache.delete_like("search_lists%")
    notification(translation(30244))


def clear_history_by_type(type="all", update=False):
    if update:
        msg = translation(90110)
    else:
        msg = translation(90111)
    confirmed = Dialog().yesno("Clear History", msg)
    if confirmed:
        keys = []
        if type == "lth":
            keys = ["jt:lth"]
        elif type == "lfh":
            keys = ["jt:lfh"]
        else:
            keys = ["jt:lth", "jt:lfh"]

        for key in keys:
            pickle_db.set_key(key, {})

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

    if mode == "tv":
        builder.filter_sources(episode_name, episode, season)
    builder.filter_by_quality()
    if get_setting("filter_size_enabled"):
        builder.filter_by_size()

    results = builder.get_results()
    kodilog(f"Pre-processed results count: {len(results)}")
    return results


def post_process(results: List[TorrentStream], season: int = 0) -> List[TorrentStream]:
    return (
        PostProcessBuilder(results)
        .check_season_pack(season)
        .sort_results()
        .limit_results()
        .get_results()
    )


def filter_debrid_episode(
    files, episode_num: int, season_num: int, strict: bool = True
) -> List[Dict]:
    str_season, str_episode = str(season_num), str(episode_num)
    season_fill, episode_fill = str_season.zfill(2), str_episode.zfill(2)
    ep_plus_1 = str(episode_num + 1).zfill(2)
    ep_minus_1 = str(episode_num - 1).zfill(2)

    def get_filename(file):
        return (
            file.get("path")
            or file.get("filename")
            or file.get("name")
            or file.get("n")
            or ""
        )

    # Normalize filenames for matching
    def normalize_title(title):
        title = unquote(title).replace("'", "")
        title = re.sub(r"[^A-Za-z0-9-]+", ".", title)
        return title.lower()

    string_list = []

    # SXXEYY variants and S2 - 11 / S02.11
    for s, e in [
        (season_fill, episode_fill),
        (str_season, episode_fill),
        (season_fill, str_episode),
        (str_season, str_episode),
    ]:
        string_list.append(rf"s{s}[.-]?e{e}")
        string_list.append(rf"s{s}[.\s-]?{e}")  # S2 - 11 or S02.11

    # Season X Episode Y or SxE patterns
    for s, e in [
        (season_fill, episode_fill),
        (str_season, episode_fill),
        (season_fill, str_episode),
        (str_season, str_episode),
    ]:
        string_list.append(rf"(season[.-]?{s}[.-]?episode[.-]?{e})")
        string_list.append(rf"{s}[x.]?{e}")  # 2x11 or 02.11

    # Episode ±1
    string_list.append(rf"s{season_fill}e{ep_minus_1}[.-]?e{episode_fill}")
    string_list.append(rf"s{season_fill}e{episode_fill}[.-]?e{ep_plus_1}")

    # Episode-only patterns
    string_list.append(rf"episode[.-]?{episode_fill}")
    string_list.append(rf"[.-]ep[.-]?{episode_fill}")
    string_list.append(r"cap\.")

    # Optional strict negative lookahead to avoid false positives like 10x11 matching 1x01
    if strict:
        lookahead = rf"^(?=.*\.e?0*{episode_fill}\.)(?:(?!((?:s|season)[.-]?\d+[.-x]?(?:ep?|episode)[.-]?\d+)|\d+x\d+).)*$"
        string_list.append(lookahead)

    combined_pattern = "|".join(string_list)
    try:
        regex = re.compile(combined_pattern, re.IGNORECASE)
    except re.error as e:
        kodilog(f"Regex compilation failed: {e}")
        return files

    filtered = [f for f in files if regex.search(normalize_title(get_filename(f)))]
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
            with open(kodi_log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = deque(f, maxlen=500)

            content = "".join(reversed(lines))

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


def extract_release_group(title):
    if not title:
        return ""
    # Remove file extension if present
    title = re.sub(r"\.[a-z0-9]{3,4}$", "", title, flags=re.IGNORECASE)
    # Search for -GroupName at the end (common in scene releases)
    match = re.search(r"-([a-zA-Z0-9]+)$", title)
    if match:
        return match.group(1)
    # Search for [GroupName] at the beginning (common in anime/p2p)
    match = re.search(r"^\[([a-zA-Z0-9]+)\]", title)
    if match:
        return match.group(1)
    return ""


def translate_weekday(weekday_name, lang="eng"):
    sub_language = str(get_setting("subtitle_language"))
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


def parse_time(item):
    ts = item[1].get("timestamp")
    if ts:
        try:
            return datetime.strptime(ts, "%a, %d %b %Y %I:%M %p")
        except Exception as e:
            kodilog(e)
            return datetime.min
    return datetime.min
