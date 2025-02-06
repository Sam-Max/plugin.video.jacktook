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
from xbmcplugin import addDirectoryItem, setContent, endOfDirectory
from xbmc import getSupportedMedia
from zipfile import ZipFile


PROVIDER_COLOR_MIN_BRIGHTNESS = 128

URL_REGEX = r"^(?!\/)(rtmps?:\/\/|mms:\/\/|rtsp:\/\/|https?:\/\/|ftp:\/\/)?([^\/:]+:[^\/@]+@)?(www\.)?(?=[^\/:\s]+\.[^\/:\s]+)([^\/:\s]+\.[^\/:\s]+)(:\d+)?(\/[^#\s]*[\s\S]*)?(\?[^#\s]*)?(#.*)?$"

USER_AGENT_HEADER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
}

TMDB_POSTER_URL = "http://image.tmdb.org/t/p/w780"
TMDB_BACKDROP_URL = "http://image.tmdb.org/t/p/w1280"

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


class FakeDialog():
    def create(self, message: str):
        pass
    def update(self, percent: int, title: str, message: str):
        pass
class DialogListener:
    def __init__(self):
        # self._dialog = DialogProgressBG()
        self._dialog = FakeDialog()
        pass

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


def set_video_properties(list_item, poster, mode, title, overview, ids):
    set_media_infotag(list_item, mode, title, overview, ids=ids)
    list_item.setProperty("IsPlayable", "true")
    list_item.setArt(
        {
            "poster": poster,
            "fanart": poster,
            "icon": os.path.join(ADDON_PATH, "resources", "img", "magnet.png"),
        }
    )


def set_video_info(
    list_item,
    mode,
    name,
    overview="",
    ids="",
    season_number="",
    episode="",
    ep_name="",
    duration="",
    air_date="",
    url="",
):
    info = {"plot": overview}

    if ids:
        info["imdbnumber"] = ids["imdb_id"]

    if duration:
        info["duration"] = int(duration)

    if mode in ["movies", "multi"]:
        info.update({"mediatype": "movie", "title": name, "originaltitle": name})
    else:
        info.update({"mediatype": "tvshow", "tvshowtitle": name})
        if ep_name:
            info["title"] = name
        if url:
            info["filenameandpath"] = url
        if air_date:
            info["aired"] = air_date
        if season_number:
            info["season"] = int(season_number)
        if episode:
            info["episode"] = int(episode)

    list_item.setInfo("video", info)


def make_listing(metadata):
    title = metadata.get("title")
    tv_data = metadata.get("tv_data", {})
    mode = metadata.get("mode", "")
    ep_name = metadata.get("ep_name", "")
    episode = metadata.get("episode", "")
    season = metadata.get("season", "")
    list_item = ListItem(label=title)
    list_item.setLabel(title)
    list_item.setContentLookup(False)

    ids={"tmdb_id":metadata["tmdb_id"], "tvdb_id":metadata["tvdb_id"], "imdb_id":metadata["imdb_id"]}

    set_media_infotag(
        list_item,
        mode,
        title,
        season=season,
        episode=episode,
        ep_name=ep_name,
        ids=ids,
    )

    list_item.setProperty("IsPlayable", "true")
    return list_item


def set_media_infotag(
    list_item,
    mode,
    name,
    overview="",
    ids="",
    season="",
    episode="",
    ep_name="",
    duration="",
    air_date="",
    url="",
    original_name="",
):
    RuntimeError("CHECK THIS FUNCTION")
    info_tag = list_item.getVideoInfoTag()
    info_tag.setPath(url)
    info_tag.setTitle(name)
    info_tag.setOriginalTitle(original_name if original_name else name)
    if mode == "movies":
        info_tag.setMediaType("movie")
    elif mode == "multi":
        info_tag.setMediaType("video")
        info_tag.setFilenameAndPath(url)
    else:
        info_tag.setMediaType("episode")
        info_tag.setFilenameAndPath(url)
        if air_date:
            info_tag.setFirstAired(air_date)
        if season:
            info_tag.setSeason(int(season))
        if episode:
            info_tag.setEpisode(int(episode))
        if ep_name:
            info_tag.setTitle(ep_name)
        else:
            info_tag.setTitle(name)

    info_tag.setPlot(overview)
    if duration:
        info_tag.setDuration(int(duration) * 60)
    if ids:
        tmdb_id, tvdb_id, imdb_id = ids.values()
        info_tag.setIMDBNumber(imdb_id)
        info_tag.setUniqueIDs(
            {"imdb": str(imdb_id), "tmdb": str(tmdb_id), "tvdb": str(tvdb_id)}
        )


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


def get_description_length():
    return int(get_setting("indexers_desc_length"))


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



def clean_auto_play_undesired(results):
    undesired = ("SD", "CAM", "TELE", "SYNC", "480p")
    for res in copy.deepcopy(results):
        if res.get("isPack"):
            results.remove(res)
        else:
            if any(u in res["title"] for u in undesired):
                results.remove(res)
    return results[0]



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
