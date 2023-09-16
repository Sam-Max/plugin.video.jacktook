from datetime import datetime
import logging
import os
import re
import requests

from resources.lib.clients import Jackett, Prowlarr
from resources.lib.database import Database
from resources.lib.fanarttv import get_api_fanarttv
from resources.lib.kodi import (
    ADDON_PATH,
    bytes_to_human_readable,
    get_int_setting,
    get_setting,
    hide_busy_dialog,
    notify,
)
from resources.lib.kodi import HANDLE, hide_busy_dialog
from urllib3.exceptions import InsecureRequestWarning

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


class Enum:
    @classmethod
    def values(cls):
        return [value for name, value in vars(cls).items() if not name.startswith("_")]


class Indexer(Enum):
    PROWLARR = "Prowlarr"
    JACKETT = "Jackett"


def get_client():
    selected_indexer = get_setting("selected_indexer")

    if selected_indexer == Indexer.JACKETT:
        host = get_setting("jackett_host")
        api_key = get_setting("jackett_apikey")

        if not host or not api_key:
            notify("You need to configure Jackett first")
            return

        if len(api_key) != 32:
            notify("Jackett API key is invalid")
            return

        return Jackett(host, api_key)

    elif selected_indexer == Indexer.PROWLARR:
        host = get_setting("prowlarr_host")
        api_key = get_setting("prowlarr_apikey")

        if not host or not api_key:
            notify("You need to configure Prowlarr first")
            return

        if len(api_key) != 32:
            notify("Prowlarr API key is invalid")
            return

        return Prowlarr(host, api_key)


def search_api(query, mode, tracker):
    query = None if query == "None" else query
    selected_indexer = get_setting("selected_indexer")

    jackett_insecured = get_setting("jackett_insecured")
    prowlarr_insecured = get_setting("prowlarr_insecured")

    if prowlarr_insecured or jackett_insecured:
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

    if selected_indexer == Indexer.JACKETT:
        jackett = get_client()
        if not jackett:
            return

        if query:
            response = jackett.search(query, tracker, mode, jackett_insecured)
        else:
            keyboard = xbmc.Keyboard("", "Search for torrents:", False)
            keyboard.doModal()
            if keyboard.isConfirmed():
                text = keyboard.getText().strip()
                text = quote(text)
                response = jackett.search(text, tracker, mode, jackett_insecured)
            else:
                hide_busy_dialog()
                return
        return response

    elif selected_indexer == Indexer.PROWLARR:
        indexers_ids = get_setting("prowlarr_indexer_ids")
        indexers_ids_list = indexers_ids.split() if indexers_ids else None

        anime_ids = get_setting("prowlarr_anime_indexer_ids")
        anime_indexers_ids_list = anime_ids.split() if anime_ids else None

        prowlarr = get_client()
        if not prowlarr:
            return

        if query:
            response = prowlarr.search(
                query,
                tracker,
                indexers_ids_list,
                anime_indexers_ids_list,
                mode,
                prowlarr_insecured,
            )
        else:
            keyboard = xbmc.Keyboard("", "Search for torrents:", False)
            keyboard.doModal()
            if keyboard.isConfirmed():
                text = keyboard.getText().strip()
                text = quote(text)
                response = prowlarr.search(
                    text,
                    tracker,
                    indexers_ids_list,
                    anime_indexers_ids_list,
                    mode,
                    prowlarr_insecured,
                )
            else:
                hide_busy_dialog()
                return
        return response


def play(url, title, magnet):
    set_watched(title=title, magnet=magnet, url=url)

    magnet = None if magnet == "None" else magnet
    url = None if url == "None" else url

    if magnet is None and url is None:
        notify("No sources found to play")
        return

    torrent_client = get_setting("torrent_client")
    if torrent_client == "Torrest":
        if xbmc.getCondVisibility('System.HasAddon("plugin.video.torrest")'):
            if magnet:
                plugin_url = (
                    "plugin://plugin.video.torrest/play_magnet?magnet=" + quote(magnet)
                )
            elif url:
                plugin_url = "plugin://plugin.video.torrest/play_url?url=" + quote(url)
            setResolvedUrl(HANDLE, True, ListItem(path=plugin_url))
        else:
            notify("You need to install the addon Torrest(plugin.video.torrest)")
            return
    else:
        notify("You need to select a torrent client")


def api_show_results(results, plugin, id, mode, func):
    selected_indexer = get_setting("selected_indexer")

    poster = ""
    if id:
        fanart_data = get_fanartv(id, mode)
        if fanart_data:
            poster = fanart_data["clearlogo2"]

    if selected_indexer == Indexer.JACKETT:
        description_length = int(get_setting("jackett_desc_length"))

        for r in results:
            title = r["Title"]
            if len(title) > description_length:
                title = title[0:description_length]

            date = r["PublishDate"]
            match = re.search(r"\d{4}-\d{2}-\d{2}", date)
            if match:
                date = match.group()

            size = bytes_to_human_readable(r["Size"])
            seeders = r["Seeders"]
            magnet = r["MagnetUri"]
            url = r["Link"]
            tracker = r["Tracker"]

            watched = is_torrent_watched(title)
            if watched:
                title = f"[COLOR palevioletred]{title}[/COLOR]"

            torrent_title = f"[B][COLOR palevioletred][{tracker}][/COLOR][/B] {title}[CR][I][LIGHT][COLOR lightgray]{date}, {size}, {seeders} seeds[/COLOR][/LIGHT][/I]"

            list_item = ListItem(label=torrent_title)
            list_item.setArt(
                {
                    "poster": poster,
                    "thumb": os.path.join(ADDON_PATH, "resources", "img", "magnet.png"),
                    "icon": os.path.join(ADDON_PATH, "resources", "img", "magnet.png"),
                }
            )
            list_item.setInfo(
                "video", {"title": title, "mediatype": "video", "plot": ""}
            )
            list_item.setProperty("IsPlayable", "true")

            addDirectoryItem(
                plugin.handle,
                plugin.url_for(func, query=f"{url} {magnet} {title}"),
                list_item,
                isFolder=False,
            )

        endOfDirectory(plugin.handle)

    elif selected_indexer == Indexer.PROWLARR:
        description_length = int(get_setting("prowlarr_desc_length"))

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

            magnet = None
            guid = r.get("guid")
            if guid and is_magnet_link(guid):
                magnet = r.get("guid")
            else:
                magnetUrl = r.get("magnetUrl")
                if magnetUrl:
                    res = requests.get(magnetUrl, allow_redirects=False)
                    if "location" in res.headers:
                        magnet = res.headers["location"]

            url = r.get("downloadUrl")
            indexer = r["indexer"]

            watched = is_torrent_watched(title)
            if watched:
                title = f"[COLOR palevioletred]{title}[/COLOR]"

            torrent_title = f"[B][COLOR palevioletred][{indexer}][/COLOR][/B] {title}[CR][I][LIGHT][COLOR lightgray]{date}, {size}, {seeders} seeds[/COLOR][/LIGHT][/I]"

            list_item = ListItem(label=torrent_title)
            list_item.setArt(
                {"icon": os.path.join(ADDON_PATH, "resources", "img", "magnet.png")}
            )
            list_item.setInfo(
                "video",
                {"title": title, "mediatype": "video", "plot": ""},
            )
            list_item.setProperty("IsPlayable", "true")

            addDirectoryItem(
                plugin.handle,
                plugin.url_for(func, query=f"{url} {magnet} {title}"),
                list_item,
                False,
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


def save_db_fanarttv(id, poster, fanart, clearlogo):
    db.database["jt:fanarttv"][id] = {
        "poster2": poster,
        "fanart2": fanart,
        "clearlogo2": clearlogo,
    }
    db.commit()


def get_db_fanarttv(id):
    if id in db.database["jt:fanarttv"]:
        return db.database["jt:fanarttv"][id]
    return None


def is_torrent_watched(title):
    return db.database["jt:watch"].get(title, False)


def get_fanartv(id, mode="tv"):
    fanart_data = get_db_fanarttv(id)
    if fanart_data:
        return fanart_data
    else:
        fanart_data, _ = get_api_fanarttv(mode, "en", id)
        if fanart_data:
            poster = fanart_data["poster2"]
            fanart = fanart_data["fanart2"]
            clearlogo2 = fanart_data["clearlogo2"]
            save_db_fanarttv(id, poster, fanart, clearlogo2)
            fanart_data = get_db_fanarttv(id)
            if fanart_data:
                return fanart_data


def clear():
    dialog = Dialog()
    confirmed = dialog.yesno(
        "Clear History",
        "Do you want to clear this history list?.",
    )
    if confirmed:
        db.database["jt:history"] = {}
        db.commit()
        xbmc.executebuiltin("Container.Refresh")


def history(plugin, func1, func2):
    setPluginCategory(plugin.handle, f"Jackett Torrents - History")
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


def limit_results(res):
    selected_indexer = get_setting("selected_indexer")
    rsp = get_int_setting("results_per_page")

    if selected_indexer == Indexer.JACKETT:
        sliced_res = res["Results"][:rsp]
    elif selected_indexer == Indexer.PROWLARR:
        sliced_res = res[:rsp]

    return sliced_res


def sort_results(results):
    selected_indexer = get_setting("selected_indexer")

    if selected_indexer == Indexer.JACKETT:
        sort_by = get_setting("jackett_sort_by")
        if sort_by == "Seeds":
            sorted_results = sorted(
                results, key=lambda r: int(r["Seeders"]), reverse=True
            )
        elif sort_by == "Size":
            sorted_results = sorted(results, key=lambda r: r["Size"], reverse=True)
        elif sort_by == "Date":
            sorted_results = sorted(
                results, key=lambda r: r["PublishDate"], reverse=True
            )
        elif sort_by == "Quality":
            sorted_results = sorted(results, key=lambda r: r["Quality"], reverse=False)
    elif selected_indexer == Indexer.PROWLARR:
        sort_by = get_setting("prowlarr_sort_by")
        if sort_by == "Seeds":
            sorted_results = sorted(
                results, key=lambda r: int(r["seeders"]), reverse=True
            )
        elif sort_by == "Size":
            sorted_results = sorted(results, key=lambda r: r["size"], reverse=True)
        elif sort_by == "Date":
            sorted_results = sorted(
                results, key=lambda r: r["publishDate"], reverse=True
            )
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

    jackett = False
    prowlarr = False

    selected_indexer = get_setting("selected_indexer")
    if selected_indexer == Indexer.JACKETT:
        jackett = True
        results = results["Results"]
    elif selected_indexer == Indexer.PROWLARR:
        prowlarr = True
        results = results

    for res in results:
        if jackett:
            title = res["Title"]
        elif prowlarr:
            title = res["title"]
        match = re.search(r"{}".format(pattern), title)
        if match:
            filtered_episodes.append(res)
    return filtered_episodes


def filter_by_quality(results, mode=""):
    quality_720p = []
    quality_1080p = []
    quality_4k = []

    jackett = False
    prowlarr = False

    selected_indexer = get_setting("selected_indexer")
    if selected_indexer == Indexer.JACKETT:
        jackett = True
        if mode == "tv_episode":
            results = results
        else:
            results = results["Results"]
    elif selected_indexer == Indexer.PROWLARR:
        prowlarr = True
        results = results

    for res in results:
        if jackett:
            matches = re.findall(r"\b\d+p\b|\b\d+k\b", res["Title"])
        elif prowlarr:
            matches = re.findall(r"\b\d+p\b|\b\d+k\b", res["title"])

        for match in matches:
            if "720p" in match:
                if jackett:
                    res["Title"] = "[B][COLOR orange]720p - [/COLOR][/B]" + res["Title"]
                elif prowlarr:
                    res["title"] = "[B][COLOR orange]720p - [/COLOR][/B]" + res["title"]
                res["Quality"] = "720p"
                quality_720p.append(res)
            elif "1080p" in match:
                if jackett:
                    res["Title"] = "[B][COLOR blue]1080p - [/COLOR][/B]" + res["Title"]
                elif prowlarr:
                    res["title"] = "[B][COLOR blue]1080p - [/COLOR][/B]" + res["title"]
                res["Quality"] = "1080p"
                quality_1080p.append(res)
            elif "4k" in match:
                if jackett:
                    res["Title"] = "[B][COLOR yellow]4k - [/COLOR][/B]" + res["Title"]
                elif prowlarr:
                    res["title"] = "[B][COLOR yellow]4k - [/COLOR][/B]" + res["title"]
                res["Quality"] = "4k"
                quality_4k.append(res)

    combined_list = quality_4k + quality_1080p + quality_720p
    return combined_list


def is_magnet_link(link):
    pattern = r"^magnet:\?xt=urn:btih:[a-fA-F0-9]{40}&dn=.+&tr=.+$"
    return bool(re.match(pattern, link))


