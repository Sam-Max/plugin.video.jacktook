import logging
import os
from threading import Thread
from resources.lib.clients import search_api
from resources.lib.debrid import RealDebrid
import routing

from resources.lib.tmdbv3api.objs.search import Search
from resources.lib.tmdbv3api.objs.genre import Genre
from resources.lib.tmdbv3api.tmdb import TMDb
from resources.lib.tmdb import (
    TMDB_POSTER_URL,
    add_icon_genre,
    tmdb_show_results,
)
from resources.lib.anilist import search_anilist
from resources.lib.utils import (
    check_debrid_cached,
    clear,
    clear_all_cache,
    clear_tmdb_cache,
    fanartv_get,
    get_cached,
    last_files,
    last_titles,
    list_item,
    list_pack_torrent,
    play,
    process_results,
    process_tv_results,
    set_cached,
    set_watched_title,
    show_search_result,
    show_tv_result,
    tmdb_get,
)
from resources.lib.kodi import (
    ADDON_PATH,
    Keyboard,
    addon_settings,
    addon_status,
    dialogyesno,
    get_setting,
    log,
    notify,
    translation,
)
from resources.lib.tmdbv3api.objs.season import Season
from resources.lib.tmdbv3api.objs.tv import TV

from xbmcgui import ListItem, DialogProgressBG
from xbmc import getLanguage, ISO_639_1
from xbmcplugin import (
    addDirectoryItem,
    endOfDirectory,
    setPluginCategory,
)

plugin = routing.Plugin()

tmdb = TMDb()
tmdb.api_key = get_setting("tmdb_apikey", "b70756b7083d9ee60f849d82d94a0d80")
kodi_lang = getLanguage(ISO_639_1)
if kodi_lang:
    tmdb.language = kodi_lang

rd_client = RealDebrid(encoded_token=get_setting("real_debrid_token"))


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
        list_item("Anime", "movies.png"),
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
        plugin.url_for(last_titles_history),
        list_item("Titles History", "history.png"),
        isFolder=True,
    )

    addDirectoryItem(
        plugin.handle,
        plugin.url_for(last_files_history),
        list_item("Files History", "history.png"),
        isFolder=True,
    )
    endOfDirectory(plugin.handle)


@plugin.route("/direct")
def direct_menu():
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(search, mode="multi", query=None, id=-1),
        list_item("Search", "search.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(search, mode="tv", query=None, id=-1),
        list_item("TV Search", "tv.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(search, mode="movie", query=None, id=-1),
        list_item("Movie Search", "movies.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(search, mode="anime", query=None, id=-1),
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


@plugin.route("/search/<mode>/<query>/<id>")
def search(mode, query, id):
    set_watched_title(query, id, mode)
    
    p_dialog = DialogProgressBG()
    torr_client = get_setting("torrent_client")

    cached_results = get_cached(query, params=("index"))
    if cached_results:
        p_results = cached_results
    else:
        results, query = search_api(query, mode, p_dialog)
        if results:
            p_results = process_results(results)
            set_cached(p_results, query, params=("index"))
        else:
            notify("No results")
            p_dialog.close()
            return
    if p_results:
        if torr_client == "Debrid":
            deb_cached_results = get_cached(query, params=("deb"))
            if deb_cached_results:
                cached = True
            else:
                deb_cached_results = check_debrid_cached(p_results, rd_client, p_dialog)
                if deb_cached_results:
                    set_cached(deb_cached_results, query, params=("deb"))
                    cached = True
                else:
                    cached = False
                    notify("No debrid results")
            if cached:
                show_search_result(
                    deb_cached_results,
                    mode,
                    id,
                    plugin,
                    func=play_torrent,
                    func2=show_pack,
                    func3=download,
                )
        elif torr_client == "Torrest":
            show_search_result(
                p_results,
                mode,
                id,
                plugin,
                func=play_torrent,
                func2=show_pack,
                func3=download,
            )
    else:
        notify("No results")

    try:
        p_dialog.close()
    except:
        pass


@plugin.route(
    "/search_season/<mode>/<query>/<tvdb_id>/<episode_name>/<episode>/<season>"
)
def search_tv_episode(mode, query, tvdb_id, episode_name, episode, season):
    set_watched_title(query, tvdb_id, mode)

    torr_client = get_setting("torrent_client")
    p_dialog = DialogProgressBG()

    cached_results = get_cached(query, params=(episode, "index"))
    if cached_results:
        p_results = cached_results
    else:
        results, query = search_api(query, mode, p_dialog, season, episode)
        if results:
            p_results = process_tv_results(
                results,
                episode_name,
                episode,
                season,
            )
            set_cached(p_results, query, params=(episode, "index"))
        else:
            notify("No results")
            p_dialog.close()
            return
    if p_results:
        if torr_client == "Debrid":
            deb_cached_results = get_cached(query, params=(episode, "deb"))
            if deb_cached_results:
                cached = True
            else:
                deb_cached_results = check_debrid_cached(p_results, rd_client, p_dialog)
                if deb_cached_results:
                    set_cached(deb_cached_results, query, params=(episode, "deb"))
                    cached = True
                else:
                    cached = False
                    notify("No debrid results")
            if cached:
                show_tv_result(
                    deb_cached_results,
                    mode,
                    tvdb_id,
                    plugin,
                    func=play_torrent,
                    func2=show_pack,
                    func3=download,
                )
        else:
            show_tv_result(
                p_results,
                mode,
                tvdb_id,
                plugin,
                func=play_torrent,
                func2=show_pack,
                func3=download,
            )
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


@plugin.route("/search_tmdb/<mode>/<genre_id>/<page>")
def search_tmdb(mode, genre_id, page):
    page = int(page)
    genre_id = int(genre_id)

    if mode == "multi":
        text = Keyboard(id=30241)
        if text:
            data = Search().multi(str(text), page=page)
            show_tmdb_results(data, mode, genre_id, page, plugin)
    elif mode == "movie":
        if genre_id != -1:
            data = tmdb_get("discover_movie", {"with_genres": genre_id, "page": page})
        else:
            data = tmdb_get("trending_movie", page)
        show_tmdb_results(data, mode, genre_id, page, plugin)
    elif mode == "tv":
        if genre_id != -1:
            data = tmdb_get("discover_tv", {"with_genres": genre_id, "page": page})
        else:
            data = tmdb_get("trending_tv", page)
        show_tmdb_results(data, mode, genre_id, page, plugin)
    elif mode == "movie_genres" or mode == "tv_genres":
        menu_genre(mode, page)


@plugin.route("/tv/details/<id>")
def tv_details(id):
    tv = TV()
    d = tv.details(id)

    show_name = d.name
    number_of_seasons = d.number_of_seasons
    tvdb_id = d.external_ids.tvdb_id

    set_watched_title(show_name, id=id, mode="tv")

    fanart_data = fanartv_get(tvdb_id)
    if fanart_data:
        poster = fanart_data["clearlogo2"]
        fanart = fanart_data["fanart2"]
    else:
        poster = TMDB_POSTER_URL + d.poster_path if d.get("poster_path") else ""
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
        list_item.setInfo(
            "video",
            {"title": title, "mediatype": "video", "plot": f"{d.overview}"},
        )
        list_item.setProperty("IsPlayable", "false")

        addDirectoryItem(
            plugin.handle,
            plugin.url_for(
                tv_season_details,
                show_name=show_name,
                id=id,
                tvdb_id=tvdb_id,
                season=number,
            ),
            list_item,
            isFolder=True,
        )

    endOfDirectory(plugin.handle)


@plugin.route("/tv/details/season/<show_name>/<id>/<tvdb_id>/<season>")
def tv_season_details(show_name, id, tvdb_id, season):
    tmdb_season = Season()
    season_details = tmdb_season.details(id, season)

    fanart_data = fanartv_get(tvdb_id)
    fanart = fanart_data.get("fanart2") if fanart_data else ""

    for ep in season_details.episodes:
        ep_name = ep.name
        episode = f"{ep.episode_number:02}"
        season = f"{int(season):02}"

        title = f"{season}x{episode}. {ep_name}"
        air_date = ep.air_date
        duration = ep.runtime

        poster = TMDB_POSTER_URL + ep.still_path if ep.get("still_path") else ""

        list_item = ListItem(label=title)
        list_item.setArt(
            {
                "poster": poster,
                "fanart": fanart,
                "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
            }
        )
        list_item.setInfo(
            "video",
            {
                "title": title,
                "mediatype": "video",
                "aired": air_date,
                "duration": duration,
                "plot": f"{ep.overview}",
            },
        )
        list_item.setProperty("IsPlayable", "false")

        query = show_name.replace("/", "").replace("?", "")
        ep_name = ep_name.replace("/", "").replace("?", "")

        addDirectoryItem(
            plugin.handle,
            plugin.url_for(
                search_tv_episode,
                "tv",
                query,
                tvdb_id,
                ep_name,
                episode,
                season,
            ),
            list_item,
            isFolder=True,
        )

    endOfDirectory(plugin.handle)


@plugin.route("/show_pack")
def show_pack():
    id, _ = plugin.args["query"][0].split(" ", 1)
    list_pack_torrent(id, func=play_torrent, client=rd_client, plugin=plugin)


@plugin.route("/anilist/<category>")
def anilist(category, page=1):
    search_anilist(category, page, plugin, action=search, next_action=next_page_anilist)


@plugin.route("/next_page/anilist/<category>/<page>")
def next_page_anilist(category, page):
    search_anilist(
        category, int(page), plugin, action=search, next_action=next_page_anilist
    )


@plugin.route("/next_page/<mode>/<page>/<genre_id>")
def next_page(mode, page, genre_id):
    search_tmdb(mode=mode, genre_id=int(genre_id), page=int(page))


@plugin.route("/download")
def download():
    magnet = plugin.args["query"][0]
    response = dialogyesno(
        "Kodi", "Do you want to transfer this file to your Real Debrid Cloud?"
    )
    if response:
        Thread(
            target=rd_client.download, args=(magnet,), kwargs={"pack": False}
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


@plugin.route("/files_history")
def last_files_history():
    last_files(plugin, clear_history, play_torrent)


@plugin.route("/titles_history")
def last_titles_history():
    last_titles(plugin, clear_history, tv_details, search)


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
    rd_client.auth()


def menu_genre(mode, page):
    if mode == "movie_genres":
        data = Genre().movie_list()
    elif mode == "tv_genres":
        data = Genre().tv_list()

    mode = mode.split("_")[0]

    for d in data.genres:
        name = d["name"]
        if name == "TV Movie":
            continue
        item = ListItem(label=name)
        add_icon_genre(item, name)
        addDirectoryItem(
            plugin.handle,
            plugin.url_for(search_tmdb, mode=mode, genre_id=d["id"], page=page),
            item,
            isFolder=True,
        )
    endOfDirectory(plugin.handle)


def show_tmdb_results(data, mode, genre_id, page, plugin):
    tmdb_show_results(
        data.results,
        func=search,
        func2=tv_details,
        next_func=next_page,
        page=page,
        plugin=plugin,
        genre_id=genre_id,
        mode=mode,
    )


def run():
    try:
        plugin.run()
    except Exception as e:
        logging.error("Caught exception:", exc_info=True)
        notify(str(e))
