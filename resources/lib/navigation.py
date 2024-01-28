import logging
import os
from resources.lib.clients import search_api
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
    clear_tmdb_cache,
    fanartv_get,
    get_cached_db,
    last_files,
    last_titles,
    list_item,
    list_pack_torrent,
    play,
    process_results,
    process_tv_results,
    real_debrid_auth,
    set_cached_db,
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
    torr_client = get_setting("torrent_client")
    p_dialog = DialogProgressBG()

    set_watched_title(query, id, mode)

    results, query = search_api(query, mode, dialog=p_dialog)
    if results:
        p_results = process_results(results)
        if p_results:
            if torr_client == "Debrid":
                cached_results = get_cached_db(query, params=(len(p_results)))
                if cached_results:
                    cached = True
                else:
                    cached_results = check_debrid_cached(p_results, p_dialog)
                    if cached_results:
                        set_cached_db(cached_results, query, params=(len(p_results)))
                        cached = True
                    else:
                        cached = False
                        notify("No debrid results")
                if cached:
                    show_search_result(
                        cached_results,
                        mode,
                        id,
                        plugin,
                        func=play_torrent,
                        func2=show_pack,
                    )
            else:
                show_search_result(
                    p_results,
                    mode,
                    id,
                    plugin,
                    func=play_torrent,
                    func2=show_pack,
                )
    else:
        notify("No results")

    p_dialog.close()


@plugin.route(
    "/search_season/<mode>/<query>/<tvdb_id>/<episode_name>/<episode_num>/<season_num>"
)
def search_tv_episode(mode, query, tvdb_id, episode_name, episode_num, season_num):
    torr_client = get_setting("torrent_client")
    p_dialog = DialogProgressBG()

    results, query = search_api(query, mode, p_dialog)
    if results:
        p_results = process_tv_results(
            results,
            episode_name,
            episode_num,
            season_num,
        )
        if p_results:
            if torr_client == "Debrid":
                cached_results = get_cached_db(
                    query, params=(episode_num, len(p_results))
                )
                if cached_results:
                    cached = True
                else:
                    cached_results = check_debrid_cached(p_results, p_dialog)
                    if cached_results:
                        set_cached_db(
                            cached_results, query, params=(episode_num, len(p_results))
                        )
                        cached = True
                    else:
                        cached = False
                        notify("No debrid results")
                if cached:
                    show_tv_result(
                        cached_results,
                        mode,
                        tvdb_id,
                        plugin,
                        func=play_torrent,
                        func2=show_pack,
                    )
            else:
                show_tv_result(
                    p_results,
                    mode,
                    tvdb_id,
                    plugin,
                    func=play_torrent,
                    func2=show_pack,
                )
    else:
        notify("No results")

    p_dialog.close()


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
            results = Search().multi(str(text), page=page)
        tmdb_show_results(
            results,
            func=search,
            func2=tv_details,
            next_func=next_page,
            page=page,
            plugin=plugin,
            genre_id=genre_id,
            mode=mode,
        )
    elif mode == "movie":
        if genre_id != -1:
            data = tmdb_get("discover_movie", {"with_genres": genre_id, "page": page})
        else:
            data = tmdb_get("trending_movie", page)
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
    elif mode == "tv":
        if genre_id != -1:
            data = tmdb_get("discover_tv", {"with_genres": genre_id, "page": page})
        else:
            data = tmdb_get("trending_tv", page)
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
    elif mode == "movie_genres":
        menu_genre(mode, page)
    elif mode == "tv_genres":
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
                season_num=number,
            ),
            list_item,
            isFolder=True,
        )

    endOfDirectory(plugin.handle)


@plugin.route("/tv/details/season/<show_name>/<id>/<tvdb_id>/<season_num>")
def tv_season_details(show_name, id, tvdb_id, season_num):
    season = Season()
    tv_season = season.details(id, season_num)

    fanart_data = fanartv_get(tvdb_id)
    fanart = fanart_data.get("fanart2") if fanart_data else ""

    for ep in tv_season.episodes:
        ep_name = ep.name
        ep_num = f"{ep.episode_number:02}"
        season_num_ = f"{int(season_num):02}"

        title = f"{season_num}x{ep_num}. {ep_name}"
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

        query = show_name.replace("/", "")
        ep_name = ep_name.replace("/", "")

        query = f"{query} S{season_num_}E{ep_num}"

        addDirectoryItem(
            plugin.handle,
            plugin.url_for(
                search_tv_episode,
                "tv",
                query,
                tvdb_id,
                ep_name,
                ep_num,
                season_num_,
            ),
            list_item,
            isFolder=True,
        )

    endOfDirectory(plugin.handle)


@plugin.route("/show_pack")
def show_pack():
    id, _ = plugin.args["query"][0].split(" ", 1)
    list_pack_torrent(id, func=play_torrent, plugin=plugin)


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


def menu_genre(mode, page):
    if mode == "movie_genres":
        movies = Genre().movie_list()
        for gen in movies.genres:
            if gen["name"] == "TV Movie":
                continue
            name = gen["name"]
            item = ListItem(label=name)
            add_icon_genre(item, name)
            addDirectoryItem(
                plugin.handle,
                plugin.url_for(
                    search_tmdb, mode="movie", genre_id=gen["id"], page=page
                ),
                item,
                isFolder=True,
            )
    elif mode == "tv_genres":
        tv = Genre().tv_list()
        for gen in tv.genres:
            name = gen["name"]
            item = ListItem(label=name)
            add_icon_genre(item, name)
            addDirectoryItem(
                plugin.handle,
                plugin.url_for(search_tmdb, mode="tv", genre_id=gen["id"], page=page),
                item,
                isFolder=True,
            )
    endOfDirectory(plugin.handle)


@plugin.route("/clear_cached_tmdb")
def clear_cached_tmdb():
    clear_tmdb_cache()
    notify(translation(30240))


@plugin.route("/rd_auth")
def rd_auth():
    real_debrid_auth()


def run():
    try:
        plugin.run()
    except Exception as e:
        logging.error("Caught exception:", exc_info=True)
        notify(str(e))
