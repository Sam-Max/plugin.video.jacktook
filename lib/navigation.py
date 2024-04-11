from functools import wraps
import logging
import os
from threading import Thread
import requests

from lib.api.premiumize_api import Premiumize
from lib.api.real_debrid_api import RealDebrid
from lib.api.jacktorr_api import (
    TorrServer,
)
from lib.clients.search import search_client
from lib.debrid import check_debrid_cached
from lib.files_history import last_files
from lib.indexer import indexer_show_results
from lib.play import make_listing, play
from lib.player import JacktookPlayer
from lib.simkl import search_simkl_episodes
from lib.titles_history import last_titles
from lib.utils.kodi_formats import is_music, is_picture, is_text
from lib.utils.pm_utils import get_pm_link, get_pm_pack
from lib.utils.rd_utils import get_rd_link, get_rd_pack, get_rd_pack_link
from routing import Plugin

from lib.api.tmdbv3api.tmdb import TMDb
from lib.tmdb import (
    TMDB_POSTER_URL,
    tmdb_search,
    tmdb_show_results,
)
from lib.anilist import search_anilist
from lib.utils.utils import (
    DialogListener,
    clear,
    clear_all_cache,
    clear_tmdb_cache,
    get_password,
    get_service_host,
    get_username,
    post_process,
    pre_process,
    search_fanart_tv,
    get_port,
    is_video,
    list_item,
    set_pack_art,
    set_pack_item_pm,
    set_pack_item_rd,
    set_video_info,
    set_video_infotag,
    set_watched_title,
    ssl_enabled,
    tmdb_get,
)
from lib.utils.kodi import (
    ADDON_PATH,
    EPISODES_TYPE,
    MOVIES_TYPE,
    SHOWS_TYPE,
    JACKTORR_ADDON,
    action,
    addon_settings,
    addon_status,
    auto_play,
    buffer_and_play,
    burst_addon_settings,
    close_all_dialog,
    container_update,
    dialogyesno,
    get_kodi_version,
    get_setting,
    log,
    notify,
    play_info_hash,
    play_media,
    refresh,
    set_view,
    show_picture,
    translation,
)
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
                    if name in ["rescrape", "is_torrent", "is_debrid"]:
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
        list_item("Torrents", "settings.png"),
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
        plugin.url_for(search, mode="multi"),
        list_item("Search", "search.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(search, mode="tv"),
        list_item("TV Search", "tv.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(search, mode="movie"),
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
            notify("No results found")
            return
        tmdb_show_results(
            data.results,
            next_func=next_page,
            page=page,
            plugin=plugin,
            genre_id=genre_id,
            mode=mode,
        )


@plugin.route("/search")
@query_arg("mode", required=True)
@query_arg("media_type", required=False)
@query_arg("query", required=False)
@query_arg("ids", required=False)
@query_arg("tv_data", required=False)
@query_arg("rescrape", required=False)
def search(mode="", media_type="", query="", ids="", tv_data="", rescrape=False):
    if mode == "movie" or media_type == "movie":
        setContent(plugin.handle, MOVIES_TYPE)
    elif mode == "tv" or media_type == "tv":
        setContent(plugin.handle, SHOWS_TYPE)

    set_watched_title(query, ids, mode)
    if tv_data:
        ep_name, episode, season = tv_data.split("(^)")
    else:
        episode = season = 0
        ep_name = ""
    
    torr_client = get_setting("torrent_client")

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
                if torr_client == "Debrid" or torr_client == "All":
                    deb_cached_results = check_debrid_cached(
                        query,
                        proc_results,
                        mode,
                        media_type,
                        p_dialog,
                        rescrape,
                        episode,
                    )
                    if deb_cached_results:
                        final_results = post_process(deb_cached_results)
                        if auto_play():
                            close_all_dialog()
                            p_dialog.close()
                            play_first_result(deb_cached_results, ids, tv_data, mode)
                            return
                    else:
                        notify("No debrid results")
                        return
                elif torr_client in ["Torrest", "Elementum", "Jacktorr"]:
                    final_results = post_process(proc_results)
                indexer_show_results(
                    final_results,
                    mode,
                    query,
                    ids,
                    tv_data,
                    plugin,
                )
            else:
                notify("No results")
        else:
            notify("No results")

def play_first_result(results, ids, tv_data, mode):
    for res in results:
        if res["debridPack"]:
            continue
        play_media(
            plugin,
            play_torrent,
            title=results[0]["title"],
            ids=ids,
            tv_data=tv_data,
            info_hash=results[0]["infoHash"],
            torrent_id=results[0]["debridId"],
            debrid_type=results[0]["debridType"],
            is_debrid=True,
            mode=mode,
        )
        break


@plugin.route("/play_torrent")
@query_arg("title", required=True)
@query_arg("url", required=False)
@query_arg("magnet", required=False)
@query_arg("ids", required=False)
@query_arg("tv_data", required=False)
@query_arg("info_hash", required=False)
@query_arg("torrent_id", required=False)
@query_arg("is_torrent", required=False)
@query_arg("is_debrid", required=False)
@query_arg("debrid_type", required=False)
@query_arg("mode", required=False)
def play_torrent(
    title,
    url="",
    magnet="",
    ids="",
    tv_data="",
    torrent_id="",
    info_hash="",
    mode="",
    debrid_type="",
    is_torrent=False,
    is_debrid=False,
):

    if torrent_id and debrid_type == "RD":
        rd_client = RealDebrid(encoded_token=get_setting("real_debrid_token"))
        url = get_rd_link(rd_client, torrent_id)
    if info_hash and debrid_type == "PM":
        pm_client = Premiumize(token=get_setting("premiumize_token"))
        url = get_pm_link(pm_client, info_hash)
    play(
        url,
        magnet,
        ids,
        tv_data,
        title,
        plugin,
        debrid_type,
        mode,
        is_debrid,
        is_torrent,
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
        notify("Addon Jacktorr not found")


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
    player = JacktookPlayer()
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
    fanart_data = search_fanart_tv(tvdb_id)
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
    fanart_data = search_fanart_tv(tvdb_id)

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


@plugin.route("/get_rd_link_pack")
@query_arg("args", required=False)
@query_arg("ids", required=False)
@query_arg("tv_data", required=False)
@query_arg("mode", required=False)
def get_rd_link_pack(args, ids, mode, tv_data=""):
    id, torrent_id, debrid_type, title = args.split(" ", 3)
    url = get_rd_pack_link(id, torrent_id)
    play(
        url=url,
        magnet="",
        ids=ids,
        tv_data=tv_data,
        mode=mode,
        title=title,
        is_debrid=True,
        debrid_type=debrid_type,
        plugin=plugin,
    )


@plugin.route("/show_pack")
@query_arg("ids", required=False)
@query_arg("query", required=False)
@query_arg("mode", required=False)
@query_arg("tv_data", required=False)
def show_pack(ids, query, mode, tv_data=""):
    info_hash, torrent_id, debrid_type = query.split()
    if debrid_type == "RD":
        info = get_rd_pack(torrent_id)
        if info:
            for id, title in info:
                list_item = ListItem(label=f"{title}")
                set_pack_item_rd(
                    list_item,
                    mode,
                    id,
                    torrent_id,
                    title,
                    ids,
                    tv_data,
                    debrid_type,
                    plugin=plugin,
                )
                set_pack_art(list_item)
            endOfDirectory(plugin.handle)
    elif debrid_type == "PM":
        info = get_pm_pack(info_hash)
        if info:
            for url, title in info:
                list_item = ListItem(label=f"{title}")
                set_pack_item_pm(
                    list_item,
                    mode,
                    url,
                    title,
                    ids,
                    tv_data,
                    debrid_type,
                    plugin=plugin,
                )
                set_pack_art(list_item)
            endOfDirectory(plugin.handle)


@plugin.route("/anilist/<category>")
def anilist(category, page=1):
    setContent(plugin.handle, MOVIES_TYPE)
    search_anilist(category, page, plugin)


@plugin.route("/next_page/anilist/<category>/<page>")
def next_page_anilist(category, page):
    setContent(plugin.handle, MOVIES_TYPE)
    page = int(page) + 1
    search_anilist(category, page, plugin)


@plugin.route("/anilist/episodes/<query>/<id>/<mal_id>")
def get_anime_episodes(query, id, mal_id):
    search_simkl_episodes(query, id, mal_id, plugin=plugin)


@plugin.route("/next_page/<mode>/<page>/<genre_id>")
def next_page(mode, page, genre_id):
    search_tmdb(mode=mode, genre_id=int(genre_id), page=int(page))


@plugin.route("/download")
@query_arg("query", required=True)
def download(query):
    magnet, debrid_type = query.split(" ")
    response = dialogyesno(
        "Kodi", "Do you want to transfer this file to your Debrid Cloud?"
    )
    if response:
        if debrid_type == "RD":
            rd_client = RealDebrid(encoded_token=get_setting("real_debrid_token"))
            Thread(
                target=rd_client.download, args=(magnet,), kwargs={"pack": False}
            ).start()
        else:
            pm_client = Premiumize(token=get_setting("premiumize_token"))
            Thread(
                target=pm_client.download, args=(magnet,), kwargs={"pack": False}
            ).start()


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


@plugin.route("/clear_cached_tmdb")
def clear_cached_tmdb():
    clear_tmdb_cache()
    notify(translation(30240))


@plugin.route("/clear_cached_all")
def clear_cached_all():
    clear_all_cache()
    notify(translation(30244))


@plugin.route("/rd_auth")
def rd_auth():
    rd_client = RealDebrid(encoded_token=get_setting("real_debrid_token"))
    rd_client.auth()


@plugin.route("/pm_auth")
def pm_auth():
    pm_client = Premiumize(token=get_setting("premiumize_token"))
    pm_client.auth()


@plugin.route("/open_burst_config")
def open_burst_config():
    burst_addon_settings()


def torrent_status(info_hash):
    status = api.get_torrent_info(link=info_hash)
    notify(
        "{}".format(status.get("stat_string")),
        status.get("name"),
        sound=False,
    )


def run():
    try:
        plugin.run()
    except Exception as e:
        logging.error("Caught exception:", exc_info=True)
        notify(str(e))
