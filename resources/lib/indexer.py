import re
from resources.lib.anilist import get_anilist_client
from resources.lib.kodi import action, bytes_to_human_readable, get_setting
from resources.lib.tmdbv3api.objs.find import Find
from resources.lib.utils.utils import (
    Indexer,
    add_item,
    add_pack_item,
    fanartv_get,
    get_tracker_color,
    info_hash_to_magnet,
    is_torrent_watched,
    set_video_item,
    tmdb_get,
)
from xbmcgui import ListItem
from xbmcplugin import endOfDirectory


def indexer_show_results(results, mode, id, tvdb_id, plugin, func, func2, func3):
    indexer = get_setting("indexer")
    if indexer == Indexer.JACKETT:
        desc_length = "jackett_desc_length"
    elif indexer == Indexer.PROWLARR:
        desc_length = "prowlarr_desc_length"
    elif indexer == Indexer.TORRENTIO:
        desc_length = "torrentio_desc_length"
    description_length = int(get_setting(desc_length))

    poster = overview = ""

    if id != "-1":  # Direct Search -1
        if mode == "tv":
            result = Find().find_by_tvdb_id(tvdb_id)
            tv_results = result["tv_results"]
            if tv_results:
                overview = tv_results[0]["overview"]
                data = fanartv_get(tvdb_id, mode)
                if data:
                    poster = data["clearlogo2"]
        elif mode == "movie":
            details = tmdb_get("movie_details", id)
            overview = details["overview"] if details.get("overview") else ""
            data = fanartv_get(tvdb_id, mode)
            if data:
                poster = data["clearlogo2"]
        elif mode == "anime":
            _, result = get_anilist_client().get_by_id(id)
            if result:
                overview = result["description"]
                poster = result["coverImage"]["large"]

    for res in results:
        title = res["title"]
        if len(title) > description_length:
            title = title[:description_length]

        qtTitle = res["qtTitle"]
        if len(qtTitle) > description_length:
            qtTitle = qtTitle[:description_length]

        magnet = ""
        date = res.get("publishDate", "")
        match = re.search(r"\d{4}-\d{2}-\d{2}", date)
        if match:
            date = match.group()
        size = bytes_to_human_readable(int(res.get("size")))
        seeders = res["seeders"]
        tracker = res["indexer"]

        watched = is_torrent_watched(qtTitle)
        if watched:
            qtTitle = f"[COLOR palevioletred]{qtTitle}[/COLOR]"

        tracker_color = get_tracker_color(tracker)
        torr_title = f"[B][COLOR {tracker_color}][{tracker}][/COLOR][/B] {qtTitle}[CR][I][LIGHT][COLOR lightgray]{date}, {size}, {seeders} seeds[/COLOR][/LIGHT][/I]"

        if res["rdCached"]:
            rd_links = res.get("rdLinks")
            if rd_links:
                if len(rd_links) > 1:
                    rdId = res.get("rdId")
                    list_item = ListItem(label=f"[B][Pack-Cached][/B]-{torr_title}")
                    add_pack_item(list_item, title, rdId, func2, plugin)
                else:
                    url = rd_links[0]
                    title = f"[B][Cached][/B]-{title}"
                    list_item = ListItem(label=f"[B][Cached][/B]-{torr_title}")
                    set_video_item(list_item, title, poster, overview)
                    add_item(list_item, url, magnet, id, title, func, plugin)
        else:
            downloadUrl = res.get("downloadUrl") or res.get("magnetUrl")
            guid = res.get("guid")
            if guid:
                if Indexer.TORRENTIO:
                    magnet = info_hash_to_magnet(guid)
                else:
                    if guid.startswith("magnet:?"):
                        magnet = guid
                    else:
                        # For some indexers, the guid is a torrent file url
                        downloadUrl = res.get("guid")
            list_item = ListItem(label=torr_title)
            set_video_item(list_item, title, poster, overview)
            if magnet:
                list_item.addContextMenuItems(
                    [("Download to Debrid", action(plugin, func3, query=magnet))]
                )
            add_item(list_item, downloadUrl, magnet, id, title, func, plugin)

    endOfDirectory(plugin.handle)
