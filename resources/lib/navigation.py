from functools import wraps
import logging
import os
from threading import Thread
from resources.lib.api.premiumize_api import Premiumize
from resources.lib.api.real_debrid_api import RealDebrid
from resources.lib.api.torrest_api import STATUS_PAUSED, STATUS_SEEDING, Torrest
from resources.lib.clients import search_api
from resources.lib.debrid import check_debrid_cached
from resources.lib.files_history import last_files
from resources.lib.indexer import indexer_show_results
from resources.lib.play import play
from resources.lib.player import JacktookPlayer
from resources.lib.simkl import search_simkl_episodes
from resources.lib.titles_history import last_titles
from resources.lib.utils.pm_utils import get_pm_link, get_pm_pack
from resources.lib.utils.rd_utils import get_rd_link, get_rd_pack, get_rd_pack_link
from routing import Plugin

from resources.lib.tmdbv3api.tmdb import TMDb
from resources.lib.tmdb import (
    TMDB_POSTER_URL,
    tmdb_search,
    tmdb_show_results,
)
from resources.lib.anilist import search_anilist
from resources.lib.utils.utils import (
    clear,
    clear_all_cache,
    clear_tmdb_cache,
    search_fanart_tv,
    get_credentials,
    get_port,
    get_service_address,
    get_state_string,
    is_video,
    list_item,
    process_results,
    set_pack_art,
    set_pack_item_pm,
    set_pack_item_rd,
    set_video_info,
    set_video_infotag,
    set_watched_title,
    ssl_enabled,
    tmdb_get,
)
from resources.lib.utils.kodi import (
    ADDON_PATH,
    EPISODES_TYPE,
    MOVIES_TYPE,
    SHOWS_TYPE,
    TORREST_ADDON,
    action,
    addon_settings,
    addon_status,
    auto_play,
    buffer_and_play,
    close_all_dialog,
    container_update,
    dialogyesno,
    get_kodi_version,
    get_setting,
    notify,
    play_info_hash,
    play_media,
    refresh,
    set_view,
    translation,
)
from xbmcgui import ListItem, DialogProgressBG
from xbmc import getLanguage, ISO_639_1
from xbmcplugin import (
    addDirectoryItem,
    endOfDirectory,
    setPluginCategory,
    setResolvedUrl,
    setContent,
)

plugin = Plugin()

if TORREST_ADDON:
    api = Torrest(get_service_address(), get_port(), get_credentials(), ssl_enabled())

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


@plugin.route("/")
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

    endOfDirectory(plugin.handle)


@plugin.route("/direct")
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
    endOfDirectory(plugin.handle)


@plugin.route("/anime")
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
    endOfDirectory(plugin.handle)


@plugin.route("/genre")
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
    endOfDirectory(plugin.handle)


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
            func=search,
            func2=tv_seasons_details,
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

    if ids:
        _, _, imdb_id = ids.split(", ")
    else:
        imdb_id = -1

    if tv_data:
        ep_name, episode, season = tv_data.split("(^)")
    else:
        episode = season = 0
        ep_name = ""

    set_watched_title(query, ids, mode)

    torr_client = get_setting("torrent_client")
    p_dialog = DialogProgressBG()

    results = search_api(
        query, imdb_id, mode, media_type, p_dialog, rescrape, season, episode
    )
    if results:
        proc_results = process_results(
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
                    final_results = deb_cached_results
                    if auto_play():
                        close_all_dialog()
                        p_dialog.close()
                        play_first_result(deb_cached_results, ids, tv_data, mode)
                        return
                else:
                    notify("No debrid results")
                    p_dialog.close()
                    return
            elif torr_client == "Torrest" or torr_client == "Elementum":
                final_results = proc_results
            indexer_show_results(
                final_results,
                mode,
                query,
                ids,
                tv_data,
                plugin,
                func=play_torrent,
                func2=show_pack,
                func3=download,
            )
        else:
            notify("No results")
    else:
        notify("No results")

    try:
        p_dialog.close()
    except:
        pass


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


@plugin.route("/play_url")
def play_url():
    info_hash, file_id = plugin.args["query"][0].split(" ")
    serve_url = api.serve_url(info_hash, file_id)
    name = api.torrent_info(info_hash).name

    list_item = ListItem(name, path=serve_url)
    setResolvedUrl(plugin.handle, True, list_item)

    player = JacktookPlayer()
    list_item = player.make_listing(list_item, serve_url, name)
    player.run(list_item)


@plugin.route("/torrents")
def torrents():
    if TORREST_ADDON:
        for torrent in api.torrents():
            context_menu_items = [
                (
                    translation(30700),
                    play_info_hash(torrent.info_hash),
                )
            ]

            if torrent.status.state not in (STATUS_SEEDING, STATUS_PAUSED):
                context_menu_items.append(
                    (
                        translation(30701),
                        action(plugin, torrent_action, torrent.info_hash, "stop"),
                    )
                    if torrent.status.total == torrent.status.total_wanted
                    else (
                        translation(30702),
                        action(plugin, torrent_action, torrent.info_hash, "download"),
                    )
                )

            context_menu_items.extend(
                [
                    (
                        (
                            translation(30703),
                            action(plugin, torrent_action, torrent.info_hash, "resume"),
                        )
                        if torrent.status.paused
                        else (
                            translation(30704),
                            action(plugin, torrent_action, torrent.info_hash, "pause"),
                        )
                    ),
                    (
                        translation(30705),
                        action(
                            plugin, torrent_action, torrent.info_hash, "remove_torrent"
                        ),
                    ),
                    (
                        translation(30706),
                        action(
                            plugin,
                            torrent_action,
                            torrent.info_hash,
                            "remove_torrent_and_files",
                        ),
                    ),
                    (
                        translation(30707),
                        action(
                            plugin, torrent_action, torrent.info_hash, "torrent_status"
                        ),
                    ),
                ]
            )

            list_item = ListItem(label=torrent.name)
            list_item.addContextMenuItems(context_menu_items)
            addDirectoryItem(
                plugin.handle,
                plugin.url_for(torrent_files, torrent.info_hash),
                list_item,
                isFolder=True,
            )

        endOfDirectory(plugin.handle)
    else:
        notify("Addon Torrest not found")


@plugin.route("/torrents/<info_hash>/<action_str>")
def torrent_action(info_hash, action_str):
    needs_refresh = True

    if action_str == "stop":
        api.stop_torrent(info_hash)
    elif action_str == "download":
        api.download_torrent(info_hash)
    elif action_str == "pause":
        api.pause_torrent(info_hash)
    elif action_str == "resume":
        api.resume_torrent(info_hash)
    elif action_str == "remove_torrent":
        api.remove_torrent(info_hash, delete=False)
    elif action_str == "remove_torrent_and_files":
        api.remove_torrent(info_hash, delete=True)
    elif action_str == "torrent_status":
        torrent_status(info_hash)
        needs_refresh = False
    else:
        logging.error("Unknown action '%s'", action_str)
        needs_refresh = False

    if needs_refresh:
        refresh()


@plugin.route("/torrents/<info_hash>/files/<file_id>/<action_str>")
def file_action(info_hash, file_id, action_str):
    if action_str == "download":
        api.download_file(info_hash, file_id)
    elif action_str == "stop":
        api.stop_file(info_hash, file_id)
    else:
        logging.error("Unknown action '%s'", action_str)
        return
    refresh()


@plugin.route("/torrents/<info_hash>")
def torrent_files(info_hash):
    files = api.files(info_hash)
    for f in files:
        serve_url = api.serve_url(info_hash, f.id)
        list_item = ListItem(f.name, "download.png")
        list_item.setPath(serve_url)

        context_menu_items = []
        info_labels = {"title": f.name}

        if is_video(f.name):
            info_type = "video"
        else:
            info_type = None

        if info_type:
            list_item.setInfo(info_type, info_labels)
            list_item.setProperty("IsPlayable", "true")
            context_menu_items.append(
                (translation(30700), buffer_and_play(info_hash, f.id))
            )

        context_menu_items.append(
            (
                translation(30702),
                action(plugin, file_action, info_hash, f.id, "download"),
            )
            if f.status.priority == 0
            else (
                translation(30708),
                action(plugin, file_action, info_hash, f.id, "stop"),
            )
        )

        list_item.addContextMenuItems(context_menu_items)

        if info_type:
            addDirectoryItem(
                plugin.handle,
                plugin.url_for(play_url, query=f"{info_hash} {f.id}"),
                list_item,
                isFolder=False,
            )

    endOfDirectory(plugin.handle)


@plugin.route("/tv/details")
@query_arg("ids", required=False)
@query_arg("mode", required=False)
@query_arg("media_type", required=False)
def tv_seasons_details(ids, mode, media_type=None):
    setContent(plugin.handle, SHOWS_TYPE)
    tmdb_id, tvdb_id, _ = ids.split(", ")

    details = tmdb_get("tv_details", tmdb_id)
    name = details.name
    seasons = details.seasons
    overview = details.overview

    set_watched_title(name, ids, mode=mode)

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
    endOfDirectory(plugin.handle)


@plugin.route("/tv/details/season/<tv_name>/<season>")
@query_arg("ids", required=False)
@query_arg("mode", required=False)
@query_arg("media_type", required=False)
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
                        plugin,
                        search,
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
    endOfDirectory(plugin.handle)


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
                    func=get_rd_link_pack,
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
                    func=play_torrent,
                    plugin=plugin,
                )
                set_pack_art(list_item)
            endOfDirectory(plugin.handle)


@plugin.route("/anilist/<category>")
def anilist(category, page=1):
    setContent(plugin.handle, MOVIES_TYPE)
    search_anilist(
        category, page, plugin, search, get_anime_episodes, next_page_anilist
    )


@plugin.route("/next_page/anilist/<category>/<page>")
def next_page_anilist(category, page):
    setContent(plugin.handle, MOVIES_TYPE)
    page = int(page) + 1
    search_anilist(
        category, page, plugin, search, get_anime_episodes, next_page_anilist
    )


@plugin.route("/anilist/episodes/<query>/<id>/<mal_id>")
def get_anime_episodes(query, id, mal_id):
    search_simkl_episodes(query, id, mal_id, func=search, plugin=plugin)


@plugin.route("/next_page/<mode>/<page>/<genre_id>")
def next_page(mode, page, genre_id):
    search_tmdb(mode=mode, genre_id=int(genre_id), page=int(page))


@plugin.route("/download")
def download():
    magnet, debrid_type = plugin.args["query"][0].split(" ")
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
    last_titles(plugin, clear_history, tv_seasons_details, search)


@plugin.route("/history/files")
def files():
    last_files(plugin, clear_history, play_torrent)


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


def torrent_status(info_hash):
    status = api.torrent_status(info_hash)
    notify(
        "{:s} ({:.2f}%)".format(get_state_string(status.state), status.progress),
        api.torrent_info(info_hash).name,
        sound=False,
    )


def run():
    try:
        plugin.run()
    except Exception as e:
        logging.error("Caught exception:", exc_info=True)
        notify(str(e))
