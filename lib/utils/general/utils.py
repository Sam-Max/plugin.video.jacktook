from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import datetime, timedelta
import hashlib
import os
import re
import unicodedata
import requests
from enum import Enum

from typing import Dict, List

from lib.api.fanart.fanart import FanartTv

from lib.utils.general.processors import PostProcessBuilder, PreProcessBuilder
from lib.api.trakt.trakt import TraktAPI
from lib.clients.base import TorrentStream
from lib.api.tvdbapi.tvdbapi import TVDBAPI
from lib.db.cached import cache
from lib.db.main import main_db
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    MOVIES_TYPE,
    SHOWS_TYPE,
    build_url,
    container_refresh,
    get_jacktorr_setting,
    get_setting,
    kodilog,
    translation,
)

from lib.utils.kodi.settings import get_cache_expiration, is_cache_enabled

from lib.vendor.torf._magnet import Magnet
from xbmcgui import ListItem, Dialog
from xbmcgui import DialogProgressBG
from xbmcplugin import addDirectoryItem, setContent
from xbmc import getSupportedMedia
import xbmc

from zipfile import ZipFile


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


class Enum:
    @classmethod
    def values(cls):
        return [value for name, value in vars(cls).items() if not name.startswith("_")]


class Debrids(Enum):
    RD = "RealDebrid"
    PM = "Premiumize"
    TB = "Torbox"
    ED = "EasyDebrid"


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


class IndexerType(Enum):
    TORRENT = "Torrent"
    DIRECT = "Direct"
    DEBRID = "Debrid"
    STREMIO_DEBRID = "Stremio"


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
        or get_setting("easydebrid_enabled")
    )


def check_debrid_enabled(type):
    if type == Debrids.RD:
        return is_rd_enabled()
    elif type == Debrids.PM:
        return is_pm_enabled()
    elif type == Debrids.TB:
        return is_tb_enabled()
    elif type == Debrids.ED:
        return is_ed_enabled()


def is_rd_enabled():
    return get_setting("real_debrid_enabled")


def is_pm_enabled():
    return get_setting("premiumize_enabled")


def is_tb_enabled():
    return get_setting("torbox_enabled")


def is_ed_enabled():
    return get_setting("easydebrid_enabled")


def list_item(label, icon="", poster_path=""):
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


def make_listing(metadata):
    title = metadata.get("title")
    ids = metadata.get("ids", {})
    tv_data = metadata.get("tv_data", {})
    mode = metadata.get("mode", "")

    list_item = ListItem(label=title)
    list_item.setLabel(title)
    list_item.setContentLookup(False)

    metadata["episode"] = tv_data.get("episode", "")
    metadata["season"] = tv_data.get("season", "")
    metadata["name"] = tv_data.get("name", "")
    metadata["id"] = ids.get("tmdb_id")
    metadata["imdb_id"] = ids.get("imdb_id")

    set_media_infoTag(list_item, metadata=metadata, mode=mode)

    list_item.setProperty("IsPlayable", "true")
    return list_item


def set_media_infoTag(list_item, metadata, fanart_details={}, mode="video"):
    kodilog(f"Setting media infoTag for mode: {mode}")

    info_tag = list_item.getVideoInfoTag()

    # General Video Info
    info_tag.setTitle(metadata.get("title", metadata.get("name", "")))
    info_tag.setOriginalTitle(
        metadata.get(
            "original_title", metadata.get("original_name", metadata.get("title", ""))
        )
    )
    info_tag.setPlot(metadata.get("overview", ""))

    # Year & Dates
    if "first_air_date" in metadata:
        info_tag.setFirstAired(metadata["first_air_date"])
        info_tag.setYear(int(metadata["first_air_date"].split("-")[0]))
    elif "air_date" in metadata:
        info_tag.setFirstAired(metadata["air_date"])  # Setting air_date for episodes
    elif "release_date" in metadata:
        info_tag.setPremiered(metadata["release_date"])
        info_tag.setYear(int(metadata["release_date"].split("-")[0]))

    if "runtime" in metadata:
        runtime = metadata.get("runtime")
        if runtime:
            info_tag.setDuration(runtime * 60)  # Convert to seconds

    # Rating
    info_tag.setRating(
        metadata.get("vote_average", metadata.get("rating", 0)),
        votes=metadata.get("vote_count", metadata.get("votes", 0)),
    )

    info_tag.setUserRating(int(float(metadata.get("popularity", 0))))

    # Media Type
    if mode == "movies":
        info_tag.setMediaType("movie")
    elif mode == "tv":
        info_tag.setMediaType("tvshow")
    elif mode == "episode":
        info_tag.setMediaType("episode")
    else:
        info_tag.setMediaType("video")

    # Classification
    genres = metadata.get("genre_ids", metadata.get("genres", []))
    final_genres = extract_genres(genres, mode)
    info_tag.setGenres(final_genres)

    # Countries
    countries = list(metadata.get("origin_country", metadata.get("countries", [])))
    if isinstance(countries, str):
        countries = [countries]  # Ensure it's a List
    info_tag.setCountries(countries)

    # Identification
    if "imdb_id" in metadata:
        info_tag.setIMDBNumber(metadata["imdb_id"])
    if "id" in metadata:
        unique_ids = {
            "tmdb": str(metadata.get("id", "")),
            "imdb": metadata.get("imdb_id", ""),
        }
        info_tag.setUniqueIDs(unique_ids, "tmdb")

    # Artwork
    set_listitem_artwork(list_item, metadata, fanart_details)

    if "seasons" in metadata:
        seasons = list(metadata["seasons"])
        if isinstance(seasons, list):
            named_seasons = [
                (season.get("season_number", 0), season.get("name", ""))
                for season in seasons
            ]
            info_tag.addSeasons(named_seasons)
        else:
            info_tag.addSeason(seasons.get("season_number", 0), seasons.get("name", ""))

    set_cast_and_actors(info_tag, metadata)

    # Episode & Season Info (for TV shows/episodes)
    if mode in ["tv", "episode"]:
        info_tag.setTvShowTitle(metadata.get("tvshow_title", metadata.get("name", "")))
    if mode == "episode":
        info_tag.setSeason(metadata.get("season", metadata.get("season_number", 0)))
        info_tag.setEpisode(metadata.get("episode", metadata.get("episode_number", 0)))


def extract_genres(genres, media_type="movies"):
    genre_list = []
    path = "movie_genres" if media_type == "movies" else "show_genres"

    from lib.clients.tmdb.utils import tmdb_get

    genre_response = tmdb_get(path=path)
    genre_mapping = {g["id"]: g["name"] for g in genre_response.get("genres", [])}

    kodilog(f"Genre mapping for {media_type}: {genre_mapping}", level=xbmc.LOGDEBUG)

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


def set_cast_and_actors(info_tag, metadata):
    cast_list = []
    casts = []

    kodilog(f"Setting cast and actors for metadata: {metadata}", level=xbmc.LOGDEBUG)

    if "credits" in metadata:
        credits = metadata["credits"]
        if "cast" in credits:
            casts = credits["cast"]
    elif "casts" in metadata:
        casts_obj = metadata["casts"]
        casts = casts_obj.get("cast", [])
        if not casts:
            kodilog(f"Extracted casts from list: {casts}")
            try:
                casts = list(casts_obj)
            except Exception:
                casts = []
    elif "cast" in metadata:
        casts = metadata["cast"]
    elif "actors" in metadata:
        casts = metadata["actors"]

    kodilog(f"Extracted casts: {casts}", level=xbmc.LOGDEBUG)

    for cast_member in casts:
        actor = xbmc.Actor(
            name=cast_member.get("name", ""),
            role=cast_member.get("character", ""),
            thumbnail=(
                f"http://image.tmdb.org/t/p/w185{cast_member['profile_path']}"
                if cast_member.get("profile_path")
                else ""
            ),
            order=cast_member.get("order", 0),
        )
        cast_list.append(actor)

    if "credits" in metadata and "crew" in metadata["credits"]:
        set_cast_and_crew({"crew": metadata["credits"]["crew"]}, cast_list)
    elif "crew" in metadata:
        set_cast_and_crew(metadata, cast_list)

    info_tag.setCast(cast_list)


def set_cast_and_crew(metadata, cast_list):
    if "crew" in metadata:
        for crew_member in metadata["crew"]:
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

    if "guest_stars" in metadata:
        for guest in metadata["guest_stars"]:
            actor = xbmc.Actor(
                name=guest["name"],
                role=guest["character"],  # Role = Character name
                thumbnail=(
                    f"http://image.tmdb.org/t/p/w185{guest['profile_path']}"
                    if guest.get("profile_path")
                    else ""
                ),
                order=guest.get("order", 0),  # Preserve the order from TMDB
            )
            cast_list.append(actor)


def set_listitem_artwork(list_item, metadata, fanart_details={}):
    list_item.setArt(
        {
            "thumb": (
                f"http://image.tmdb.org/t/p/w780{metadata['poster_path']}"
                if "poster_path" in metadata
                else (
                    f"http://image.tmdb.org/t/p/w1280{metadata['still_path']}"
                    if "still_path" in metadata
                    else ""
                )
            ),
            "poster": (
                f"http://image.tmdb.org/t/p/w500{metadata['poster_path']}"
                if "poster_path" in metadata
                else (
                    f"http://image.tmdb.org/t/p/w1280{metadata['still_path']}"
                    if "still_path" in metadata
                    else ""
                )
            ),
            "fanart": (
                f"http://image.tmdb.org/t/p/w1280{metadata['backdrop_path']}"
                if "backdrop_path" in metadata
                else (
                    f"http://image.tmdb.org/t/p/w1280{metadata['still_path']}"
                    if "still_path" in metadata
                    else fanart_details.get("fanart", "")
                )
            ),
        }
    )


def set_watched_file(data):
    title = data.get("title", "")
    is_torrent = data.get("is_torrent", False)
    is_direct = data.get("type", "") == IndexerType.DIRECT

    if title in main_db.database["jt:lfh"]:
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

    if title not in main_db.database["jt:watch"]:
        main_db.database["jt:watch"][title] = True

    data["timestamp"] = datetime.now().strftime("%a, %d %b %Y %I:%M %p")

    main_db.set_data(key="jt:lfh", subkey=title, value=data)
    main_db.commit()


def set_watched_title(title, ids, mode, tg_data="", media_type=""):
    kodilog(f"Setting watched title: {title}")
    current_time = datetime.now()

    if mode == "multi":
        mode = media_type

    main_db.set_data(
        key="jt:lth",
        subkey=title,
        value={
            "timestamp": current_time.strftime("%a, %d %b %Y %I:%M %p"),
            "ids": ids,
            "mode": mode,
            "tg_data": tg_data,
        },
    )
    main_db.commit()


def is_torrent_watched(title):
    return main_db.database["jt:watch"].get(title, False)


def get_fanart_details(tvdb_id="", tmdb_id="", mode="tv"):
    identifier = "{}|{}".format(
        "fanart.tv", tvdb_id if tvdb_id and tvdb_id != "None" else tmdb_id
    )
    data = cache.get(identifier)
    if data:
        return data
    else:
        fanart = FanartTv(client_key="fa836e1c874ba95ab08a14ee88e05565")
        if mode == "tv":
            results = fanart.get_show(tvdb_id)
            data = get_fanart_data(results)
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


def get_fanart_data(fanart_details):
    fanart_objec = fanart_details["fanart_object"]
    fanart = clearlogo = poster = ""
    if fanart_objec:
        art = fanart_objec.get("art", {})
        fanart_obj = art.get("fanart", {})
        if fanart_obj:
            fanart = fanart_obj[0]["url"]

        clearlogo_obj = art.get("clearlogo", {})
        if clearlogo_obj:
            clearlogo = clearlogo_obj[0]["url"]

        poster_obj = art.get("poster", {})
        if poster_obj:
            poster = poster_obj[0]["url"]

    return {"fanart": fanart, "clearlogo": clearlogo, "poster": poster}


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


def set_content_type(mode, media_type="movies"):
    if mode == "tv" or media_type == "tv" or mode == "anime":
        setContent(ADDON_HANDLE, SHOWS_TYPE)
    elif mode == "movies" or media_type == "movies":
        setContent(ADDON_HANDLE, MOVIES_TYPE)


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
    max_workers = min(8, (os.cpu_count() or 1) * 2)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        [executor.submit(func, res, *args, **kwargs) for res in results]
        executor.shutdown(wait=True)


def paginate_list(data, page_size=10):
    for i in range(0, len(data), page_size):
        yield data[i : i + page_size]


def clear_cache_on_update():
    clear(update=True)


def clear_all_cache():
    cache.clean_all()
    TraktAPI().cache.clear_cache(cache_type="trakt")
    TraktAPI().cache.clear_cache(cache_type="list")


def clear(type="", update=False):
    if update:
        msg = "Do you want to clear your cached history?."
    else:
        msg = "Do you want to clear this history?."
    dialog = Dialog()
    confirmed = dialog.yesno("Clear History", msg)
    if confirmed:
        if type == "lth":
            main_db.database["jt:lth"] = {}
        elif type == "lfh":
            main_db.database["jt:lfh"] = {}
        else:
            main_db.database["jt:lth"] = {}
            main_db.database["jt:lfh"] = {}
        main_db.commit()
        container_refresh()


def limit_results(results):
    limit = int(get_setting("indexers_total_results"))
    return results[:limit]


def get_description_length():
    return int(get_setting("indexers_desc_length"))


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
        kodilog("Filtering torrent sources")
        builder.filter_torrent_sources()
    if mode == "tv" and get_setting("filter_by_episode"):
        builder.filter_by_episode(episode_name, episode, season)
    builder.filter_by_quality()
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
        rf"\s{season_fill}\s",  # season surrounded by spaces
        rf"\.S{season_fill}",  # .SXX format
        rf"\.S{season_fill}E{episode_fill}",  # .SXXEXX format
        rf"\sS{season_fill}E{episode_fill}\s",  # season and episode surrounded by spaces
        r"Cap\.",  # match "Cap."
    ]

    combined_pattern = "|".join(patterns)

    kodilog(f"Combined regex pattern: {combined_pattern}", level=xbmc.LOGDEBUG)
    kodilog("Results before filtering:", level=xbmc.LOGDEBUG)
    kodilog(results, level=xbmc.LOGDEBUG)

    results = [
        res for res in results if re.search(combined_pattern, res.get("filename", ""))
    ]
    kodilog("Results after filtering:", level=xbmc.LOGDEBUG)
    kodilog(results, level=xbmc.LOGDEBUG)
    return results


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
    media_types = getSupportedMedia("video")
    return media_types.split("|")


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
    return get_jacktorr_setting("ssl_connection")


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
    if not public_ip:
        try:
            response = requests.get("https://ipconfig.io/ip", timeout=5)
            response.raise_for_status()
            public_ip = response.text.strip()
            cache.set(
                "public_ip",
                public_ip,
                timedelta(hours=get_cache_expiration() if is_cache_enabled() else 0),
            )
        except requests.RequestException as e:
            kodilog(f"Error getting public ip: {e}")
            return None
    return public_ip


def extract_publish_date(date):
    if not date:
        return ""
    match = re.search(r"\d{4}-\d{2}-\d{2}", date)
    return match.group() if match else ""
