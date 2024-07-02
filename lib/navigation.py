from functools import wraps
import logging
import os
from threading import Thread
from urllib.parse import quote
import requests

from lib.api.debrid_apis.premiumize_api import Premiumize
from lib.api.debrid_apis.real_debrid_api import RealDebrid
from lib.api.debrid_apis.tor_box_api import Torbox
from lib.api.jacktorr_api import (
    TorrServer,
)
from lib.clients.search import search_client
from lib.debrid import check_debrid_cached, get_debrid_pack_direct_url
from lib.files_history import last_files
from lib.indexer import indexer_show_results
from lib.play import make_listing, play
from lib.player import JacktookPlayer
from lib.plex import plex_login, plex_logout, validate_server
from lib.titles_history import last_titles
from lib.utils.kodi_formats import is_music, is_picture, is_text
from lib.utils.pm_utils import get_pm_pack_info
from lib.utils.rd_utils import get_rd_pack_info, get_rd_info
from lib.utils.torbox_utils import (
    get_torbox_pack_info,
)
from routing import Plugin
from lib.api.tmdbv3api.tmdb import TMDb
from lib.tmdb import (
    TMDB_POSTER_URL,
    tmdb_search,
    tmdb_show_results,
)
from lib.anilist import search_anilist, search_episodes
from lib.db.bookmark_db import bookmark_db
from lib.utils.general_utils import (
    DialogListener,
    Players,
    clear,
    clear_all_cache,
    get_password,
    get_random_color,
    get_service_host,
    get_username,
    is_debrid_activated,
    post_process,
    pre_process,
    get_fanart,
    get_port,
    is_video,
    list_item,
    set_video_info,
    set_video_infotag,
    set_watched_title,
    ssl_enabled,
    tmdb_get,
    check_debrid_enabled,
    Debrids,
)
from lib.utils.kodi_utils import (
    ADDON_PATH,
    EPISODES_TYPE,
    MOVIES_TYPE,
    SHOWS_TYPE,
    JACKTORR_ADDON,
    Keyboard,
    action,
    addon_status,
    buffer_and_play,
    burst_addon_settings,
    close_all_dialog,
    container_update,
    get_kodi_version,
    get_setting,
    notification,
    play_info_hash,
    play_media,
    refresh,
    set_view,
    show_picture,
    translation,
    url_for,
)

from lib.utils.settings import is_auto_play
from lib.utils.settings import addon_settings
from lib.updater import updates_check_addon
from xbmcgui import ListItem, Dialog
from xbmc import getLanguage, ISO_639_1
from xbmcplugin import (
    addDirectoryItem,
    endOfDirectory,
    setResolvedUrl,
    setPluginCategory,
    setContent,
)

plugin = Plugin()

if JACKTORR_ADDON:
    api = TorrServer(
        get_service_host(), get_port(), get_username(), get_password(), ssl_enabled()
    )

tmdb = TMDb()
tmdb.api_key = get_setting("tmdb_apikey", "b70756b7083d9ee60f849d82d94a0d80")

kodi_lang = getLanguage(ISO_639_1)
if kodi_lang:
    tmdb.language = kodi_lang


def query_arg(name, required=True):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if name not in kwargs:
                query_list = plugin.args.get(name)
                if query_list:
                    if name in ["direct", "rescrape", "is_torrent", "is_plex"]:
                        kwargs[name] = eval(query_list[0])
                    else:
                        kwargs[name] = query_list[0]
                elif required:
                    raise AttributeError(
                        "Missing {} required query argument".format(name)
                    )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def check_directory(func):
    def wrapper(*args, **kwargs):
        succeeded = False
        try:
            ret = func(*args, **kwargs)
            succeeded = True
            return ret
        finally:
            endOfDirectory(plugin.handle, succeeded=succeeded)

    return wrapper


@plugin.route("/")
@check_directory
def main_menu():
    setPluginCategory(plugin.handle, "Main Menu")
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(search_tmdb, mode="multi", genre_id=-1, page=1),
        list_item("Search", "search.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(search_tmdb, mode="tv", genre_id=-1, page=1),
        list_item("TV Shows", "tv.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(search_tmdb, mode="movie", genre_id=-1, page=1),
        list_item("Movies", "movies.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(anime_menu),
        list_item("Anime", "anime.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(genre_menu),
        list_item("By Genre", "movies.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(direct_menu),
        list_item("Direct Search", "search.png"),
        isFolder=True,
    )

    addDirectoryItem(
        plugin.handle,
        plugin.url_for(torrents),
        list_item("Torrents", "magnet2.png"),
        isFolder=True,
    )

    addDirectoryItem(
        plugin.handle,
        plugin.url_for(cloud),
        list_item("Cloud", "cloud.png"),
        isFolder=True,
    )

    addDirectoryItem(
        plugin.handle,
        plugin.url_for(settings),
        list_item("Settings", "settings.png"),
        isFolder=True,
    )

    addDirectoryItem(
        plugin.handle,
        plugin.url_for(status),
        list_item("Status", "status.png"),
        isFolder=True,
    )

    addDirectoryItem(
        plugin.handle,
        plugin.url_for(history),
        list_item("History", "history.png"),
        isFolder=True,
    )


@plugin.route("/direct")
@check_directory
def direct_menu():
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(search_direct, mode="multi"),
        list_item("Search", "search.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(search_direct, mode="tv"),
        list_item("TV Search", "tv.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(search_direct, mode="movie"),
        list_item("Movie Search", "movies.png"),
        isFolder=True,
    )


@plugin.route("/anime")
@check_directory
def anime_menu():
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(anilist, category="search"),
        list_item("Search", "search.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(
            anilist,
            category="Popular",
        ),
        list_item("Popular", "tv.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(anilist, category="Trending"),
        list_item("Trending", "movies.png"),
        isFolder=True,
    )


@plugin.route("/genre")
@check_directory
def genre_menu():
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(search_tmdb, mode="tv_genres", genre_id=-1, page=1),
        list_item("TV Shows", "tv.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(search_tmdb, mode="movie_genres", genre_id=-1, page=1),
        list_item("Movies", "movies.png"),
        isFolder=True,
    )


@plugin.route("/search_tmdb/<mode>/<genre_id>/<page>")
def search_tmdb(mode, genre_id, page):
    if mode in ["movie", "movie_genres"]:
        setContent(plugin.handle, MOVIES_TYPE)
    elif mode in ["tv", "tv_genres"]:
        setContent(plugin.handle, SHOWS_TYPE)

    page = int(page)
    data = tmdb_search(mode, genre_id, page, search_tmdb, plugin)
    if data:
        if data.total_results == 0:
            notification("No results found")
            return
        tmdb_show_results(
            data.results,
            next_func=next_page,
            page=page,
            plugin=plugin,
            genre_id=genre_id,
            mode=mode,
        )


@plugin.route("/search_direct/<mode>")
def search_direct(mode):
    text = Keyboard(id=30243)
    if text:
        text = quote(text)
        list_item = ListItem(label=f"Search [I]{text}[/I]")
        list_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "search.png")}
        )
        addDirectoryItem(
            plugin.handle,
            plugin.url_for(
                search,
                mode=mode,
                query=text,
                direct=True
            ),
            list_item,
            isFolder=True,
        )
        endOfDirectory(plugin.handle)


@plugin.route("/search")
@query_arg("query", required=False)
@query_arg("mode", required=True)
@query_arg("media_type", required=False)
@query_arg("ids", required=False)
@query_arg("tv_data", required=False)
@query_arg("direct", required=False)
@query_arg("rescrape", required=False)
def search(
    query="", mode="", media_type="", ids="", tv_data="", direct=False, rescrape=False
):
    if mode == "movie" or media_type == "movie":
        setContent(plugin.handle, MOVIES_TYPE)
    elif mode == "tv" or media_type == "tv" or mode == "anime":
        setContent(plugin.handle, SHOWS_TYPE)

    set_watched_title(query, ids, mode)
    if tv_data:
        ep_name, episode, season = tv_data.split("(^)")
    else:
        episode = season = 0
        ep_name = ""

    client = get_setting("client_player")

    with DialogListener() as listener:
        p_dialog = listener.dialog
        results = search_client(
            query, ids, mode, media_type, p_dialog, rescrape, season, episode
        )
        if results:
            proc_results = pre_process(
                results,
                mode,
                ep_name,
                episode,
                season,
            )
            if proc_results:
                if client == Players.DEBRID:
                    if is_debrid_activated():
                        debrid_cached = check_debrid_cached(
                            query,
                            proc_results,
                            mode,
                            media_type,
                            p_dialog,
                            rescrape,
                            episode,
                        )
                        if debrid_cached:
                            final_results = post_process(debrid_cached, season)
                            if is_auto_play():
                                auto_play(final_results, ids, tv_data, mode, p_dialog)
                                return
                        else:
                            notification("No cached results")
                            return
                    else:
                        notification("No debrid client enabled")
                        return
                else:
                    final_results = post_process(proc_results)

                if final_results:
                    indexer_show_results(
                        final_results,
                        mode,
                        ids,
                        tv_data,
                        direct,
                        plugin,
                    )
                    set_view("widelist")
                    endOfDirectory(plugin.handle)
            else:
                notification("No results found for episode")
        else:
            notification("No results found")


def auto_play(results, ids, tv_data, mode, p_dialog):
    close_all_dialog()
    p_dialog.close()
    play_first_result(results, ids, tv_data, mode)


def play_first_result(results, ids, tv_data, mode):
    for res in results:
        if res["isDebridPack"]:
            continue
        play_media(
            plugin,
            play_torrent,
            title=results[0]["title"],
            ids=ids,
            tv_data=tv_data,
            info_hash=results[0]["infoHash"],
            torrent_id=results[0]["torrentId"],
            debrid_type=results[0]["debridType"],
            is_torrent=False,
            mode=mode,
        )
        break


@plugin.route("/play_torrent")
@query_arg("title", required=True)
@query_arg("url", required=False)
@query_arg("magnet", required=False)
@query_arg("info_hash", required=False)
@query_arg("ids", required=False)
@query_arg("tv_data", required=False)
@query_arg("is_torrent", required=False)
@query_arg("is_plex", required=False)
@query_arg("debrid_type", required=False)
@query_arg("is_debrid_pack", required=False)
@query_arg("mode", required=False)
def play_torrent(
    title,
    url="",
    magnet="",
    info_hash="",
    ids="",
    tv_data="",
    mode="",
    debrid_type="",
    is_debrid_pack=False,
    is_torrent=False,
    is_plex=False,
):
    play(
        url,
        ids,
        tv_data,
        title,
        plugin,
        magnet=magnet,
        info_hash=info_hash,
        debrid_type=debrid_type,
        mode=mode,
        is_torrent=is_torrent,
        is_plex=is_plex,
        is_debrid_pack=is_debrid_pack,
    )


@plugin.route("/cloud/details")
@check_directory
@query_arg("debrid_type", required=False)
def cloud_details(debrid_type=""):
    if debrid_type == Debrids.TB:
        notification("Not yet implemented")
        return

    if debrid_type == Debrids.RD:
        downloads_method = get_rd_downloads
        info_method = rd_info
    elif debrid_type == Debrids.PM:
        downloads_method = None
        info_method = None

    addDirectoryItem(
        plugin.handle,
        plugin.url_for(downloads_method),
        list_item("Downloads", "download.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(info_method),
        list_item("Account Info", "download.png"),
        isFolder=True,
    )


@plugin.route("/cloud")
@check_directory
def cloud():
    activated_debrids = [
        debrid for debrid in Debrids.values() if check_debrid_enabled(debrid)
    ]
    if activated_debrids:
        for debrid_name in activated_debrids:
            torrent_li = list_item(debrid_name, "download.png")
            addDirectoryItem(
                plugin.handle,
                plugin.url_for(
                    cloud_details,
                    debrid_type=debrid_name,
                ),
                torrent_li,
                isFolder=True,
            )
    else:
        notification("No debrid services activated")


@plugin.route("/rd_info")
def rd_info():
    get_rd_info()


@plugin.route("/rd_downloads")
@query_arg("page", required=False)
@check_directory
def get_rd_downloads(page=1):
    debrid_type = "RD"
    debrid_color = get_random_color(debrid_type)
    format_debrid_type = f"[B][COLOR {debrid_color}][{debrid_type}][/COLOR][/B]"

    rd_client = RealDebrid(encoded_token=get_setting("real_debrid_token"))
    downloads = rd_client.get_user_downloads_list(page=page)
    for d in downloads:
        torrent_li = list_item(f"{format_debrid_type}-{d['filename']}", "download.png")
        torrent_li.setArt(
            {
                "icon": d["host_icon"],
            }
        )
        addDirectoryItem(
            plugin.handle,
            plugin.url_for(play_url, url=d.get("download"), name=d["filename"]),
            torrent_li,
            isFolder=False,
        )

    next_page = int(page) + 1
    next_item = list_item("Next", icon="nextpage.png")
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(get_rd_downloads, page=next_page),
        next_item,
        isFolder=True,
    )


@plugin.route("/torrents")
@check_directory
def torrents():
    if JACKTORR_ADDON:
        for torrent in api.torrents():
            info_hash = torrent.get("hash")

            context_menu_items = [(translation(30700), play_info_hash(info_hash))]

            if torrent.get("stat") in [2, 3]:
                context_menu_items.append(
                    (
                        translation(30709),
                        action(plugin, torrent_action, info_hash, "drop"),
                    )
                )

            context_menu_items.extend(
                [
                    (
                        translation(30705),
                        action(plugin, torrent_action, info_hash, "remove_torrent"),
                    ),
                    (
                        translation(30707),
                        action(plugin, torrent_action, info_hash, "torrent_status"),
                    ),
                ]
            )

            torrent_li = list_item(torrent.get("title", ""), "download.png")
            torrent_li.addContextMenuItems(context_menu_items)
            addDirectoryItem(
                plugin.handle,
                plugin.url_for(torrent_files, info_hash),
                torrent_li,
                isFolder=True,
            )
    else:
        notification(translation(30253))


@plugin.route("/torrents/<info_hash>/<action_str>")
def torrent_action(info_hash, action_str):
    needs_refresh = True

    if action_str == "drop":
        api.drop_torrent(info_hash)
    elif action_str == "remove_torrent":
        api.remove_torrent(info_hash)
    elif action_str == "torrent_status":
        torrent_status(info_hash)
        needs_refresh = False
    else:
        logging.error("Unknown action '%s'", action_str)
        needs_refresh = False

    if needs_refresh:
        refresh()


@plugin.route("/torrents/<info_hash>")
@check_directory
def torrent_files(info_hash):
    info = api.get_torrent_info(link=info_hash)
    file_stats = info.get("file_stats")

    for f in file_stats:
        name = f.get("path")
        id = f.get("id")
        serve_url = api.get_stream_url(link=info_hash, path=f.get("path"), file_id=id)
        file_li = list_item(name, "download.png")
        file_li.setPath(serve_url)

        context_menu_items = []
        info_type = None
        info_labels = {"title": info.get("title")}
        kwargs = dict(info_hash=info_hash, file_id=id, path=name)

        if is_picture(name):
            url = plugin.url_for(display_picture, **kwargs)
            file_li.setInfo("pictures", info_labels)
        elif is_text(name):
            url = plugin.url_for(display_text, **kwargs)
        else:
            url = serve_url
            if is_video(name):
                info_type = "video"
            elif is_music(name):
                info_type = "music"

            if info_type is not None:
                file_li.setInfo(info_type, info_labels)
                file_li.setProperty("IsPlayable", "true")

                context_menu_items.append(
                    (
                        translation(30700),
                        buffer_and_play(**kwargs),
                    )
                )

                file_li.addContextMenuItems(context_menu_items)

        if info_type is not None:
            addDirectoryItem(
                plugin.handle,
                plugin.url_for(play_url, url=serve_url, name=name),
                file_li,
            )
        else:
            addDirectoryItem(plugin.handle, url, file_li)


@plugin.route("/play_url")
@query_arg("url")
@query_arg("name")
def play_url(url, name):
    list_item = ListItem(name, path=url)
    make_listing(list_item, mode="multi", title=name)

    setResolvedUrl(plugin.handle, True, list_item)
    player = JacktookPlayer(bookmark_db)
    player.set_constants(url)
    player.run(list_item)


@plugin.route("/display_picture/<info_hash>/<file_id>")
@query_arg("path")
def display_picture(info_hash, file_id, path):
    show_picture(api.get_stream_url(link=info_hash, path=path, file_id=file_id))


@plugin.route("/display_text/<info_hash>/<file_id>")
@query_arg("path")
def display_text(info_hash, file_id, path):
    r = requests.get(api.get_stream_url(link=info_hash, path=path, file_id=file_id))
    Dialog().textviewer(path, r.text)


@plugin.route("/tv/details")
@query_arg("ids", required=False)
@query_arg("mode", required=False)
@query_arg("media_type", required=False)
@check_directory
def tv_seasons_details(ids, mode, media_type=None):
    setContent(plugin.handle, SHOWS_TYPE)
    tmdb_id, tvdb_id, _ = ids.split(", ")

    details = tmdb_get("tv_details", tmdb_id)
    name = details.name
    seasons = details.seasons
    overview = details.overview

    set_watched_title(name, ids, mode=mode, media_type=media_type)

    show_poster = TMDB_POSTER_URL + details.get("poster_path", "")
    fanart_data = get_fanart(tvdb_id)
    fanart = fanart_data["fanart"] if fanart_data else ""

    for s in seasons:
        season_name = s.name
        if "Specials" in season_name:
            continue
        season_number = s.season_number
        if season_number == 0:
            continue
        if s.poster_path:
            poster = TMDB_POSTER_URL + s.poster_path
        else:
            poster = show_poster

        list_item = ListItem(label=season_name)

        if get_kodi_version() >= 20:
            set_video_infotag(
                list_item, mode, name, overview, season_number=season_number, ids=ids
            )
        else:
            set_video_info(
                list_item, mode, name, overview, season_number=season_number, ids=ids
            )

        list_item.setArt(
            {
                "poster": poster,
                "tvshow.poster": poster,
                "fanart": fanart,
                "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
            }
        )
        list_item.setProperty("IsPlayable", "false")

        addDirectoryItem(
            plugin.handle,
            plugin.url_for(
                tv_episodes_details,
                tv_name=name,
                ids=ids,
                mode=mode,
                media_type=media_type,
                season=season_number,
            ),
            list_item,
            isFolder=True,
        )

    set_view("widelist")


@plugin.route("/tv/details/season/<tv_name>/<season>")
@query_arg("ids", required=False)
@query_arg("mode", required=False)
@query_arg("media_type", required=False)
@check_directory
def tv_episodes_details(tv_name, season, ids, mode, media_type):
    setContent(plugin.handle, EPISODES_TYPE)
    tmdb_id, tvdb_id, _ = ids.split(", ")
    season_details = tmdb_get("season_details", {"id": tmdb_id, "season": season})
    fanart_data = get_fanart(tvdb_id)

    for ep in season_details.episodes:
        ep_name = ep.name
        episode = ep.episode_number
        label = f"{season}x{episode}. {ep_name}"
        air_date = ep.air_date
        duration = ep.runtime
        tv_data = f"{ep_name}(^){episode}(^){season}"

        still_path = ep.get("still_path", "")
        if still_path:
            poster = TMDB_POSTER_URL + still_path
        else:
            poster = fanart_data.get("fanart", "") if fanart_data else ""

        list_item = ListItem(label=label)

        if get_kodi_version() >= 20:
            set_video_infotag(
                list_item,
                mode,
                tv_name,
                ep.overview,
                episode=episode,
                duration=duration,
                air_date=air_date,
                ids=ids,
            )
        else:
            set_video_info(
                list_item,
                mode,
                tv_name,
                ep.overview,
                episode=episode,
                duration=duration,
                air_date=air_date,
                ids=ids,
            )

        list_item.setArt(
            {
                "poster": poster,
                "tvshow.poster": poster,
                "fanart": poster,
                "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
            }
        )
        list_item.setProperty("IsPlayable", "false")
        list_item.addContextMenuItems(
            [
                (
                    "Rescrape item",
                    container_update(
                        name="search",
                        mode=mode,
                        query=tv_name,
                        ids=ids,
                        tv_data=tv_data,
                        rescrape=True,
                    ),
                )
            ]
        )

        addDirectoryItem(
            plugin.handle,
            plugin.url_for(
                search,
                mode=mode,
                media_type=media_type,
                query=tv_name,
                ids=ids,
                tv_data=tv_data,
            ),
            list_item,
            isFolder=True,
        )

    set_view("widelist")


@plugin.route("/play_file_from_pack")
@query_arg("title", required=False)
@query_arg("ids", required=False)
@query_arg("tv_data", required=False)
@query_arg("mode", required=False)
@query_arg("debrid_type", required=False)
@query_arg("mode", required=False)
@query_arg("file_id", required=False)
@query_arg("torrent_id", required=False)
def play_file_from_pack(ids, mode, debrid_type, title, tv_data, file_id, torrent_id):
    url = get_debrid_pack_direct_url(file_id, torrent_id, debrid_type)
    play(
        url,
        ids,
        tv_data,
        title,
        plugin,
        mode=mode,
        debrid_type=debrid_type,
        is_debrid_pack=True
    )


@plugin.route("/show_pack_info")
@query_arg("ids", required=False)
@query_arg("info_hash", required=False)
@query_arg("debrid_type", required=False)
@query_arg("mode", required=False)
@query_arg("tv_data", required=False)
@check_directory
def show_pack_info(ids, info_hash, debrid_type, mode, tv_data):
    if mode == "movie":
        setContent(plugin.handle, MOVIES_TYPE)
    elif mode == "tv" or mode == "anime":
        setContent(plugin.handle, SHOWS_TYPE)

    if debrid_type == "PM":
        info = get_pm_pack_info(info_hash)
        if info:
            for url, title in info["files"]:
                list_item = ListItem(label=f"{title}")
                list_item.setArt(
                    {
                        "icon": os.path.join(
                            ADDON_PATH, "resources", "img", "trending.png"
                        )
                    }
                )
                addDirectoryItem(
                    plugin.handle,
                    url_for(
                        name="play_torrent",
                        title=title,
                        url=url,
                        ids=ids,
                        tv_data=tv_data,
                        mode=mode,
                        is_torrent=False,
                        debrid_type=debrid_type,
                    ),
                    list_item,
                    isFolder=False,
                )
        return 
    elif debrid_type == "RD":
        info = get_rd_pack_info(info_hash)
    elif debrid_type == "TB":
        info = get_torbox_pack_info(info_hash)

    if info:
        for file_id, title in info["files"]:
            list_item = ListItem(label=title)
            list_item.setArt(
                {"icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png")}
            )
            addDirectoryItem(
                plugin.handle,
                url_for(
                    name="play_file_from_pack",
                    file_id=file_id,
                    torrent_id=info["id"],
                    debrid_type=debrid_type,
                    title=title,
                    mode=mode,
                    ids=ids,
                    tv_data=tv_data,
                ),
                list_item,
                isFolder=False,
            )

@plugin.route("/anilist/<category>")
def anilist(category, page=1):
    setContent(plugin.handle, MOVIES_TYPE)
    search_anilist(category, page, plugin)


@plugin.route("/anilist/next_page/<category>/<page>")
def next_page_anilist(category, page):
    setContent(plugin.handle, MOVIES_TYPE)
    page = int(page) + 1
    search_anilist(category, page, plugin)


@plugin.route("/anilist/episodes/<query>/<anilist_id>/<mal_id>")
def search_anime_episodes(query, anilist_id, mal_id):
    search_episodes(query, anilist_id, mal_id, plugin)


@plugin.route("/next_page/<mode>/<page>/<genre_id>")
def next_page(mode, page, genre_id):
    search_tmdb(mode=mode, genre_id=int(genre_id), page=int(page))


@plugin.route("/download_to_debrid")
@query_arg("magnet", required=True)
@query_arg("debrid_type", required=True)
def download(magnet, debrid_type):
    if debrid_type == "RD":
        rd_client = RealDebrid(encoded_token=get_setting("real_debrid_token"))
        thread = Thread(
            target=rd_client.download, args=(magnet,), kwargs={"pack": False}
        )
    elif debrid_type == "TB":
        tb_client = Torbox(token=get_setting("torbox_token"))
        thread = Thread(target=tb_client.download, args=(magnet,))
    elif debrid_type == "PM":
        pm_client = Premiumize(token=get_setting("premiumize_token"))
        thread = Thread(
            target=pm_client.download, args=(magnet,), kwargs={"pack": False}
        )
    thread.start()


@plugin.route("/addon_update")
def addon_update():
    updates_check_addon()


@plugin.route("/status")
def status():
    addon_status()


@plugin.route("/settings")
def settings():
    addon_settings()


@plugin.route("/history/clear/<type>")
def clear_history(type):
    clear(type=type)


@plugin.route("/history")
def history():
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(files),
        list_item("Files History", "history.png"),
        isFolder=True,
    )

    addDirectoryItem(
        plugin.handle,
        plugin.url_for(titles),
        list_item("Titles History", "history.png"),
        isFolder=True,
    )
    endOfDirectory(plugin.handle)


@plugin.route("/history/titles")
def titles():
    last_titles(plugin)


@plugin.route("/history/files")
def files():
    last_files(plugin)


@plugin.route("/clear_cached_all")
def clear_cached_all():
    clear_all_cache()
    notification(translation(30244))


@plugin.route("/rd_auth")
def rd_auth():
    rd_client = RealDebrid(encoded_token=get_setting("real_debrid_token"))
    rd_client.auth()


@plugin.route("/pm_auth")
def pm_auth():
    pm_client = Premiumize(token=get_setting("premiumize_token"))
    pm_client.auth()


@plugin.route("/plex_auth")
def plex_auth():
    plex_login()


@plugin.route("/plex_logout")
def logout():
    plex_logout()


@plugin.route("/plex_validate")
def plex_validate():
    validate_server()


@plugin.route("/open_burst_config")
def open_burst_config():
    burst_addon_settings()


def torrent_status(info_hash):
    status = api.get_torrent_info(link=info_hash)
    notification(
        "{}".format(status.get("stat_string")),
        status.get("name"),
        sound=False,
    )


def run():
    try:
        plugin.run()
    except Exception as e:
        logging.error("Caught exception:", exc_info=True)
        notification(str(e))
