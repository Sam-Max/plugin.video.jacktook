from datetime import datetime, timedelta
import hashlib
import os
import re

from resources.lib.db.cached import Cache
from resources.lib.db.database import get_db
from resources.lib.player import JacktookPlayer
from resources.lib.tmdbv3api.objs.genre import Genre
from resources.lib.tmdbv3api.objs.movie import Movie
from resources.lib.tmdbv3api.objs.search import Search
from resources.lib.tmdbv3api.objs.season import Season
from resources.lib.tmdbv3api.objs.tv import TV

from resources.lib.torf._magnet import Magnet
from resources.lib.fanarttv import get_api_fanarttv
from resources.lib.kodi import (
    ADDON_PATH,
    container_refresh,
    get_cache_expiration,
    get_int_setting,
    get_setting,
    is_torrest_addon,
    is_elementum_addon,
    notify,
    translation,
)

from resources.lib.tmdbv3api.objs.discover import Discover
from resources.lib.tmdbv3api.objs.trending import Trending

from xbmcgui import ListItem, Dialog
from xbmcplugin import (
    addDirectoryItem,
    setResolvedUrl,
)
from xbmc import getSupportedMedia
from urllib.parse import quote


cache = Cache.get_instance()

db = get_db()

PROVIDER_COLOR_MIN_BRIGHTNESS = 50

URL_REGEX = r"^(?!\/)(rtmps?:\/\/|mms:\/\/|rtsp:\/\/|https?:\/\/|ftp:\/\/)?([^\/:]+:[^\/@]+@)?(www\.)?(?=[^\/:\s]+\.[^\/:\s]+)([^\/:\s]+\.[^\/:\s]+)(:\d+)?(\/[^#\s]*[\s\S]*)?(\?[^#\s]*)?(#.*)?$"


class Enum:
    @classmethod
    def values(cls):
        return [value for name, value in vars(cls).items() if not name.startswith("_")]


class Indexer(Enum):
    PROWLARR = "Prowlarr"
    JACKETT = "Jackett"
    TORRENTIO = "Torrentio"
    ELHOSTED = "Elfhosted"


def play(url, magnet, id, title, plugin, debrid=False):
    set_watched_file(title, id, magnet, url)

    if not magnet and not url:
        notify(translation(30251))
        return

    torr_client = get_setting("torrent_client")
    if torr_client == "Torrest":
        if not is_torrest_addon():
            notify(translation(30250))
            return
        if magnet:
            _url = "plugin://plugin.video.torrest/play_magnet?magnet=" + quote(magnet)
        else:
            _url = "plugin://plugin.video.torrest/play_url?url=" + quote(url)
    elif torr_client == "Elementum":
        if not is_elementum_addon():
            notify(translation(30250))
            return
        if magnet:
            _url = "plugin://plugin.video.elementum/play?uri=" + quote(magnet)
        else:
            notify("Not a playable url.")
            return
    elif torr_client == "Debrid":
        debrid = True
        if url.endswith(".torrent") or magnet:
            notify("Not a playable url.")
            return
        _url = url

    list_item = ListItem(title, path=_url)
    setResolvedUrl(plugin.handle, True, list_item)

    if debrid:
        player = JacktookPlayer()
        list_item = player.make_listing(list_item, _url, title, id)
        player.run(list_item)


def list_item(label, icon):
    item = ListItem(label)
    item.setArt(
        {
            "icon": os.path.join(ADDON_PATH, "resources", "img", icon),
            "thumb": os.path.join(ADDON_PATH, "resources", "img", icon),
            "fanart": os.path.join(ADDON_PATH, "fanart.png"),
        }
    )
    return item


def add_item(list_item, url, magnet, id, title, func, plugin):
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(func, query=f"{url} {magnet} {id} {title}"),
        list_item,
        isFolder=False,
    )


def add_pack_item(list_item, func, debrid_id, debrid_type, plugin):
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(func, query=f"{debrid_id} {debrid_type}"),
        list_item,
        isFolder=True,
    )


def set_video_item(list_item, poster, overview):
    list_item.setArt(
        {
            "poster": poster,
            "thumb": os.path.join(ADDON_PATH, "resources", "img", "magnet.png"),
            "icon": os.path.join(ADDON_PATH, "resources", "img", "magnet.png"),
        }
    )
    info_tag = list_item.getVideoInfoTag()
    info_tag.setMediaType("video")
    info_tag.setPlot(overview)

    list_item.setProperty("IsPlayable", "true")


def set_watched_file(title, id, magnet, url):
    if title not in db.database["jt:watch"]:
        db.database["jt:watch"][title] = True

    db.database["jt:lfh"][title] = {
        "timestamp": datetime.now(),
        "id": id,
        "url": url,
        "magnet": magnet,
    }
    db.commit()


def set_watched_title(title, id, tvdb_id=-1, imdb_id=-1, mode=""):
    if title != "None":
        db.database["jt:lth"][title] = {
            "timestamp": datetime.now(),
            "id": id,
            "tvdb_id": tvdb_id,
            "imdb_id": imdb_id,
            "mode": mode,
        }
        db.commit()


def is_torrent_watched(title):
    return db.database["jt:watch"].get(title, False)


def fanartv_get(id, mode="tv"):
    fanart_data = db.get_fanarttv("jt:fanarttv", id)
    if not fanart_data:
        fanart_data = get_api_fanarttv(mode, "en", id)
        if fanart_data:
            db.set_fanarttv(
                "jt:fanarttv",
                id,
                fanart_data["poster2"],
                fanart_data["fanart2"],
                fanart_data["clearlogo2"],
            )
    return fanart_data


def get_cached(path, params={}):
    identifier = "{}|{}".format(path, params)
    return cache.get(identifier, hashed_key=True)


def set_cached(results, path, params={}):
    identifier = "{}|{}".format(path, params)
    cache.set(
        identifier,
        results,
        timedelta(hours=get_cache_expiration()),
        hashed_key=True,
    )


def db_get(name, func, path, params):
    identifier = "{}|{}".format(path, params)
    data = cache.get(identifier, hashed_key=True)
    if not data:
        if name == "search_api":
            data = func()
        cache.set(
            identifier,
            data,
            timedelta(hours=get_cache_expiration()),
            hashed_key=True,
        )
    return data


def tmdb_get(path, params={}):
    identifier = "{}|{}".format(path, params)
    data = cache.get(identifier, hashed_key=True)
    if not data:
        if path == "search_tv":
            data = Search().tv_shows(params)
        elif path == "search_movie":
            data = Search().movies(params)
        elif path == "movie_details":
            data = Movie().details(params)
        elif path == "tv_details":
            data = TV().details(params)
        elif path == "season_details":
            data = Season().details(params["id"], params["season"])
        elif path == "movie_genres":
            data = Genre().movie_list()
        elif path == "tv_genres":
            data = Genre().tv_list()
        elif path == "discover_movie":
            discover = Discover()
            data = discover.discover_movies(params)
        elif path == "discover_tv":
            discover = Discover()
            data = discover.discover_tv_shows(params)
        elif path == "trending_movie":
            trending = Trending()
            data = trending.movie_week(page=params)
        elif path == "trending_tv":
            trending = Trending()
            data = trending.tv_day(page=params)
        cache.set(
            identifier,
            data,
            timedelta(hours=get_cache_expiration()),
            hashed_key=True,
        )
    return data


# This method was taken from script.elementum.jackett
def get_random_color(provider_name):
    hash = hashlib.sha256(provider_name.encode("utf")).hexdigest()
    colors = []

    spec = 10
    for i in range(0, 3):
        offset = spec * i
        rounded = round(
            int(hash[offset: offset + spec], 16) / int("F" * spec, 16) * 255
        )
        colors.append(int(max(rounded, PROVIDER_COLOR_MIN_BRIGHTNESS)))

    while (sum(colors) / 3) < PROVIDER_COLOR_MIN_BRIGHTNESS:
        for i in range(0, 3):
            colors[i] += 10

    for i in range(0, 3):
        colors[i] = f"{colors[i]:02x}"

    return "FF" + "".join(colors).upper()


def clear_tmdb_cache():
    db.database["jt:tmdb"] = {}
    db.commit()


def clear_all_cache():
    cache.clean_all()
    db.database["jt:tmdb"] = {}
    db.commit()


def clear(type=""):
    dialog = Dialog()
    confirmed = dialog.yesno(
        "Clear History",
        "Do you want to clear this history list?.",
    )
    if confirmed:
        if type == "lth":
            db.database["jt:lth"] = {}
        else:
            db.database["jt:lfh"] = {}
        db.commit()
        container_refresh()


def limit_results(results):
    indexer = get_setting("indexer")
    if indexer == Indexer.JACKETT:
        limit = get_int_setting("jackett_results_per_page")
    elif indexer == Indexer.PROWLARR:
        limit = get_int_setting("prowlarr_results_per_page")
    elif indexer == Indexer.TORRENTIO:
        limit = get_int_setting("torrentio_results_per_page")
    elif indexer == Indexer.ELHOSTED:
        limit = get_int_setting("elfhosted_results_per_page")
    return results[:limit]


def get_description_length():
    indexer = get_setting("indexer")
    if indexer == Indexer.JACKETT:
        desc_length = "jackett_desc_length"
    elif indexer == Indexer.PROWLARR:
        desc_length = "prowlarr_desc_length"
    elif indexer == Indexer.TORRENTIO:
        desc_length = "torrentio_desc_length"
    elif indexer == Indexer.ELHOSTED:
        desc_length = "elfhosted_desc_length"
    return int(get_setting(desc_length))


def remove_duplicate(results):
    seen_values = []
    result_dict = []
    for res in results:
        if res not in seen_values:
            result_dict.append(res)
            seen_values.append(res)
    return result_dict


def process_movie_results(results):
    res = remove_duplicate(results)
    res = limit_results(res)
    res = filter_by_quality(res)
    res = sort_results(res)
    return res


def process_tv_results(results, episode_name, episode, season):
    res = remove_duplicate(results)
    res = limit_results(res)
    # res = filter_by_episode(res, episode_name, episode, season)
    # if res:
    res = filter_by_quality(res)
    res = sort_results(res)
    return res


def sort_results(results):
    indexer = get_setting("indexer")
    if indexer == Indexer.JACKETT:
        sort_by = get_setting("jackett_sort_by")
    elif indexer == Indexer.PROWLARR:
        sort_by = get_setting("prowlarr_sort_by")
    elif indexer == Indexer.TORRENTIO:
        sort_by = get_setting("torrentio_sort_by")
    elif indexer == Indexer.ELHOSTED:
        sort_by = get_setting("elfhosted_sort_by")

    if sort_by == "Seeds":
        sort_results = sorted(results, key=lambda r: int(r["seeders"]), reverse=True)
    elif sort_by == "Size":
        sort_results = sorted(results, key=lambda r: r["size"], reverse=True)
    elif sort_by == "Date":
        sort_results = sorted(results, key=lambda r: r["publishDate"], reverse=True)
    elif sort_by == "Quality":
        sort_results = sorted(results, key=lambda r: r["Quality"], reverse=False)
    elif sort_by == "Cached":
        sort_results = sorted(results, key=lambda r: r["debridCached"], reverse=True)

    return sort_results


def filter_by_episode(results, episode_name, episode_num, season_num):
    episode_num = f"{int(episode_num):02}"
    season_num = f"{int(season_num):02}"

    filtered_episodes = []
    pattern1 = "S%sE%s" % (season_num, episode_num)
    pattern2 = "%sx%s" % (season_num, episode_num)
    pattern3 = "\s%s\s" % (episode_num)
    pattern4 = "\.S%s" % (season_num)
    pattern5 = "\.S%sE%s" % (season_num, episode_num)
    pattern6 = "\sS%sE%s\s" % (season_num, episode_num)

    pattern = "|".join(
        [pattern1, pattern2, pattern3, pattern4, pattern5, pattern6, episode_name]
    )

    for res in results:
        title = res["title"]
        match = re.search(f"r{pattern}", title)
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
            res["quality_title"] = "[B][COLOR orange]480p - [/COLOR][/B]" + res["title"]
            res["Quality"] = "480p"
            quality_720p.append(res)
        elif "720p" in title:
            res["quality_title"] = "[B][COLOR orange]720p - [/COLOR][/B]" + res["title"]
            res["Quality"] = "720p"
            quality_720p.append(res)
        elif "1080p" in title:
            res["quality_title"] = "[B][COLOR blue]1080p - [/COLOR][/B]" + res["title"]
            res["Quality"] = "1080p"
            quality_1080p.append(res)
        elif "2160" in title:
            res["quality_title"] = "[B][COLOR yellow]4k - [/COLOR][/B]" + res["title"]
            res["Quality"] = "4k"
            quality_4k.append(res)
        else:
            res["quality_title"] = "[B][COLOR yellow]N/A - [/COLOR][/B]" + res["title"]
            res["Quality"] = "N/A"
            no_quarlity.append(res)

    combined_list = quality_4k + quality_1080p + quality_720p + no_quarlity
    return combined_list


def supported_video_extensions():
    media_types = getSupportedMedia("video")
    return media_types.split("|")


def get_info_hash(magnet):
    return Magnet.from_string(magnet).infohash


def is_magnet_link(link):
    if link.startswith("magnet:?"):
        return link


def is_url(url):
    return bool(re.match(URL_REGEX, url))


def info_hash_to_magnet(info_hash):
    return f"magnet:?xt=urn:btih:{info_hash}"


""" def direct_download():
    import urllib.request

    url = 'your_file_url'
    file_name = 'your_file_name'

    def reporthook(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = min(int(downloaded * 100 / total_size), 100)
            print(f'Downloading: {percent}%', end='\r')

    urllib.request.urlretrieve(url, file_name, reporthook)
    print('Download complete') """


""" def direct_download(url, file_name):
    progressDialog.create("Download Manager")

    response = requests.get(url, stream=True)
    total_size = int(response.headers.get("content-length", 0))

    with open(file_name, "wb") as file:
        for data in response.iter_content(chunk_size=1024):
            file.write(data)
            content = f"Downloaded: {int(file.tell() / total_size * 100)}%"
            progressDialog.update(-1, content)
            if progressDialog.iscanceled():
                progressDialog.close()
                return

    progressDialog.update(-1, "Download complete.") """
