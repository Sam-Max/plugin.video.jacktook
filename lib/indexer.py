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
    is_torrent_watched,
    set_video_properties,
    tmdb_get,
)
from xbmcgui import ListItem


def show_indexers_results(res, mode, ids, tv_data, direct, plugin):
    kodilog("indexer::show_indexers_results")
    description_length = get_description_length()

    tmdb_id = ids.split(", ")[0] if ids else None
    poster, overview = get_media_details(tmdb_id, mode) if not direct else ("", "")

    title = truncate(res["title"], description_length)
    quality_title = truncate(res.get("qualityTitle", ""), description_length)
    date = extract_publish_date(res.get("publishDate", ""))
    size = bytes_to_human_readable(int(res.get("size", 0)))
    seeders = format_seeders(res.get("seeders", ""))
    tracker = res["indexer"]
    watched = is_torrent_watched(quality_title)
    if watched:
        quality_title = f"[COLOR palevioletred]{quality_title}[/COLOR]"
    tracker_color = get_random_color(tracker)
    languages = get_colored_languages(res.get("fullLanguages", []))
    languages = languages if languages else ""
    providers = res.get("provider", "")
    providers_color = get_random_color(providers)

    formated_title = (
        f"[B][COLOR {tracker_color}][{tracker}][/COLOR][/B] - {quality_title}[CR]"
        f"[I][LIGHT][COLOR lightgray]{date}, {size}, {seeders}[/COLOR][/LIGHT][/I]"
        f"{f'[I][LIGHT][COLOR lightgray]{languages}[/COLOR][/LIGHT][/I]' if languages else ''}"
        f"{f'[I][B][COLOR {providers_color}]-{providers}[/COLOR][/B][/I]'  if providers else ''}"
    )

    debrid_type = res.get("debridType", "")
    debrid_color = get_random_color(debrid_type)
    format_debrid_type = f"[B][COLOR {debrid_color}][{debrid_type}][/COLOR][/B]"

    if res.get("isDebrid"):
        handle_debrid_items(
            res,
            format_debrid_type,
            formated_title,
            tv_data,
            ids,
            poster,
            title,
            overview,
            mode,
            plugin,
        )
    elif get_setting("indexer") == Indexer.JACKGRAM:
        handle_jackgram_items(
            res, formated_title, tv_data, ids, poster, title, overview, mode, plugin
        )
    else:
        handle_torrent_items(
            res, formated_title, tv_data, ids, poster, title, overview, mode, plugin
        )


def handle_debrid_items(
    res,
    format_debrid_type,
    formated_title,
    tv_data,
    ids,
    poster,
    title,
    overview,
    mode,
    plugin,
):
    info_hash = res.get("infoHash")
    debrid_type = res.get("debridType")

    if res.get("isDebridPack"):
        list_item = ListItem(label=f"{format_debrid_type}-CachedPack-{formated_title}")
        add_pack_item(
            list_item, tv_data, ids, info_hash, res["debridType"], mode, plugin
        )
    else:
        cached_title = f"[B][Cached][/B]-{title}"
        list_item = ListItem(label=f"{format_debrid_type}-Cached-{formated_title}")
        set_video_properties(list_item, poster, mode, cached_title, overview, ids)
        list_item.addContextMenuItems(
            [
                (
                    "Browse into",
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
            cached_title,
            debrid_type=debrid_type,
            info_hash=info_hash,
            mode=mode,
            plugin=plugin,
        )


def handle_jackgram_items(
    res, formated_title, tv_data, ids, poster, title, overview, mode, plugin
):
    url = res.get("downloadUrl")
    list_item = ListItem(label=formated_title)
    set_video_properties(list_item, poster, mode, title, overview, ids)
    add_play_item(list_item, ids, tv_data, title, url, mode=mode, plugin=plugin)


def handle_torrent_items(
    res, formated_title, tv_data, ids, poster, title, overview, mode, plugin
):
    guid = res.get("guid")
    magnet = (
        info_hash_to_magnet(guid)
        if res.get("indexer")
        in [
            Indexer.TORRENTIO,
            Indexer.ELHOSTED,
            Indexer.ZILEAN,
        ]
        else (guid if guid and guid.startswith("magnet:?") else "")
    )
    url = res.get("magnetUrl", "") or res.get("downloadUrl", "")
    if not url.startswith("magnet:?"):
        url = ""
    list_item = ListItem(label=formated_title)
    set_video_properties(list_item, poster, mode, title, overview, ids)
    if magnet:
        list_item.addContextMenuItems(
            [
                (
                    "Download to Debrid",
                    action_url_run(
                        name="download_to_debrid",
                        magnet=magnet,
                        debrid_type=res.get("debridType", ""),
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


def get_media_details(tmdb_id, mode):
    if not tmdb_id:
        return "", ""
    if mode == "tv":
        details = tmdb_get("tv_details", tmdb_id)
    elif mode == "movies":
        details = tmdb_get("movie_details", tmdb_id)
    else:
        return "", ""
    poster = TMDB_POSTER_URL + details.poster_path if details.poster_path else ""
    overview = details.overview or ""
    return poster, overview


def truncate(text, length):
    return text[:length] if len(text) > length else text


def format_seeders(seeders):
    return f"{seeders} seeds" if seeders else ""


def extract_publish_date(date):
    if not date:
        return ""
    match = re.search(r"\d{4}-\d{2}-\d{2}", date)
    return match.group() if match else ""
