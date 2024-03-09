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
    fanartv_get,
    get_credentials,
    get_port,
    get_service_address,
    get_state_string,
    is_video,
    list_item,
    process_results,
    set_video_item,
    set_watched_title,
    ssl_enabled,
    tmdb_get,
)
from resources.lib.utils.kodi import (
    ADDON_PATH,
    TORREST_ADDON,
    action,
    addon_settings,
    addon_status,
    buffer_and_play,
    container_update,
    dialogyesno,
    get_setting,
    log,
    notify,
    play_info_hash,
    refresh,
    translation,
)
from xbmcgui import ListItem, DialogProgressBG
from xbmc import getLanguage, ISO_639_1
from xbmcplugin import (
    addDirectoryItem,
    endOfDirectory,
    setPluginCategory,
    setResolvedUrl,
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
    page = int(page)
    data = tmdb_search(mode, genre_id, page, search_tmdb, plugin)
    if data:
        tmdb_show_results(
            data,
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
@query_arg("query", required=False)
@query_arg("ids", required=False)
@query_arg("tvdata", required=False)
@query_arg("rescrape", required=False)
def search(mode="", query="", ids="", tvdata="", rescrape=False):
    if ids:
        _, _, imdb_id = ids.split(", ")
    else:
        imdb_id = -1

    if tvdata:
        episode_name, episode, season = tvdata.split(", ")
    else:
        episode = season = 0
        episode_name = ""

    set_watched_title(query, ids, mode)

    torr_client = get_setting("torrent_client")
    p_dialog = DialogProgressBG()

    results = search_api(query, imdb_id, mode, p_dialog, rescrape, season, episode)
    if results:
        proc_results = process_results(
            results,
            mode,
            episode_name,
            episode,
            season,
        )
        if proc_results:
            if torr_client == "Debrid" or torr_client == "All":
                deb_cached_results = check_debrid_cached(
                    query,
                    proc_results,
                    mode,
                    p_dialog,
                    rescrape,
                    episode,
                )
                if deb_cached_results:
                    final_results = deb_cached_results
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
                tvdata,
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


@plugin.route("/play_torrent")
@query_arg("title", required=True)
@query_arg("url", required=False)
@query_arg("magnet", required=False)
@query_arg("ids", required=False)
@query_arg("tvdata", required=False)
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
    tvdata="",
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
        tvdata,
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
def tv_seasons_details(ids, mode):
    tmdb_id, tvdb_id, _ = ids.split(", ")

    details = tmdb_get("tv_details", tmdb_id)
    name = details.name
    number_of_seasons = details.number_of_seasons
    poster_path = details.get("poster_path", "")
    overview = details.overview

    set_watched_title(name, ids, mode=mode)

    fanart_data = fanartv_get(tvdb_id)
    if fanart_data:
        poster = fanart_data["clearlogo2"]
        fanart = fanart_data["fanart2"]
    else:
        poster = TMDB_POSTER_URL + poster_path
        fanart = poster

    for i in range(number_of_seasons):
        season = i + 1
        title = f"Season {season}"
        list_item = ListItem(label=title)
        list_item.setArt(
            {
                "poster": poster,
                "fanart": fanart,
                "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
            }
        )

        info_tag = list_item.getVideoInfoTag()
        info_tag.setMediaType("video")
        info_tag.setTitle(title)
        info_tag.setPlot(overview)

        list_item.setProperty("IsPlayable", "false")

        addDirectoryItem(
            plugin.handle,
            plugin.url_for(
                tv_episodes_details,
                tv_name=name,
                ids=ids,
                mode=mode,
                season=season,
            ),
            list_item,
            isFolder=True,
        )

    endOfDirectory(plugin.handle)


@plugin.route("/tv/details/season/<tv_name>/<season>")
@query_arg("ids", required=False)
@query_arg("mode", required=False)
def tv_episodes_details(tv_name, season, ids, mode):
    tmdb_id, tvdb_id, _ = ids.split(", ")
    season_details = tmdb_get("season_details", {"id": tmdb_id, "season": season})
    fanart_data = fanartv_get(tvdb_id)
    fanart = fanart_data.get("fanart2", "") if fanart_data else ""

    for ep in season_details.episodes:
        ep_name = ep.name
        episode = ep.episode_number
        title = f"{season}x{episode}. {ep_name}"
        air_date = ep.air_date
        duration = ep.runtime

        still_path = ep.get("still_path", "")
        if still_path:
            poster = TMDB_POSTER_URL + still_path
        else:
            poster = ""

        list_item = ListItem(label=title)
        list_item.setArt(
            {
                "poster": poster,
                "fanart": fanart,
                "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
            }
        )
        info_tag = list_item.getVideoInfoTag()
        info_tag.setMediaType("episode")
        info_tag.setTitle(title)
        info_tag.setSeason(int(season))
        info_tag.setEpisode(int(episode))
        if duration:
            info_tag.setDuration(int(duration))
        info_tag.setFirstAired(air_date)
        info_tag.setPlot(ep.overview)

        tvdata = f"{ep_name}, {episode}, {season}"

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
                        tvdata=tvdata,
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
                query=tv_name,
                episode_name=ep_name,
                ids=ids,
                tvdata=tvdata,
            ),
            list_item,
            isFolder=True,
        )

    endOfDirectory(plugin.handle)


@plugin.route("/get_rd_link_pack")
@query_arg("args", required=False)
@query_arg("ids", required=False)
@query_arg("tvdata", required=False)
@query_arg("mode", required=False)
def get_rd_link_pack(args, ids, mode, tvdata=""):
    id, torrent_id, debrid_type, title = args.split(" ", 3)
    url = get_rd_pack_link(id, torrent_id)
    play(
        url=url,
        magnet="",
        ids=ids,
        tvdata=tvdata,
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
@query_arg("tvdata", required=False)
def show_pack(ids, query, mode, tvdata=""):
    info_hash, torrent_id, debrid_type = query.split()
    if debrid_type == "RD":
        info = get_rd_pack(torrent_id)
        if info:
            for id, title in info:
                list_item = ListItem(label=f"{title}")
                set_video_item(list_item, poster="", overview="")
                addDirectoryItem(
                    plugin.handle,
                    plugin.url_for(
                        get_rd_link_pack,
                        args=f"{id} {torrent_id} {debrid_type} {title}",
                        mode=mode,
                        ids=ids,
                        tvdata=tvdata,
                    ),
                    list_item,
                    isFolder=False,
                )
            endOfDirectory(plugin.handle)
    elif debrid_type == "PM":
        info = get_pm_pack(info_hash)
        if info:
            for url, title in info:
                list_item = ListItem(label=f"{title}")
                set_video_item(list_item, poster="", overview="")
                addDirectoryItem(
                    plugin.handle,
                    plugin.url_for(
                        play_torrent,
                        title=title,
                        url=url,
                        ids=ids,
                        tvdata=tvdata,
                        mode=mode,
                        is_debrid=True,
                        debrid_type=debrid_type,
                    ),
                    list_item,
                    isFolder=False,
                )
            endOfDirectory(plugin.handle)


@plugin.route("/anilist/<category>")
def anilist(category, page=1):
    search_anilist(
        category, page, plugin, search, get_anime_episodes, next_page_anilist
    )


@plugin.route("/next_page/anilist/<category>/<page>")
def next_page_anilist(category, page):
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
