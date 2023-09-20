from datetime import datetime, timedelta
import hashlib
import io
import os
import re
import requests
from resources.lib.cached import Cache

from resources.lib.torf._torrent import Torrent
from resources.lib.torf._magnet import Magnet
from resources.lib.database import Database
from resources.lib.fanarttv import get_api_fanarttv
from resources.lib.kodi import (
    ADDON_PATH,
    bytes_to_human_readable,
    container_refresh,
    get_cache_expiration,
    get_int_setting,
    get_setting,
    log,
    notify,
    translation,
)

from resources.lib.tmdbv3api.objs.discover import Discover
from resources.lib.tmdbv3api.objs.trending import Trending

import xbmc
from xbmcgui import ListItem, Dialog
from xbmcplugin import (
    addDirectoryItem,
    endOfDirectory,
    setPluginCategory,
    setResolvedUrl,
)

from urllib.parse import quote

db = Database()
cache = Cache.get_instance()

PROVIDER_COLOR_MIN_BRIGHTNESS = 50


class Enum:
    @classmethod
    def values(cls):
        return [value for name, value in vars(cls).items() if not name.startswith("_")]


class Indexer(Enum):
    PROWLARR = "Prowlarr"
    JACKETT = "Jackett"


def play(url, title, magnet, plugin):
    set_watched(title=title, magnet=magnet, url=url)

    magnet = None if magnet == "None" else magnet
    url = None if url == "None" else url

    if magnet is None and url is None:
        notify(translation(30251))
        return

    torrent_client = get_setting("torrent_client")
    if torrent_client == "Torrest":
        if xbmc.getCondVisibility('System.HasAddon("plugin.video.torrest")'):
            if magnet:
                plugin_url = (
                    "plugin://plugin.video.torrest/play_magnet?magnet=" + quote(magnet)
                )
                setResolvedUrl(plugin.handle, True, ListItem(path=plugin_url))
            elif url:
                plugin_url = "plugin://plugin.video.torrest/play_url?url=" + quote(url)
                setResolvedUrl(plugin.handle, True, ListItem(path=plugin_url))
        else:
            notify(translation(30250))
            return


def api_show_results(results, plugin, id, mode, func):
    selected_indexer = get_setting("selected_indexer")
    if selected_indexer == Indexer.JACKETT:
        description_length = int(get_setting("jackett_desc_length"))
    elif selected_indexer == Indexer.PROWLARR:
        description_length = int(get_setting("prowlarr_desc_length"))

    if id:
        fanart_data = fanartv_get(id, mode)
        poster = fanart_data["clearlogo2"] if fanart_data else ""

    for r in results:
        title = r["title"]
        if len(title) > description_length:
            title = title[0:description_length]

        date = r["publishDate"]
        match = re.search(r"\d{4}-\d{2}-\d{2}", date)
        if match:
            date = match.group()
        size = bytes_to_human_readable(r["size"])
        seeders = r["seeders"]
        tracker = r["indexer"]

        magnet = None
        guid = r.get("guid")
        if guid and is_magnet_link(guid):
            magnet = guid
        else:
            magnetUrl = r.get("magnetUrl")
            magnet = get_magnet(magnetUrl)
        url = r.get("downloadUrl")

        watched = is_torrent_watched(title)
        if watched:
            title = f"[COLOR palevioletred]{title}[/COLOR]"
        tracker_color = get_tracker_color(tracker)

        torr_title = f"[B][COLOR {tracker_color}][{tracker}][/COLOR][/B] {title}[CR][I][LIGHT][COLOR lightgray]{date}, {size}, {seeders} seeds[/COLOR][/LIGHT][/I]"

        list_item = ListItem(label=torr_title)
        list_item.setArt(
            {
                "poster": poster,
                "thumb": os.path.join(ADDON_PATH, "resources", "img", "magnet.png"),
                "icon": os.path.join(ADDON_PATH, "resources", "img", "magnet.png"),
            }
        )
        list_item.setInfo("video", {"title": title, "mediatype": "video", "plot": ""})
        list_item.setProperty("IsPlayable", "true")

        addDirectoryItem(
            plugin.handle,
            plugin.url_for(func, query=f"{url} {magnet} {title}"),
            list_item,
            isFolder=False,
        )

    endOfDirectory(plugin.handle)


def set_watched(title, magnet, url):
    if title not in db.database["jt:watch"]:
        db.database["jt:watch"][title] = True

    db.database["jt:history"][title] = {
        "timestamp": datetime.now(),
        "url": url,
        "magnet": magnet,
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


def tmdb_get(path, params):
    identifier = "{}|{}".format(path, params)
    data = cache.get(identifier, hashed_key=True)
    if not data:
        if path == "discover_movie":
            discover = Discover()
            tmdb_data = discover.discover_movies(params)
        elif path == "discover_tv":
            discover = Discover()
            tmdb_data = discover.discover_tv_shows(params)
        elif path == "trending_movie":
            trending = Trending()
            tmdb_data = trending.movie_week(page=params)
        elif path == "trending_tv":
            trending = Trending()
            tmdb_data = trending.tv_day(page=params)
        cache.set(
            identifier,
            tmdb_data,
            timedelta(hours=get_cache_expiration()),
            hashed_key=True,
        )
    return tmdb_data


# This method was taken from script.elementum.jackett
def get_tracker_color(provider_name):
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


def clear_tmdb_cache():
    db.database["jt:tmdb"] = {}
    db.commit()


def clear():
    dialog = Dialog()
    confirmed = dialog.yesno(
        "Clear History",
        "Do you want to clear this history list?.",
    )
    if confirmed:
        db.database["jt:history"] = {}
        db.commit()
        container_refresh()


def history(plugin, func1, func2):
    setPluginCategory(plugin.handle, f"Torrents - History")
    list_item = ListItem(label="Clear History")
    addDirectoryItem(plugin.handle, plugin.url_for(func1), list_item)

    for title, data in reversed(db.database["jt:history"].items()):
        formatted_time = data["timestamp"].strftime("%a, %d %b %Y %I:%M %p")
        label = f"[COLOR palevioletred]{title} [I][LIGHT]— {formatted_time}[/LIGHT][/I][/COLOR]"

        list_item = ListItem(label=label)
        list_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "magnet.png")}
        )
        list_item.setProperty("IsPlayable", "true")

        addDirectoryItem(
            plugin.handle,
            plugin.url_for(
                func2,
                query=f"{data.get('url', None)} {data.get('magnet', None)} {title}",
            ),
            list_item,
            False,
        )

    endOfDirectory(plugin.handle)


def limit_results(results):
    selected_indexer = get_setting("selected_indexer")
    rsp = get_int_setting("results_per_page")

    if selected_indexer == Indexer.JACKETT:
        sliced_res = results[:rsp]
    elif selected_indexer == Indexer.PROWLARR:
        sliced_res = results[:rsp]

    return sliced_res


def sort_results(results):
    selected_indexer = get_setting("selected_indexer")

    if selected_indexer == Indexer.JACKETT:
        sort_by = get_setting("jackett_sort_by")
    elif selected_indexer == Indexer.PROWLARR:
        sort_by = get_setting("prowlarr_sort_by")

    if sort_by == "Seeds":
        sorted_results = sorted(results, key=lambda r: int(r["seeders"]), reverse=True)
    elif sort_by == "Size":
        sorted_results = sorted(results, key=lambda r: r["size"], reverse=True)
    elif sort_by == "Date":
        sorted_results = sorted(results, key=lambda r: r["publishDate"], reverse=True)
    elif sort_by == "Quality":
        sorted_results = sorted(results, key=lambda r: r["Quality"], reverse=False)

    return sorted_results


def filter_by_episode(results, episode_name, episode_num, season_num):
    filtered_episodes = []
    pattern1 = "S%sE%s" % (season_num, episode_num)
    pattern2 = "%sx%s" % (season_num, episode_num)
    pattern3 = "\s%s\s" % (episode_num)
    pattern4 = "\sS%s\s" % (season_num)

    pattern = "|".join([pattern1, pattern2, pattern3, pattern4, episode_name])

    for res in results:
        title = res["title"]
        match = re.search(r"{}".format(pattern), title)
        if match:
            filtered_episodes.append(res)
    return filtered_episodes


def filter_by_quality(results):
    quality_720p = []
    quality_1080p = []
    quality_4k = []

    for res in results:
        matches = re.findall(r"\b\d+p\b|\b\d+k\b", res["title"])
        for match in matches:
            if "720p" in match:
                res["title"] = "[B][COLOR orange]720p - [/COLOR][/B]" + res["title"]
                res["Quality"] = "720p"
                quality_720p.append(res)
            elif "1080p" in match:
                res["title"] = "[B][COLOR blue]1080p - [/COLOR][/B]" + res["title"]
                res["Quality"] = "1080p"
                quality_1080p.append(res)
            elif "4k" in match:
                res["title"] = "[B][COLOR yellow]4k - [/COLOR][/B]" + res["title"]
                res["Quality"] = "4k"
                quality_4k.append(res)

    combined_list = quality_4k + quality_1080p + quality_720p
    return combined_list


def get_magnet(uri):
    if uri is None:
        return

    magnet_prefix = "magnet:"
    uri = uri

    if len(uri) >= len(magnet_prefix) and uri[0:7] == magnet_prefix:
        return uri
    res = requests.get(uri, allow_redirects=False)
    if res.is_redirect:
        uri = res.headers["Location"]
        if len(uri) >= len(magnet_prefix) and uri[0:7] == magnet_prefix:
            return uri
    elif (
        res.status_code == 200
        and res.headers.get("Content-Type") == "application/x-bittorrent"
    ):
        torrent = Torrent.read_stream(io.BytesIO(res.content))
        return str(torrent.magnet())
    else:
        log(f"Could not get final redirect location for URI {uri}")


def get_info_hash(magnet):
    return Magnet.from_string(magnet).infohash


def is_magnet_link(link):
    pattern = r"^magnet:\?xt=urn:btih:[a-fA-F0-9]{40}&dn=.+&tr=.+$"
    return bool(re.match(pattern, link))
