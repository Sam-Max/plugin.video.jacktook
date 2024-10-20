import re
from lib.api.jacktook.kodi import kodilog
from lib.tmdb import TMDB_POSTER_URL
from lib.utils.kodi_utils import (
    action_url_run,
    bytes_to_human_readable,
    container_update,
    get_setting,
)
from lib.utils.utils import (
    Indexer,
    add_pack_item,
    add_play_item,
    get_colored_languages,
    get_description_length,
    get_random_color,
    info_hash_to_magnet,
    is_torrent_url,
    is_torrent_watched,
    set_video_properties,
    tmdb_get,
)
from xbmcgui import ListItem


def show_indexers_results(results, mode, ids, tv_data, direct, plugin):
    description_length = get_description_length()
    if ids:
        tmdb_id, _, _ = ids.split(", ")

    poster = overview = ""
    if not direct:
        if mode in ["tv", "anime"]:
            details = tmdb_get("tv_details", tmdb_id)
            poster = TMDB_POSTER_URL + details.poster_path if details.poster_path else ""
            overview = details.overview if details.overview else ""  
        elif mode == "movie":
            details = tmdb_get("movie_details", tmdb_id)
            poster = TMDB_POSTER_URL + details.poster_path if details.poster_path else ""
            overview = details.overview if details.overview else ""  
        elif mode == "multi":
            pass

    for res in results:
        title = res["title"]
        if len(title) > description_length:
            title = title[:description_length]

        quality_title = res.get("qualityTitle", "")
        if len(quality_title) > description_length:
            quality_title = quality_title[:description_length]

        date = res.get("publishDate", "")
        match = re.search(r"\d{4}-\d{2}-\d{2}", date)
        if match:
            date = match.group()
        
        size = bytes_to_human_readable(int(res.get("size", 0)))
        seeders = res.get("seeders", "")
        tracker = res["indexer"]

        watched = is_torrent_watched(quality_title)
        if watched:
            quality_title = f"[COLOR palevioletred]{quality_title}[/COLOR]"

        tracker_color = get_random_color(tracker)

        languages = get_colored_languages(res.get("fullLanguages", []))
        languages = languages if languages else ""

        providers = res.get("provider", "")
        providers_color = get_random_color(providers)

        torr_title = (
            f"[B][COLOR {tracker_color}][{tracker}][/COLOR][/B] - {quality_title}[CR]"
            f"[I][LIGHT][COLOR lightgray]{date}, {size}, {seeders} seeds[/COLOR][/LIGHT][/I]"
            f"{f'[I][LIGHT][COLOR lightgray]{languages}[/COLOR][/LIGHT][/I]' if languages else ''}"
            f"{f'[I][B][COLOR {providers_color}]-{providers}[/COLOR][/B][/I]'  if providers else ''}"
        )

        debrid_type = res.get("debridType", "")
        debrid_color = get_random_color(debrid_type)
        format_debrid_type = f"[B][COLOR {debrid_color}][{debrid_type}][/COLOR][/B]"

        if res.get("isDebrid"):
            info_hash = res.get("infoHash")
            if res.get("isDebridPack"):
                list_item = ListItem(
                    label=f"{format_debrid_type}-Cached-Pack-{torr_title}"
                )
                add_pack_item(
                    list_item,
                    tv_data,
                    ids,
                    info_hash,
                    debrid_type,
                    mode,
                    plugin,
                )
            else:
                title = f"[B][Cached][/B]-{title}"
                list_item = ListItem(
                    label=f"{format_debrid_type}-Cached-{torr_title}"
                )
                set_video_properties(list_item, poster, mode, title, overview, ids)
                list_item.addContextMenuItems(
                    [
                        (
                            "Check if Pack",
                            container_update(
                                name="show_pack_info",
                                ids=ids,
                                debrid_type=debrid_type,
                                info_hash=info_hash,
                                mode=mode,
                                tv_data=tv_data,
                            ),
                        )
                    ]
                )
                add_play_item(
                    list_item,
                    ids,
                    tv_data,
                    title,
                    info_hash=info_hash,
                    debrid_type=debrid_type,
                    mode=mode,
                    plugin=plugin,
                )

        elif res.get("isPlex"):
            url = res.get("downloadUrl")
            list_item = ListItem(label=torr_title)
            set_video_properties(list_item, poster, mode, title, overview, ids)
            add_play_item(
                list_item,
                ids,
                tv_data,
                title,
                url,
                is_plex=True,
                mode=mode,
                plugin=plugin,
            )
        else:
            magnet = ""
            url = ""
            if guid := res.get("guid"):
                if res.get("indexer") in [
                    Indexer.TORRENTIO,
                    Indexer.ELHOSTED,
                    Indexer.ZILEAN,
                ]:
                    magnet = info_hash_to_magnet(guid)
                else:
                    if guid.startswith("magnet:?"):
                        magnet = guid
                    else:
                        # For some indexers, the guid is a torrent file url
                        if is_torrent_url(guid):
                            url = guid
            if not url:
                _url = res.get("magnetUrl", "") or res.get("downloadUrl", "")
                if _url.startswith("magnet:?"):
                    magnet = _url
                else:
                    url = _url

            list_item = ListItem(label=torr_title)
            set_video_properties(list_item, poster, mode, title, overview, ids)
            if magnet:
                list_item.addContextMenuItems(
                    [
                        (
                            "Download to Debrid",
                            action_url_run(
                                name="download_to_debrid",
                                magnet=magnet,
                                debrid_type=debrid_type,
                            ),
                        )
                    ]
                )
            add_play_item(
                list_item,
                ids,
                tv_data,
                title,
                magnet=magnet,
                url=url,
                is_torrent=True,
                mode=mode,
                plugin=plugin,
            )
