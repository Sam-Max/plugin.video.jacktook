from datetime import datetime, timedelta
import hashlib
import io
import os
import re
from threading import Thread
import requests
from resources.lib.anilist import get_anime_client
from resources.lib.cached import Cache
from resources.lib.player import JacktookPlayer
from resources.lib.tmdbv3api.objs.find import Find
from resources.lib.tmdbv3api.objs.movie import Movie

from resources.lib.torf._torrent import Torrent
from resources.lib.torf._magnet import Magnet
from resources.lib.database import Database
from resources.lib.fanarttv import get_api_fanarttv
from resources.lib.kodi import (
    ADDON_PATH,
    action,
    bytes_to_human_readable,
    container_refresh,
    get_cache_expiration,
    get_int_setting,
    get_setting,
    is_torrest_addon,
    log,
    notify,
    translation,
)

from resources.lib.tmdbv3api.objs.discover import Discover
from resources.lib.tmdbv3api.objs.trending import Trending

from xbmcgui import ListItem, Dialog
from xbmcplugin import (
    addDirectoryItem,
    endOfDirectory,
    setPluginCategory,
    setResolvedUrl,
)
from xbmc import getSupportedMedia
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


def show_search_result(results, mode, id, plugin, func, func2, func3):
    api_show_results(results, plugin, id, mode, func=func, func2=func2, func3=func3)


def show_tv_result(results, mode, tvdb_id, plugin, func, func2, func3):
    api_show_results(
        results, plugin, tvdb_id, mode=mode, func=func, func2=func2, func3=func3
    )


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


def api_show_results(results, plugin, id, mode, func, func2, func3):
    indexer = get_setting("indexer")
    if indexer == Indexer.JACKETT:
        description_length = int(get_setting("jackett_desc_length"))
    elif indexer == Indexer.PROWLARR:
        description_length = int(get_setting("prowlarr_desc_length"))

    poster = ""
    overview = ""

    if int(id) != -1:
        data = fanartv_get(id, mode)
        if data:
            poster = data["clearlogo2"]

        if mode == "tv":
            result = Find().find_by_tvdb_id(id)
            overview = result["tv_results"][0]["overview"]
        elif mode == "movie":
            details = Movie().details(id)
            overview = details["overview"] if details.get("overview") else ""
        elif mode == "anime":
            anime = get_anime_client()
            result = anime.get_by_id(id)
            if result:
                overview = result["description"]
                poster = result["coverImage"]["large"]

    for r in results:
        title = r["title"]
        if len(title) > description_length:
            title = title[:description_length]

        qtTitle = r["qtTitle"]
        if len(qtTitle) > description_length:
            qtTitle = qtTitle[:description_length]

        magnet = ""
        date = r.get("publishDate", "")
        match = re.search(r"\d{4}-\d{2}-\d{2}", date)
        if match:
            date = match.group()
        size = bytes_to_human_readable(int(r.get("size")))
        seeders = r["seeders"]
        tracker = r["indexer"]

        watched = is_torrent_watched(qtTitle)
        if watched:
            qtTitle = f"[COLOR palevioletred]{qtTitle}[/COLOR]"

        tracker_color = get_tracker_color(tracker)
        torr_title = f"[B][COLOR {tracker_color}][{tracker}][/COLOR][/B] {qtTitle}[CR][I][LIGHT][COLOR lightgray]{date}, {size}, {seeders} seeds[/COLOR][/LIGHT][/I]"

        if r["rdCached"]:
            links = r.get("rdLinks", "")
            if len(links) > 0:
                url = links[0]
                title = f"[B][Cached][/B]-{title}"
                list_item = ListItem(label=f"[B][Cached][/B]-{torr_title}")
                set_video_item(list_item, title, poster, overview)
                add_item(list_item, url, magnet, id, title, func, plugin)
            else:
                rdId = r.get("rdId")
                list_item = ListItem(label=f"[B][Pack-Cached][/B]-{torr_title}")
                add_pack_item(list_item, title, rdId, func2, plugin)
        else:
            url = r.get("downloadUrl", "")
            guid = r.get("guid", "")
            if guid.startswith("magnet:?"):
                magnet = guid
            else:
                uri = r.get("magnetUrl")
                if uri:
                    magnet = get_magnet_from_uri(uri)
            list_item = ListItem(label=torr_title)
            set_video_item(list_item, title, poster, overview)
            if magnet:
                list_item.addContextMenuItems(
                    [("Download to Debrid", action(plugin, func3, query=magnet))]
                )
            add_item(list_item, url, magnet, id, title, func, plugin)

    endOfDirectory(plugin.handle)


def add_item(list_item, url, magnet, id, title, func, plugin):
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(func, query=f"{url} {magnet} {id} {title}"),
        list_item,
        isFolder=False,
    )


def add_pack_item(list_item, title, id, func, plugin):
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(func, query=f"{id} {title}"),
        list_item,
        isFolder=True,
    )


def list_pack_torrent(id, func, client, plugin):
    try:
        cached = False
        links = get_cached_db(id)
        if links:
            cached = True
        else:
            torr_info = client.get_torrent_info(id)
            files = torr_info["files"]
            extensions = supported_video_extensions()[:-1]
            torr_names = [
                item["path"]
                for item in files
                for x in extensions
                if item["path"].lower().endswith(x)
            ]
            links = []
            for i, name in enumerate(torr_names):
                title = f"[B][Cached][/B]-{name.split('/', 1)[1]}"
                response = client.create_download_link(torr_info["links"][i])
                links.append((response["download"], title))
            if links:
                set_cached_db(links, id)
                cached = True
        if cached:
            for link, title in links:
                list_item = ListItem(label=f"{title}")
                set_video_item(list_item, title, "", "")
                add_item(
                    list_item,
                    link,
                    magnet="",
                    id="",
                    title=title,
                    func=func,
                    plugin=plugin,
                )
            endOfDirectory(plugin.handle)
    except Exception as e:
        log(f"Error {str(e)}")


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


def set_video_item(list_item, title, poster, overview):
    list_item.setArt(
        {
            "poster": poster,
            "thumb": os.path.join(ADDON_PATH, "resources", "img", "magnet.png"),
            "icon": os.path.join(ADDON_PATH, "resources", "img", "magnet.png"),
        }
    )
    list_item.setInfo("video", {"title": title, "mediatype": "video", "plot": overview})
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


def set_watched_title(title, id, mode=""):
    if title != "None":
        db.database["jt:lth"][title] = {
            "timestamp": datetime.now(),
            "id": id,
            "mode": mode,
        }
        db.commit()


def is_torrent_watched(title):
    return db.database["jt:watch"].get(title, False)


def fanartv_get(id, mode="tv"):
    if mode == "anime":
        return
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


def get_cached_db(path, params={}):
    identifier = "{}|{}".format(path, params)
    return cache.get(identifier, hashed_key=True)


def set_cached_db(results, path, params={}):
    identifier = "{}|{}".format(path, params)
    cache.set(
        identifier,
        results,
        timedelta(hours=get_cache_expiration()),
        hashed_key=True,
    )


def tmdb_get(path, params):
    identifier = "{}|{}".format(path, params)
    data = cache.get(identifier, hashed_key=True)
    if not data:
        if path == "discover_movie":
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


def last_titles(plugin, func1, func2, func3):
    setPluginCategory(plugin.handle, f"Last Titles - History")

    addDirectoryItem(
        plugin.handle, plugin.url_for(func1, type="lth"), ListItem(label="Clear")
    )

    for title, data in reversed(db.database["jt:lth"].items()):
        formatted_time = data["timestamp"].strftime("%a, %d %b %Y %I:%M %p")
        list_item = ListItem(label=f"{title}— {formatted_time}")
        list_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png")}
        )
        list_item.setProperty("IsPlayable", "false")

        mode = data["mode"]
        id = data.get("id")

        if mode == "tv":
            addDirectoryItem(
                plugin.handle,
                plugin.url_for(
                    func2,
                    id=id,
                ),
                list_item,
                isFolder=True,
            )
        else:
            addDirectoryItem(
                plugin.handle,
                plugin.url_for(func3, mode=mode, query=title, id=id),
                list_item,
                isFolder=True,
            )
    endOfDirectory(plugin.handle)


def last_files(plugin, func1, func2):
    setPluginCategory(plugin.handle, f"Last Files - History")

    addDirectoryItem(
        plugin.handle,
        plugin.url_for(func1, type="lfh"),
        ListItem(label="Clear History"),
    )

    for title, data in reversed(db.database["jt:lfh"].items()):
        formatted_time = data["timestamp"].strftime("%a, %d %b %Y %I:%M %p")
        label = f"{title}—{formatted_time}"
        list_item = ListItem(label=label)
        list_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "magnet.png")}
        )
        list_item.setProperty("IsPlayable", "true")
        addDirectoryItem(
            plugin.handle,
            plugin.url_for(
                func2,
                query=f"{data.get('url', None)} {data.get('magnet', None)} {data.get('id')} {title}",
            ),
            list_item,
            False,
        )
    endOfDirectory(plugin.handle)


def limit_results(results):
    indexer = get_setting("indexer")
    if indexer == Indexer.JACKETT:
        limit = get_int_setting("jackett_results_per_page")
        results = results[:limit]
    elif indexer == Indexer.PROWLARR:
        limit = get_int_setting("prowlarr_results_per_page")
        results = results[:limit]
    return results


def remove_duplicate(results):
    seen_values = []
    result_dict = []
    for res in results:
        if res not in seen_values:
            result_dict.append(res)
            seen_values.append(res)
    return result_dict


def process_results(results):
    res = remove_duplicate(results)
    res = limit_results(res)
    res = filter_by_quality(res)
    res = sort_results(res)
    return res


def process_tv_results(results, episode_name, episode_num, season_num):
    res = remove_duplicate(results)
    res = limit_results(res)
    res = filter_by_episode(res, episode_name, episode_num, season_num)
    if res:
        res = filter_by_quality(res)
        res = sort_results(res)
        return res
    else:
        notify("No episodes found")


def sort_results(results):
    indexer = get_setting("indexer")
    if indexer == Indexer.JACKETT:
        sort_by = get_setting("jackett_sort_by")
    elif indexer == Indexer.PROWLARR:
        sort_by = get_setting("prowlarr_sort_by")

    if sort_by == "Seeds":
        sort_results = sorted(results, key=lambda r: int(r["seeders"]), reverse=True)
    elif sort_by == "Size":
        sort_results = sorted(results, key=lambda r: r["size"], reverse=True)
    elif sort_by == "Date":
        sort_results = sorted(results, key=lambda r: r["publishDate"], reverse=True)
    elif sort_by == "Quality":
        sort_results = sorted(results, key=lambda r: r["Quality"], reverse=False)
    elif sort_by == "Cached":
        sort_results = sorted(results, key=lambda r: r["rdCached"], reverse=True)

    return sort_results


def filter_by_episode(results, episode_name, episode_num, season_num):
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
            res["qtTitle"] = "[B][COLOR orange]480p - [/COLOR][/B]" + res["title"]
            res["Quality"] = "480p"
            quality_720p.append(res)
        elif "720p" in title:
            res["qtTitle"] = "[B][COLOR orange]720p - [/COLOR][/B]" + res["title"]
            res["Quality"] = "720p"
            quality_720p.append(res)
        elif "1080p" in title:
            res["qtTitle"] = "[B][COLOR blue]1080p - [/COLOR][/B]" + res["title"]
            res["Quality"] = "1080p"
            quality_1080p.append(res)
        elif "2160" in title:
            res["qtTitle"] = "[B][COLOR yellow]4k - [/COLOR][/B]" + res["title"]
            res["Quality"] = "4k"
            quality_4k.append(res)
        else:
            res["qtTitle"] = "[B][COLOR yellow]N/A - [/COLOR][/B]" + res["title"]
            res["Quality"] = "N/A"
            no_quarlity.append(res)

    combined_list = quality_4k + quality_1080p + quality_720p + no_quarlity
    return combined_list


def get_magnet_from_uri(uri):
    magnet_prefix = "magnet:"
    res = requests.get(uri, allow_redirects=False)
    if res.is_redirect:
        uri = res.headers["Location"]
        if uri.startswith(magnet_prefix):
            return uri
    elif (
        res.status_code == 200
        and res.headers.get("Content-Type") == "application/x-bittorrent"
    ):
        torrent = Torrent.read_stream(io.BytesIO(res.content))
        return str(torrent.magnet())
    else:
        log(f"Could not get final redirect location for URI {uri}")


def check_debrid_cached(results, client, dialog):
    dialog.update(50, "Jacktook [COLOR FFFF6B00]Debrid[/COLOR]", "Searching...")
    threads = []
    cached_results = []
    uncached_results = []
    hashes = "/".join([res["infoHash"] for res in results if res.get("infoHash")])
    if hashes:
        torr_available = client.get_torrent_instant_availability(hashes)
        magnet = ""
        for res in results:
            guid = res.get("guid", "")
            if guid.startswith("magnet:?"):
                magnet = guid
            else:
                uri = res.get("magnetUrl") or res.get("downloadUrl")
                if uri:
                    magnet = get_magnet_from_uri(uri)
            if magnet:
                infoHash = res.get("infoHash")
                if infoHash in torr_available:
                    info = torr_available[infoHash]
                    if isinstance(info, dict) and len(info.get("rd")) > 0:
                        res["rdCached"] = True
                        cached_results.append(res)
                    else:
                        res["rdCached"] = False
                        uncached_results.append(res)
                    thread = Thread(target=get_dd_link, args=(client, magnet, res))
                    threads.append(thread)
                else:
                    res["rdCached"] = False
                    uncached_results.append(res)
        [i.start() for i in threads]
        [i.join() for i in threads]
        if get_setting("show_uncached"):
            cached_results.extend(uncached_results)
            return cached_results
        else:
            return cached_results


def get_dd_link(rd_client, magnet, res):
    try:
        response = rd_client.add_magent_link(magnet)
        torr_info = rd_client.get_torrent_info(response["id"])
        if torr_info["status"] == "waiting_files_selection":
            files = torr_info["files"]
            extensions = supported_video_extensions()[:-1]
            torr_keys = [
                str(item["id"])
                for item in files
                for x in extensions
                if item["path"].lower().endswith(x)
            ]
            torr_keys = ",".join(torr_keys)
            rd_client.select_files(torr_info["id"], torr_keys)
        torr_info = rd_client.get_torrent_info(response["id"])
        if len(torr_info["links"]) > 1:
            res["rdId"] = response["id"]
        else:
            response = rd_client.create_download_link(torr_info["links"][0])
            res["rdLinks"] = [response["download"]]
    except Exception as e:
        log(f"Error {str(e)}")


def supported_video_extensions():
    media_types = getSupportedMedia("video")
    return media_types.split("|")


def get_info_hash(magnet):
    return Magnet.from_string(magnet).infohash


def is_magnet_link(link):
    if link.startswith("magnet:?"):
        return link


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
