from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import datetime, timedelta
import hashlib
import os
import re
import unicodedata
import requests

from lib.api.fanart.fanarttv import FanartTv
from lib.api.jacktook.kodi import kodilog
from lib.api.trakt.trakt_api import clear_cache
from lib.db.bookmark_db import bookmark_db
from lib.api.tvdbapi.tvdbapi import TVDBAPI
from lib.db.cached import cache
from lib.db.main_db import main_db


from lib.torf._magnet import Magnet
from lib.utils.kodi_utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    MOVIES_TYPE,
    SHOWS_TYPE,
    build_url,
    container_refresh,
    get_jacktorr_setting,
    get_setting,
    translation,
)

from lib.utils.settings import get_cache_expiration, is_cache_enabled

from xbmcgui import ListItem, Dialog
from xbmcgui import DialogProgressBG
from xbmcplugin import addDirectoryItem, setContent
from xbmc import getSupportedMedia
from zipfile import ZipFile
import xbmc


PROVIDER_COLOR_MIN_BRIGHTNESS = 128

URL_REGEX = r"^(?!\/)(rtmps?:\/\/|mms:\/\/|rtsp:\/\/|https?:\/\/|ftp:\/\/)?([^\/:]+:[^\/@]+@)?(www\.)?(?=[^\/:\s]+\.[^\/:\s]+)([^\/:\s]+\.[^\/:\s]+)(:\d+)?(\/[^#\s]*[\s\S]*)?(\?[^#\s]*)?(#.*)?$"

USER_AGENT_HEADER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
}

TMDB_POSTER_URL = "http://image.tmdb.org/t/p/w780"

MEDIA_FUSION_DEFAULT_KEY = "eJwBYACf_4hAkZJe85krAoD5hN50-2M0YuyGmgswr-cis3uap4FNnLMvSfOc4e1IcejWJmykujTnWAlQKRi9cct5k3IRqhu-wFBnDoe_QmwMjJI3FnQtFNp2u3jDo23THEEgKXHYqTMrLos="

dialog_update = {"count": -1, "percent": 50}

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
    if mode == "tv":
        info_tag.setMediaType("tvshow")
    elif mode == "episode":
        info_tag.setMediaType("episode")
    else:
        info_tag.setMediaType("video")

    # Classification
    genres = metadata.get("genre_ids", metadata.get("genres", []))
    final_genres = extract_genres(genres)
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

    set_cast_and_crew(info_tag, metadata)

    # Episode & Season Info (for TV shows/episodes)
    if mode in ["tv", "episode"]:
        info_tag.setTvShowTitle(metadata.get("tvshow_title", metadata.get("name", "")))
    if mode == "episode":
        info_tag.setSeason(metadata.get("season", metadata.get("season_number", 0)))
        info_tag.setEpisode(metadata.get("episode", metadata.get("episode_number", 0)))


def extract_genres(genres):
    genre_list = []

    for g in genres:
        if isinstance(g, dict) and "name" in g:  # Case: { "id": 28, "name": "Action" }
            genre_list.append(g["name"])
        elif isinstance(g, int):
            genre_list.append(str(g))
        elif isinstance(g, str):
            genre_list.append(g)

    return genre_list


def set_cast_and_crew(info_tag, metadata):
    cast_list = []

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

    info_tag.setCast(cast_list)


def set_watched_file(title, data, is_direct=False, is_torrent=False):
    if title in main_db.database["jt:lfh"]:
        return

    if is_direct:
        color = get_random_color("Direct")
        title = f"[B][COLOR {color}][Direct][/COLOR][/B] - {title}"
    elif is_torrent:
        color = get_random_color("Torrent")
        title = f"[B][COLOR {color}][Torrent][/COLOR][/B] - {title}"
    else:
        color = get_random_color("Cached")
        title = f"[B][COLOR {color}][Cached][/COLOR][/B] - {title}"

    if title not in main_db.database["jt:watch"]:
        main_db.database["jt:watch"][title] = True

    data["timestamp"] = datetime.now().strftime("%a, %d %b %Y %I:%M %p")
    data["is_torrent"] = is_torrent

    main_db.set_data(key="jt:lfh", subkey=title, value=data)
    main_db.commit()


def set_watched_title(title, ids, mode="", media_type=""):
    if mode == "multi":
        mode = media_type
    if title != "None":
        current_time = datetime.now()
        main_db.set_data(
            key="jt:lth",
            subkey=title,
            value={
                "timestamp": current_time.strftime("%a, %d %b %Y %I:%M %p"),
                "ids": ids,
                "mode": mode,
            },
        )
        main_db.commit()


def is_torrent_watched(title):
    return main_db.database["jt:watch"].get(title, False)


def get_fanart_details(tvdb_id="", tmdb_id="", mode="tv"):
    identifier = "{}|{}".format(
        "fanart.tv", tvdb_id if tvdb_id and tvdb_id != "None" else tmdb_id
    )
    data = cache.get(identifier, hashed_key=True)
    if data:
        return data
    else:
        fanart = FanartTv(get_setting("fanart_tv_client_id"))
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
                hashed_key=True,
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


def get_cached(path, params={}):
    identifier = "{}|{}".format(path, params)
    return cache.get(identifier, hashed_key=True)


def set_cached(data, path, params={}):
    identifier = "{}|{}".format(path, params)
    cache.set(
        identifier,
        data,
        timedelta(hours=get_cache_expiration() if is_cache_enabled() else 0),
        hashed_key=True,
    )


def db_get(name, func, path, params):
    identifier = "{}|{}".format(path, params)
    data = cache.get(identifier, hashed_key=True)
    if not data:
        if name == "search_client":
            data = func()
        cache.set(
            identifier,
            data,
            timedelta(hours=get_cache_expiration() if is_cache_enabled() else 0),
            hashed_key=True,
        )
    return data


def tvdb_get(path, params={}):
    identifier = "{}|{}".format(path, params)
    data = cache.get(identifier, hashed_key=True)
    if data:
        return data
    if path == "get_imdb_id":
        data = TVDBAPI().get_imdb_id(params)
    cache.set(
        identifier,
        data,
        timedelta(hours=get_cache_expiration() if is_cache_enabled() else 0),
        hashed_key=True,
    )
    return data


def set_content_type(mode, media_type="movies"):
    if mode == "tv" or media_type == "tv" or mode == "anime":
        setContent(ADDON_HANDLE, SHOWS_TYPE)
    elif mode == "movies" or media_type == "movies":
        setContent(ADDON_HANDLE, MOVIES_TYPE)


# This method was taken from script.elementum.jackett addon
def get_random_color(provider_name):
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

    return "FF" + "".join(colors).upper()


def get_colored_languages(languages):
    if not languages:
        return ""
    colored_languages = []
    for lang in languages:
        lang_color = get_random_color(lang)
        colored_lang = f"[B][COLOR {lang_color}][{lang}][/COLOR][/B]"
        colored_languages.append(colored_lang)
    colored_languages = " ".join(colored_languages)
    return colored_languages


def execute_thread_pool(results, func, *args, **kwargs):
    with ThreadPoolExecutor(max_workers=10) as executor:
        [executor.submit(func, res, *args, **kwargs) for res in results]
        executor.shutdown(wait=True)


def paginate_list(data, page_size=10):
    for i in range(0, len(data), page_size):
        yield data[i : i + page_size]


def clear_cache_on_update():
    clear(update=True)


def clear_all_cache():
    cache.clean_all()
    bookmark_db.clear_bookmarks()
    clear_cache(cache_type="trakt")
    clear_cache(cache_type="list")


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


def check_season_pack(results, season_num):
    season_fill = f"{int(season_num):02}"

    patterns = [
        # Season as ".S{season_num}." or ".S{season_fill}."
        r"\.S%s\." % season_num,
        r"\.S%s\." % season_fill,
        # Season as " S{season_num} " or " S{season_fill} "
        r"\sS%s\s" % season_num,
        r"\sS%s\s" % season_fill,
        # Season as ".{season_num}.season" (like .1.season, .01.season)
        r"\.%s\.season" % season_num,
        # "total.season" or "season" or "the.complete"
        r"total\.season",
        r"season",
        r"the\.complete",
        r"complete",
        # Pattern to detect episode ranges like S02E01-02
        r"S(\d{2})E(\d{2})-(\d{2})",
        # Season as ".season.{season_num}." or ".season.{season_fill}."
        r"\.season\.%s\." % season_num,
        r"\.season%s\." % season_num,
        r"\.season\.%s\." % season_fill,
        # Handle cases "s1 to {season_num}", "s1 thru {season_num}", etc.
        r"s1 to %s" % season_num,
        r"s1 to s%s" % season_num,
        r"s01 to %s" % season_fill,
        r"s01 to s%s" % season_fill,
        r"s1 thru %s" % season_num,
        r"s1 thru s%s" % season_num,
        r"s01 thru %s" % season_fill,
        r"s01 thru s%s" % season_fill,
    ]

    combined_pattern = "|".join(patterns)

    for res in results:
        match = re.search(combined_pattern, res["title"])
        if match:
            res["isPack"] = True
        else:
            res["isPack"] = False


def pre_process(results, mode, episode_name, episode, season):
    results = remove_duplicate(results)

    if get_setting("stremio_enabled") and get_setting("torrent_enable"):
        results = filter_torrent_sources(results)

    if mode == "tv" and get_setting("filter_by_episode"):
        results = filter_by_episode(results, episode_name, episode, season)

    results = filter_by_quality(results)

    return results


def post_process(results, season=0):
    if int(season) > 0:
        check_season_pack(results, season)

    results = sort_results(results)

    results = limit_results(results)

    return results


def filter_torrent_sources(results):
    filtered_results = []
    for res in results:
        if res.get("infoHash") or res.get("guid"):
            filtered_results.append(res)
    return filtered_results


def sort_results(res):
    sort_by = get_setting("indexers_sort_by")

    field_to_sort = {
        "Seeds": "seeders",
        "Size": "size",
        "Date": "publishDate",
        "Quality": "quality",
        "Cached": "isCached",
    }

    if sort_by in field_to_sort:
        res = sorted(res, key=lambda r: r.get(field_to_sort[sort_by], 0), reverse=True)

    priority_language = get_setting("priority_language").lower()
    if priority_language and priority_language != "None":
        res = sorted(
            res, key=lambda r: priority_language in r.get("languages", []), reverse=True
        )

    return res


def filter_by_episode(results, episode_name, episode_num, season_num):
    episode_fill = f"{int(episode_num):02}"
    season_fill = f"{int(season_num):02}"

    patterns = [
        r"S%sE%s" % (season_fill, episode_fill),  # SXXEXX format
        r"%sx%s" % (season_fill, episode_fill),  # XXxXX format
        r"\s%s\s" % season_fill,  # season surrounded by spaces
        r"\.S%s" % season_fill,  # .SXX format
        r"\.S%sE%s" % (season_fill, episode_fill),  # .SXXEXX format
        r"\sS%sE%s\s"
        % (season_fill, episode_fill),  # season and episode surrounded by spaces
        r"Cap\.",  # match "Cap."
    ]

    if episode_name:
        patterns.append(episode_name)

    combined_pattern = "|".join(patterns)

    filtered_episodes = []
    for res in results:
        match = re.search(combined_pattern, res["title"])
        if match:
            filtered_episodes.append(res)

    return filtered_episodes


def filter_by_quality(results):
    quality_720p = []
    quality_1080p = []
    quality_4k = []
    no_quarlity = []

    for res in results:
        title = res["title"]
        if "480p" in title:
            res["quality"] = "[B][COLOR orange]480p[/COLOR][/B]"
            quality_720p.append(res)
        elif "720p" in title:
            res["quality"] = "[B][COLOR orange]720p[/COLOR][/B]"
            quality_720p.append(res)
        elif "1080p" in title:
            res["quality"] = "[B][COLOR blue]1080p[/COLOR][/B]"
            quality_1080p.append(res)
        elif "2160" in title:
            res["quality"] = "[B][COLOR yellow]4k[/COLOR][/B]"
            quality_4k.append(res)
        else:
            res["quality"] = "[B][COLOR yellow]N/A[/COLOR][/B]"
            no_quarlity.append(res)

    combined_list = quality_4k + quality_1080p + quality_720p + no_quarlity
    return combined_list


def clean_auto_play_undesired(results):
    undesired = ("SD", "CAM", "TELE", "SYNC", "480p")
    for res in copy.deepcopy(results):
        if res.get("isPack"):
            results.remove(res)
        else:
            if any(u in res["title"] for u in undesired):
                results.remove(res)
    return results[0]


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
