from functools import wraps
import logging
import os
from threading import Thread
from resources.lib.api.premiumize_api import Premiumize
from resources.lib.api.real_debrid_api import RealDebrid
from resources.lib.api.torrest_api import STATUS_PAUSED, STATUS_SEEDING, Torrest
from resources.lib.clients import search_api
from resources.lib.debrid import check_debrid_cached, get_debrid_pack
from resources.lib.files_history import last_files
from resources.lib.indexer import indexer_show_results
from resources.lib.player import JacktookPlayer
from resources.lib.simkl import search_simkl_episodes
from resources.lib.titles_history import last_titles
from routing import Plugin

from resources.lib.tmdbv3api.tmdb import TMDb
from resources.lib.tmdb import (
    TMDB_POSTER_URL,
    tmdb_search,
    tmdb_show_results,
)
from resources.lib.anilist import search_anilist
from resources.lib.utils.utils import (
    add_play_item,
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
    play,
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
                    if name == "rescrape":
                        kwargs[name] = bool(query_list[0])
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
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(search, mode="tv"),
        list_item("Anime Search", "search.png"),
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
        id, tvdb_id, imdb_id = ids.split(", ")
    else:
        id = tvdb_id = imdb_id = -1
    if tvdata:
        episode_name, episode, season = tvdata.split(", ")
    else:
        episode_name = episode = season = 0

    set_watched_title(query, id, tvdb_id, imdb_id, mode)

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
            if torr_client == "Debrid":
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
                id,
                tvdb_id,
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
def play_torrent():
    url, magnet, id, title = plugin.args["query"][0].split(" ", 3)
    play(url, magnet, id, title, plugin)


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


@plugin.route("/tv/details/<id>")
def tv_seasons_details(id):
    details = tmdb_get("tv_details", id)
    name = details.name
    number_of_seasons = details.number_of_seasons
    tvdb_id = details.external_ids.tvdb_id
    imdb_id = details.external_ids.imdb_id

    set_watched_title(name, id=id, mode="tv")

    fanart_data = fanartv_get(tvdb_id)
    if fanart_data:
        poster = fanart_data["clearlogo2"]
        fanart = fanart_data["fanart2"]
    else:
        poster_path = details.get("poster_path", "")
        poster = TMDB_POSTER_URL + poster_path
        fanart = poster

    for i in range(number_of_seasons):
        number = i + 1
        title = f"Season {number}"
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
        info_tag.setPlot(details.overview)

        list_item.setProperty("IsPlayable", "false")

        addDirectoryItem(
            plugin.handle,
            plugin.url_for(
                tv_episodes_details,
                tv_name=name,
                id=id,
                tvdb_id=tvdb_id,
                imdb_id=imdb_id,
                season=number,
            ),
            list_item,
            isFolder=True,
        )

    endOfDirectory(plugin.handle)


@plugin.route("/tv/details/season/<tv_name>/<id>/<tvdb_id>/<imdb_id>/<season>")
def tv_episodes_details(tv_name, id, tvdb_id, imdb_id, season):
    season_details = tmdb_get("season_details", {"id": id, "season": season})
    fanart_data = fanartv_get(tvdb_id)
    fanart = fanart_data.get("fanart2") if fanart_data else ""

    for ep in season_details.episodes:
        ep_name = ep.name
        episode = ep.episode_number
        title = f"{season}x{episode}. {ep_name}"
        air_date = ep.air_date
        duration = ep.runtime

        query = tv_name.replace("/", "").replace("?", "")
        ep_name = ep_name.replace("/", "").replace("?", "")

        still_path = ep.get("still_path", "")
        if still_path:
            still_path = TMDB_POSTER_URL + still_path

        list_item = ListItem(label=title)
        list_item.setArt(
            {
                "poster": still_path,
                "fanart": fanart,
                "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
            }
        )
        info_tag = list_item.getVideoInfoTag()
        info_tag.setMediaType("video")
        info_tag.setTitle(title)
        if duration:
            info_tag.setDuration(int(duration))
        info_tag.setFirstAired(air_date)
        info_tag.setPlot(ep.overview)

        list_item.setProperty("IsPlayable", "false")
        list_item.addContextMenuItems(
            [
                (
                    "Rescrape item",
                    container_update(
                        plugin,
                        search,
                        mode="tv",
                        query=query,
                        ids=f"{id}, {tvdb_id}, {imdb_id}",
                        tvdata=f"{ep_name}, {episode}, {season}",
                        rescrape=True,
                    ),
                )
            ]
        )
        addDirectoryItem(
            plugin.handle,
            plugin.url_for(
                search,
                mode="tv",
                query=query,
                ids=f"{id}, {tvdb_id}, {imdb_id}",
                tvdata=f"{ep_name}, {episode}, {season}",
            ),
            list_item,
            isFolder=True,
        )

    endOfDirectory(plugin.handle)


@plugin.route("/show_pack")
def show_pack():
    torrent_id, debrid_type = plugin.args["query"][0].split(" ")
    results = get_debrid_pack(torrent_id, debrid_type)
    if results:
        for link, title in results:
            list_item = ListItem(label=f"{title}")
            set_video_item(list_item, poster="", overview="")
            add_play_item(
                list_item,
                link,
                id="",
                magnet="",
                title=title,
                func=play_torrent,
                plugin=plugin,
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
