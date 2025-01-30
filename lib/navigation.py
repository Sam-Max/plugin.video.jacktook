from ast import literal_eval
from datetime import timedelta
import os
from threading import Thread
from urllib.parse import quote

from lib.clients.debrid.premiumize import Premiumize
from lib.clients.debrid.realdebrid import RealDebrid
from lib.clients.debrid.torbox import Torbox
from lib.api.jacktook.kodi import kodilog
from lib.api.jacktorr_api import TorrServer
from lib.api.tmdbv3api.tmdb import TMDb
from lib.db.bookmark_db import bookmark_db
from lib.gui.custom_dialogs import (
    CustomDialog,
    resume_dialog_mock,
    run_next_mock,
    source_select,
    source_select_mock,
)

from lib.player import JacktookPLayer
from lib.utils.seasons import show_episode_info, show_season_info
from lib.utils.tmdb_utils import get_tmdb_media_details
from lib.utils.torrentio_utils import open_providers_selection
from lib.api.trakt.trakt_api import (
    trakt_authenticate,
    trakt_revoke_authentication,
)
from lib.clients.search import search_client
from lib.files_history import last_files
from lib.play import get_playback_info
from lib.titles_history import last_titles

from lib.trakt import (
    handle_trakt_query,
    show_trakt_list_content,
    show_list_trakt_page,
)

from lib.utils.rd_utils import get_rd_info
from lib.utils.items_menus import tv_items, movie_items, anime_items, animation_items
from lib.utils.debrid_utils import check_debrid_cached

from lib.tmdb import (
    handle_tmdb_anime_query,
    handle_tmdb_query,
    tmdb_search_genres,
    tmdb_search_year,
)
from lib.utils.tmdb_consts import LANGUAGES

from lib.db.cached import cache

from lib.utils.utils import (
    TMDB_POSTER_URL,
    DialogListener,
    clean_auto_play_undesired,
    clear,
    clear_all_cache,
    get_fanart_details,
    get_password,
    get_random_color,
    get_service_host,
    get_username,
    make_listing,
    post_process,
    pre_process,
    get_port,
    list_item,
    set_content_type,
    set_watched_title,
    ssl_enabled,
    check_debrid_enabled,
    Debrids,
)

from lib.utils.kodi_utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    EPISODES_TYPE,
    SHOWS_TYPE,
    JACKTORR_ADDON,
    action_url_run,
    build_url,
    cancel_playback,
    container_update,
    play_media,
    show_keyboard,
    burst_addon_settings,
    get_setting,
    notification,
    play_info_hash,
    set_view,
    translation,
)

from lib.utils.settings import get_cache_expiration, is_auto_play
from lib.utils.settings import addon_settings
from lib.updater import updates_check_addon

from xbmcgui import ListItem
from xbmcplugin import (
    addDirectoryItem,
    endOfDirectory,
    setResolvedUrl,
    setPluginCategory,
    setContent,
)

paginator = None

if JACKTORR_ADDON:
    api = TorrServer(
        get_service_host(), get_port(), get_username(), get_password(), ssl_enabled()
    )

tmdb = TMDb()
tmdb.api_key = get_setting("tmdb_apikey", "b70756b7083d9ee60f849d82d94a0d80")

try:
    language_index = get_setting("language")
    tmdb.language = LANGUAGES[int(language_index)]
except IndexError:
    tmdb.language = "en-US"
except ValueError:
    tmdb.language = "en-US"


def root_menu():
    setPluginCategory(ADDON_HANDLE, "Main Menu")
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("search_tmdb", mode="multi", page=1),
        list_item("Search", "search.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("tv_shows_items"),
        list_item("TV Shows", "tv.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("movies_items"),
        list_item("Movies", "movies.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("anime_menu"),
        list_item("Anime", "anime.png"),
        isFolder=True,
    )

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("animation_menu"),
        list_item("Animation", "anime.png"),
        isFolder=True,
    )

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("direct_menu"),
        list_item("Direct Search", "search.png"),
        isFolder=True,
    )

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("torrents"),
        list_item("Torrents", "magnet2.png"),
        isFolder=True,
    )

    if get_setting("show_telegram_menu"):
        addDirectoryItem(
            ADDON_HANDLE,
            build_url("telegram_menu"),
            list_item("Telegram", "cloud.png"),
            isFolder=True,
        )

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("cloud"),
        list_item("Cloud", "cloud.png"),
        isFolder=True,
    )

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("settings"),
        list_item("Settings", "settings.png"),
        isFolder=True,
    )

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("history"),
        list_item("History", "history.png"),
        isFolder=True,
    )

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("donate"),
        list_item("Donate", "donate.png"),
        isFolder=True,
    )

    # addDirectoryItem(
    #     ADDON_HANDLE,
    #     build_url("test_resume_dialog"),
    #     list_item("Test", ""),
    #     isFolder=False,
    # )

    endOfDirectory(ADDON_HANDLE, cacheToDisc=False)


def animation_menu(params):
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("animation_item", mode="tv"),
        list_item("TV Shows", "tv.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("animation_item", mode="movies"),
        list_item("Movies", "movies.png"),
        isFolder=True,
    )
    endOfDirectory(ADDON_HANDLE)


def animation_item(params):
    mode = params.get("mode")
    if mode == "tv":
        for item in animation_items:
            addDirectoryItem(
                ADDON_HANDLE,
                build_url(
                    "search_item",
                    category=item["category"],
                    mode=item["mode"],
                    submode=mode,
                    api=item["api"],
                ),
                list_item(item["name"], item["icon"]),
                isFolder=True,
            )
    if mode == "movies":
        for item in animation_items:
            if item["api"] == "tmdb":
                addDirectoryItem(
                    ADDON_HANDLE,
                    build_url(
                        "search_item",
                        category=item["category"],
                        mode=item["mode"],
                        submode=mode,
                        api=item["api"],
                    ),
                    list_item(item["name"], item["icon"]),
                    isFolder=True,
                )
    endOfDirectory(ADDON_HANDLE)


def telegram_menu(params):
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("get_telegram_latest", page=1),
        list_item("Latest", "cloud.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("get_telegram_files", page=1),
        list_item("Files", "cloud.png"),
        isFolder=True,
    )
    endOfDirectory(ADDON_HANDLE)


def search_tmdb_year(params):
    mode = params["mode"]
    submode = params["submode"]
    page = int(params["page"])
    year = int(params["year"])

    set_content_type(mode)

    tmdb_search_year(mode, submode, year, page)


def search_tmdb_genres(params):
    mode = params["mode"]
    submode = params["submode"]
    genre_id = params["genre_id"]
    page = int(params["page"])

    set_content_type(mode)

    tmdb_search_genres(mode, genre_id, page, submode=submode)


def tv_shows_items(params):
    for item in tv_items:
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "search_item", mode=item["mode"], query=item["query"], api=item["api"]
            ),
            list_item(item["name"], item["icon"]),
            isFolder=True,
        )
    endOfDirectory(ADDON_HANDLE)


def movies_items(params):
    for item in movie_items:
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "search_item", mode=item["mode"], query=item["query"], api=item["api"]
            ),
            list_item(item["name"], item["icon"]),
            isFolder=True,
        )
    endOfDirectory(ADDON_HANDLE)


def direct_menu(params):
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("search_direct", mode="direct"),
        list_item("Search", "search.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("search_direct", mode="direct"),
        list_item("TV Search", "tv.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("search_direct", mode="direct"),
        list_item("Movie Search", "movies.png"),
        isFolder=True,
    )
    endOfDirectory(ADDON_HANDLE)


def anime_menu(params):
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("anime_item", mode="tv"),
        list_item("Tv Shows", "tv.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("anime_item", mode="movies"),
        list_item("Movies", "movies.png"),
        isFolder=True,
    )
    endOfDirectory(ADDON_HANDLE)


def history(params):
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("files"),
        list_item("Files History", "history.png"),
        isFolder=True,
    )

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("titles"),
        list_item("Titles History", "history.png"),
        isFolder=True,
    )
    endOfDirectory(ADDON_HANDLE)


def anime_item(params):
    mode = params.get("mode")
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("anime_search", mode=mode, category="Anime_Search"),
        list_item("Search", "search.png"),
        isFolder=True,
    )

    if mode == "tv":
        for item in anime_items:
            addDirectoryItem(
                ADDON_HANDLE,
                build_url(
                    "search_item",
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
                    ADDON_HANDLE,
                    build_url(
                        "search_item",
                        category=item["category"],
                        mode=item["mode"],
                        submode=mode,
                        api=item["api"],
                    ),
                    list_item(item["name"], item["icon"]),
                    isFolder=True,
                )
    endOfDirectory(ADDON_HANDLE)


def search_direct(params):
    mode = params.get("mode")
    query = params.get("query", "")
    is_clear = params.get("is_clear", False)
    is_keyboard = params.get("is_keyboard", True)
    update_listing = params.get("update_listing", False)
    rename = params.get("rename", False)

    if is_clear:
        cache.clear_list(key=mode)
        is_keyboard = False

    if rename or is_clear:
        update_listing = True

    if is_keyboard:
        text = show_keyboard(id=30243, default=query)
        if text:
            cache.add_to_list(
                key=mode,
                item=(mode, text),
                expires=timedelta(hours=get_cache_expiration()),
            )

    list_item = ListItem(label=f"Search")
    list_item.setArt(
        {"icon": os.path.join(ADDON_PATH, "resources", "img", "search.png")}
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("search_direct", mode=mode),
        list_item,
        isFolder=True,
    )

    for mode, text in cache.get_list(key=mode):
        list_item = ListItem(label=f"[I]{text}[/I]")
        list_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "search.png")}
        )
        list_item.setProperty("IsPlayable", "true")
        list_item.addContextMenuItems(
            [
                (
                    "Rescrape Item",
                    play_media(
                        name="search",
                        mode=mode,
                        query=quote(text),
                        rescrape=True,
                        direct=True,
                    ),
                ),
                (
                    "Modify Search",
                    container_update(
                        name="search_direct", mode=mode, query=text, rename=True
                    ),
                ),
            ]
        )
        addDirectoryItem(
            ADDON_HANDLE,
            build_url("search", mode=mode, query=quote(text), direct=True),
            list_item,
            isFolder=False,
        )

    list_item = ListItem(label=f"Clear Searches")
    list_item.setArt(
        {"icon": os.path.join(ADDON_PATH, "resources", "img", "clear.png")}
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("search_direct", mode=mode, is_clear=True),
        list_item,
        isFolder=True,
    )

    endOfDirectory(ADDON_HANDLE, updateListing=update_listing)


def search(params):
    query = params["query"]
    mode = params["mode"]
    media_type = params.get("media_type", "")
    ids = params.get("ids", "")
    tv_data = params.get("tv_data", "")
    direct = params.get("direct", False)
    rescrape = params.get("rescrape", False)

    set_content_type(mode, media_type)
    set_watched_title(query, ids, mode, media_type)

    episode, season, ep_name = (0, 0, "")
    if tv_data:
        try:
            ep_name, episode, season = tv_data.split("(^)")
        except ValueError:
            pass

    with DialogListener() as listener:
        results = search_client(
            query, ids, mode, media_type, listener.dialog, rescrape, season, episode
        )
        if not results:
            notification("No results found")
            return

        pre_results = pre_process(
            results,
            mode,
            ep_name,
            episode,
            season,
        )
        if not pre_results:
            notification("No results found for episode")
            return

    if get_setting("torrent_enable"):
        post_results = post_process(pre_results)
    else:
        with DialogListener() as listener:
            cached_results = handle_debrid_client(
                query,
                pre_results,
                mode,
                media_type,
                listener.dialog,
                rescrape,
                episode,
            )
            if not cached_results:
                notification("No cached results found")
                return

            if is_auto_play():
                auto_play(cached_results, ids, tv_data, mode)
                return

            post_results = post_process(cached_results, season)

    data = handle_results(post_results, mode, ids, tv_data, direct)

    if not data:
        cancel_playback()
        return

    player = JacktookPLayer(db=bookmark_db)
    player.run(data=data)
    del player


def handle_results(results, mode, ids, tv_data, direct=False):
    if direct:
        item_info = {"tv_data": tv_data, "ids": ids, "mode": mode}
    else:
        tmdb_id, tvdb_id, _ = [id.strip() for id in ids.split(",")]

        details = get_tmdb_media_details(tmdb_id, mode)
        poster = f"{TMDB_POSTER_URL}{details.poster_path or ''}"
        overview = details.overview or ""

        fanart_data = get_fanart_details(tvdb_id=tvdb_id, tmdb_id=tmdb_id, mode=mode)

        item_info = {
            "poster": poster,
            "fanart": fanart_data["fanart"] or poster,
            "clearlogo": fanart_data["clearlogo"],
            "plot": overview,
            "tv_data": tv_data,
            "ids": ids,
            "mode": mode,
        }

    if mode == "direct":
        xml_file_string = "source_select_direct.xml"
    else:
        xml_file_string = "source_select.xml"

    return source_select(
        item_info,
        xml_file=xml_file_string,
        sources=results,
    )


def handle_debrid_client(
    query,
    proc_results,
    mode,
    media_type,
    p_dialog,
    rescrape,
    episode,
):
    return check_debrid_cached(
        query,
        proc_results,
        mode,
        media_type,
        p_dialog,
        rescrape,
        episode,
    )


def play_torrent(params):
    data = literal_eval(params["data"])
    player = JacktookPLayer(db=bookmark_db)
    player.run(data=data)
    del player


def auto_play(results, ids, tv_data, mode):
    result = clean_auto_play_undesired(results)
    playback_info = get_playback_info(
        data={
            "title": result.get("title"),
            "mode": mode,
            "indexer": result.get("indexer"),
            "type": result.get("type"),
            "ids": ids,
            "info_hash": result.get("infoHash"),
            "tv_data": tv_data,
            "is_torrent": False,
        },
    )
    player = JacktookPLayer(db=bookmark_db)
    player.run(data=playback_info)
    del player


def cloud_details(params):
    type = params.get("type")

    if type == Debrids.RD:
        downloads_method = "get_rd_downloads"
        info_method = "rd_info"
    elif type == Debrids.PM:
        notification("Not yet implemented")
        return
    elif type == Debrids.TB:
        notification("Not yet implemented")
        return
    elif type == Debrids.ED:
        notification("Not yet implemented")
        return

    addDirectoryItem(
        ADDON_HANDLE,
        build_url(downloads_method),
        list_item("Downloads", "download.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url(info_method),
        list_item("Account Info", "download.png"),
        isFolder=True,
    )
    endOfDirectory(ADDON_HANDLE)


def cloud(params):
    activated_debrids = [
        debrid for debrid in Debrids.values() if check_debrid_enabled(debrid)
    ]
    if not activated_debrids:
        return notification("No debrid services activated")

    for debrid_name in activated_debrids:
        torrent_li = list_item(debrid_name, "download.png")
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "cloud_details",
                type=debrid_name,
            ),
            torrent_li,
            isFolder=True,
        )
    endOfDirectory(ADDON_HANDLE)


def rd_info(params):
    get_rd_info()


def get_rd_downloads(params):
    page = int(params.get("page", 1))
    type = Debrids.RD
    debrid_color = get_random_color(type)
    formated_type = f"[B][COLOR {debrid_color}]{type}[/COLOR][/B]"

    rd_client = RealDebrid(token=get_setting("real_debrid_token"))
    downloads = rd_client.get_user_downloads_list(page=page)

    sorted_downloads = sorted(downloads, key=lambda x: x["filename"], reverse=False)
    for d in sorted_downloads:
        torrent_li = list_item(f"{formated_type} - {d['filename']}", "download.png")
        torrent_li.setProperty("IsPlayable", "true")
        addDirectoryItem(
            ADDON_HANDLE,
            build_url("play_url", url=d.get("download"), name=d["filename"]),
            torrent_li,
            isFolder=False,
        )

    page = page + 1
    next_li = list_item("Next", icon="nextpage.png")
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("get_rd_downloads", page=page),
        next_li,
        isFolder=True,
    )
    endOfDirectory(ADDON_HANDLE)


def torrents(params):
    if not JACKTORR_ADDON:
        notification(translation(30253))

    for torrent in api.torrents():
        info_hash = torrent.get("hash")

        context_menu_items = [(translation(30700), play_info_hash(info_hash))]

        if torrent.get("stat") in [2, 3]:
            context_menu_items.append(
                (
                    translation(30709),
                    action_url_run(
                        "torrent_action", info_hash=info_hash, action_str="drop"
                    ),
                )
            )

        context_menu_items.extend(
            [
                (
                    translation(30705),
                    action_url_run(
                        "torrent_action",
                        info_hash=info_hash,
                        action_str="remove_torrent",
                    ),
                ),
                (
                    translation(30707),
                    action_url_run(
                        "torrent_action",
                        info_hash=info_hash,
                        action_str="torrent_status",
                    ),
                ),
            ]
        )

        torrent_li = list_item(torrent.get("title", ""), "download.png")
        torrent_li.addContextMenuItems(context_menu_items)
        addDirectoryItem(
            ADDON_HANDLE,
            build_url("torrent_files", info_hash=info_hash),
            torrent_li,
            isFolder=True,
        )
    endOfDirectory(ADDON_HANDLE)


def play_url(params):
    url = params.get("url")
    list_item = ListItem(label=params.get("name"), path=url)
    list_item.setPath(url)
    setResolvedUrl(ADDON_HANDLE, True, list_item)


def tv_seasons_details(params):
    ids = params["ids"]
    mode = params["mode"]
    media_type = params.get("media_type", None)

    setContent(ADDON_HANDLE, SHOWS_TYPE)
    show_season_info(ids, mode, media_type)
    set_view("widelist")
    endOfDirectory(ADDON_HANDLE)


def tv_episodes_details(params):
    ids = params["ids"]
    mode = params["mode"]
    tv_name = params["tv_name"]
    season = params["season"]
    media_type = params.get("media_type", None)

    setContent(ADDON_HANDLE, EPISODES_TYPE)
    show_episode_info(tv_name, season, ids, mode, media_type)
    set_view("widelist")
    endOfDirectory(ADDON_HANDLE)


def play_from_pack(params):
    data = eval(params.get("data"))
    data = get_playback_info(data)
    list_item = make_listing(data)
    setResolvedUrl(ADDON_HANDLE, True, list_item)


def search_item(params):
    kodilog("search_item")
    query = params.get("query", "")
    category = params.get("category", None)
    api = params["api"]
    mode = params["mode"]
    submode = params.get("submode", None)
    page = int(params.get("page", 1))

    if api == "trakt":
        handle_trakt_query(query, category, mode, page, submode, api)
    elif api == "tmdb":
        handle_tmdb_query(params)


def trakt_list_content(params):
    mode = params.get("mode")
    set_content_type(mode)
    show_trakt_list_content(
        params.get("list_type"),
        mode,
        params.get("user"),
        params.get("slug"),
        params.get("with_auth", ""),
        params.get("page", 1),
    )


def list_trakt_page(params):
    mode = params.get("mode")
    set_content_type(mode)
    show_list_trakt_page(int(params.get("page", "")), mode)


def anime_search(params):
    mode = params.get("mode")
    page = params.get("page", 1)
    category = params.get("category")
    set_content_type(mode)

    handle_tmdb_anime_query(category, mode, submode=mode, page=page)


def next_page_anime(params):
    mode = params.get("mode")
    set_content_type(mode)

    handle_tmdb_anime_query(
        params.get("category"),
        mode,
        params.get("submode"),
        page=int(params.get("page", 1)) + 1,
    )


def download(magnet, type):
    if type == "RD":
        rd_client = RealDebrid(token=get_setting("real_debrid_token"))
        thread = Thread(
            target=rd_client.download, args=(magnet,), kwargs={"pack": False}
        )
    elif type == "TB":
        tb_client = Torbox(token=get_setting("torbox_token"))
        thread = Thread(target=tb_client.download, args=(magnet,))
    elif type == "PM":
        pm_client = Premiumize(token=get_setting("premiumize_token"))
        thread = Thread(
            target=pm_client.download, args=(magnet,), kwargs={"pack": False}
        )
    thread.start()


def addon_update(params):
    updates_check_addon()


def donate(params):
    msg = "If you like Jacktook and appreciate the time and effort invested by me developing this addon you can support me by making a one time payment to:"
    dialog = CustomDialog(
        "customdialog.xml",
        ADDON_PATH,
        heading="Support Jacktook",
        text=msg,
        url="[COLOR snow]https://ko-fi.com/sammax09[/COLOR]",
    )
    dialog.doModal()


def settings(params):
    addon_settings()


def clear_history(params):
    clear(type=params.get("type"))


def titles(params):
    last_titles()


def files(params):
    last_files()


def clear_all_cached(params):
    clear_all_cache()
    notification(translation(30244))


def rd_auth(params):
    rd_client = RealDebrid(token=get_setting("real_debrid_token"))
    rd_client.auth()


def rd_remove_auth(params):
    rd_client = RealDebrid(token=get_setting("real_debrid_token"))
    rd_client.remove_auth()


def pm_auth(params):
    pm_client = Premiumize(token=get_setting("premiumize_token"))
    pm_client.auth()


def trakt_auth(params):
    trakt_authenticate()


def trakt_auth_revoke(params):
    trakt_revoke_authentication()


def open_burst_config(params):
    burst_addon_settings()


def torrentio_selection(params):
    open_providers_selection()


def test_run_next(params):
    run_next_mock()


def test_source_select(params):
    source_select_mock()


def test_resume_dialog(params):
    resume_dialog_mock()
