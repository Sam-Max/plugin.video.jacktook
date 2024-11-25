from functools import wraps
import logging
import os
from threading import Thread
from urllib.parse import quote
import requests

from lib.api.debrid.premiumize_api import Premiumize
from lib.api.debrid.real_debrid_api import RealDebrid
from lib.api.debrid.tor_box_api import Torbox
from lib.api.jacktook.kodi import kodilog
from lib.api.jacktorr_api import TorrServer
from lib.api.tmdbv3api.tmdb import TMDb

from lib.utils.seasons import show_episode_info, show_season_info
from lib.utils.torrentio_utils import open_providers_selection
from lib.api.trakt.trakt_api import (
    trakt_authenticate,
    trakt_revoke_authentication,
)
from lib.clients.search import search_client
from lib.debrid import check_debrid_cached
from lib.files_history import last_files
from lib.indexer import show_indexers_results
from lib.play import make_listing, play
from lib.player import JacktookPlayer
from lib.titles_history import last_titles

from lib.trakt import (
    handle_trakt_query,
    process_trakt_result,
    show_trakt_list_content,
    show_trakt_list_page,
)
from lib.utils.kodi_formats import is_music, is_picture, is_text

from lib.utils.pm_utils import get_pm_pack_info, show_pm_pack_info
from lib.utils.rd_utils import get_rd_info, get_rd_pack_info, show_rd_pack_info
from lib.utils.items_menus import tv_items, movie_items, anime_items
from lib.utils.torbox_utils import get_torbox_pack_info, show_tb_pack_info

from lib.tmdb import (
    handle_tmdb_anime_query,
    handle_tmdb_query,
    search as tmdb_search,
    show_results,
)
from lib.db.bookmark_db import bookmark_db

from lib.utils.utils import (
    DialogListener,
    Players,
    clear,
    clear_all_cache,
    execute_thread_pool,
    get_password,
    get_random_color,
    get_service_host,
    get_username,
    is_debrid_activated,
    post_process,
    pre_process,
    get_port,
    is_video,
    list_item,
    set_content_type,
    set_watched_title,
    ssl_enabled,
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
    donate_message,
    get_setting,
    notification,
    play_info_hash,
    play_media,
    refresh,
    set_view,
    show_picture,
    translation,
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
from routing import Plugin

plugin = Plugin()

paginator = None

if JACKTORR_ADDON:
    api = TorrServer(
        get_service_host(), get_port(), get_username(), get_password(), ssl_enabled()
    )

tmdb = TMDb()
tmdb.api_key = get_setting("tmdb_apikey", "b70756b7083d9ee60f849d82d94a0d80")

if get_setting("kodi_language"):     
    kodi_lang = getLanguage(ISO_639_1)
else:
    kodi_lang = "en"
tmdb.language = kodi_lang


def query_arg(name, required=True):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if name not in kwargs:
                query_list = plugin.args.get(name)
                if query_list:
                    if name in ["direct", "rescrape", "is_torrent", "data"]:
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
def root_menu():
    setPluginCategory(plugin.handle, "Main Menu")
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(search_tmdb, mode="multi", genre_id=-1, page=1),
        list_item("Search", "search.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(tv_shows_items),
        list_item("TV Shows", "tv.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(movies_items),
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

    addDirectoryItem(
        plugin.handle,
        plugin.url_for(donate),
        list_item("Donate", "donate.png"),
        isFolder=True,
    )


@plugin.route("/search_tmdb")
@query_arg("mode", required=True)
@query_arg("genre_id", required=True)
@query_arg("page", required=True)
def search_tmdb(mode, genre_id, page):
    if mode in ["movies", "movie_genres"]:
        setContent(plugin.handle, MOVIES_TYPE)
    elif mode in ["tv", "tv_genres"]:
        setContent(plugin.handle, SHOWS_TYPE)
    data = tmdb_search(mode, genre_id, int(page))
    if data:
        if data.total_results == 0:
            notification("No results found")
            return
        show_results(
            data.results,
            page=int(page),
            plugin=plugin,
            genre_id=genre_id,
            mode=mode,
        )


@plugin.route("/tv_items")
@check_directory
def tv_shows_items():
    for item in tv_items:
        addDirectoryItem(
            plugin.handle,
            plugin.url_for(
                search_item, mode=item["mode"], query=item["query"], api=item["api"]
            ),
            list_item(item["name"], item["icon"]),
            isFolder=True,
        )


@plugin.route("/movies_items")
@check_directory
def movies_items():
    for item in movie_items:
        addDirectoryItem(
            plugin.handle,
            plugin.url_for(
                search_item, mode=item["mode"], query=item["query"], api=item["api"]
            ),
            list_item(item["name"], item["icon"]),
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
        plugin.url_for(search_direct, mode="movies"),
        list_item("Movie Search", "movies.png"),
        isFolder=True,
    )


@plugin.route("/anime")
@check_directory
def anime_menu():
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(anime_item, mode="tv"),
        list_item("Tv Shows", "tv.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(anime_item, mode="movies"),
        list_item("Movies", "movies.png"),
        isFolder=True,
    )


@plugin.route("/anime/<mode>")
@check_directory
def anime_item(mode):
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(anime_search, mode=mode, category="Anime_Search"),
        list_item("Search", "search.png"),
        isFolder=True,
    )

    if mode == "tv":
        for item in anime_items:
            addDirectoryItem(
                plugin.handle,
                plugin.url_for(
                    search_item,
                    category=item["category"],
                    mode=item["mode"],
                    submode=mode,
                    api=item["api"],
                ),
                list_item(item["name"], item["icon"]),
                isFolder=True,
            )
    if mode == "movies":
        for item in anime_items:
            if item["api"] == "tmdb":
                addDirectoryItem(
                    plugin.handle,
                    plugin.url_for(
                        search_item,
                        category=item["category"],
                        mode=item["mode"],
                        submode=mode,
                        api=item["api"],
                    ),
                    list_item(item["name"], item["icon"]),
                    isFolder=True,
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
            plugin.url_for(search, mode=mode, query=text, direct=True),
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
    set_content_type(mode, media_type, plugin)
    set_watched_title(query, ids, mode, media_type)

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
                    execute_thread_pool(
                        final_results,
                        show_indexers_results,
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
        if res.get("isPack"):
            continue

        play_media(
            plugin,
            play_torrent,
            title=res.get("title", ""),
            mode=mode,
            data={
                "ids": ids,
                "info_hash": res.get("infoHash", ""),
                "tv_data": tv_data,
                "debrid_info": {
                    "debrid_type": res.get("debridType", ""),
                },
            },
        )
        break


@plugin.route("/play_torrent")
@query_arg("title", required=True)
@query_arg("mode", required=False)
@query_arg("is_torrent", required=False)
@query_arg("data", required=False)
def play_torrent(
    title="",
    mode="",
    is_torrent=False,
    data="",
):
    kodilog("navigation::play_torrent")
    play(
        title,
        mode,
        is_torrent=is_torrent,
        plugin=plugin,
        extra_data=data,
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

    page = int(page) + 1
    next_li = list_item("Next", icon="nextpage.png")
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(get_rd_downloads, page=page),
        next_li,
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
    show_season_info(ids, mode, media_type, plugin)
    set_view("widelist")


@plugin.route("/tv/details/season")
@query_arg("ids", required=False)
@query_arg("mode", required=False)
@query_arg("media_type", required=False)
@query_arg("tv_name", required=False)
@query_arg("season", required=False)
@check_directory
def tv_episodes_details(tv_name, season, ids, mode, media_type):
    setContent(plugin.handle, EPISODES_TYPE)
    show_episode_info(tv_name, season, ids, mode, media_type, plugin)
    set_view("widelist")


@plugin.route("/play_from_pack")
@query_arg("title", required=False)
@query_arg("mode", required=False)
@query_arg("data", required=False)
def play_from_pack(title, mode, data):
    play(title, mode, plugin=plugin, extra_data=data)


@plugin.route("/show_pack_info")
@query_arg("ids", required=False)
@query_arg("info_hash", required=False)
@query_arg("debrid_type", required=False)
@query_arg("mode", required=False)
@query_arg("tv_data", required=False)
@check_directory
def show_pack_info(ids, info_hash, debrid_type, mode, tv_data):
    if mode == "movies":
        setContent(plugin.handle, MOVIES_TYPE)
    elif mode == "tv":
        setContent(plugin.handle, SHOWS_TYPE)

    if debrid_type == "PM":
        if info := get_pm_pack_info(info_hash):
            show_pm_pack_info(info, ids, debrid_type, tv_data, mode, plugin)
    elif debrid_type == "TB":
        if info := get_torbox_pack_info(info_hash):
            show_tb_pack_info(info, ids, debrid_type, tv_data, mode, plugin)
    elif debrid_type == "RD":
        if info := get_rd_pack_info(info_hash):
            show_rd_pack_info(info, ids, debrid_type, tv_data, mode, plugin)


@plugin.route("/search_item")
@query_arg("query", required=False)
@query_arg("category", required=False)
@query_arg("mode", required=True)
@query_arg("submode", required=False)
@query_arg("api", required=True)
@query_arg("page", required=False)
def search_item(query="", category="", api="", mode="", submode=None, page=1):
    set_content_type(mode, plugin=plugin)
    if api == "trakt":
        result = handle_trakt_query(query, category, mode, page)
        if result:
            process_trakt_result(
                result, query, category, mode, submode, api, page, plugin
            )
    elif api == "tmdb":
        handle_tmdb_query(query, category, mode, submode, page, plugin)


@plugin.route("/trakt/list/content")
@query_arg("list_type", required=False)
@query_arg("mode", required=False)
@query_arg("user", required=False)
@query_arg("slug", required=False)
@query_arg("with_auth", required=False)
def trakt_list_content(list_type, mode, user, slug, with_auth="", page=1):
    set_content_type(mode, plugin=plugin)
    show_trakt_list_content(list_type, mode, user, slug, with_auth, page, plugin)


@plugin.route("/trakt/paginator")
@query_arg("page", required=False)
@query_arg("mode", required=False)
def trakt_list_page(mode, page=""):
    set_content_type(mode, plugin=plugin)
    show_trakt_list_page(int(page), mode, plugin)


@plugin.route("/anime/search/<mode>/<category>")
def anime_search(mode, category, page=1):
    handle_tmdb_anime_query(category, mode, page, plugin=plugin)


@plugin.route("/anime_next_page")
@query_arg("mode", required=True)
@query_arg("category", required=True)
@query_arg("page", required=True)
def anime_next_page(mode="", category="", page=""):
    handle_tmdb_anime_query(category, mode, page=int(page) + 1, plugin=plugin)


@plugin.route("/next_page_tmdb")
@query_arg("mode", required=True)
@query_arg("page", required=True)
@query_arg("genre_id", required=True)
def next_page_tmdb(mode, page, genre_id):
    search_tmdb(mode=mode, genre_id=int(genre_id), page=int(page))


@plugin.route("/next_page_trakt")
@query_arg("query", required=False)
@query_arg("category", required=False)
@query_arg("mode", required=True)
@query_arg("submode", required=True)
@query_arg("api", required=True)
@query_arg("page", required=True)
def next_page_trakt(query="", category="", mode="", submode="", api="", page=1):
    search_item(
        query=query,
        category=category,
        mode=mode,
        submode=submode,
        api=api,
        page=int(page),
    )


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


@plugin.route("/donate")
def donate():
    donate_message()


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


@plugin.route("/trakt_auth")
def trakt_auth():
    trakt_authenticate()


@plugin.route("/trakt_logout")
def trakt_auth():
    trakt_revoke_authentication()


@plugin.route("/open_burst_config")
def open_burst_config():
    burst_addon_settings()


@plugin.route("/open_torr_providers_select")
def open_torrentio_provider_selection():
    open_providers_selection()


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
