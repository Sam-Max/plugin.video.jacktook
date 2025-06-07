from datetime import timedelta
import json
import os
from threading import Thread
from typing import List
from urllib.parse import quote

from lib.api.jacktorr.jacktorr import TorrServer
from lib.api.tmdbv3api.tmdb import TMDb
from lib.api.trakt.trakt import TraktAPI
from lib.clients.trakt.trakt import TraktClient

from lib.clients.debrid.premiumize import Premiumize
from lib.clients.debrid.realdebrid import RealDebrid
from lib.clients.debrid.torbox import Torbox
from lib.clients.stremio.catalogs import list_stremio_catalogs
from lib.clients.tmdb.tmdb import (
    TmdbClient,
    TmdbAnimeClient,
)
from lib.clients.tmdb.utils import LANGUAGES, get_tmdb_media_details
from lib.clients.search import search_client

from lib.db.cached import cache

from lib.domain.torrent import TorrentStream
from lib.downloader import downloads_viewer
from lib.gui.custom_dialogs import (
    CustomDialog,
    download_dialog_mock,
    resume_dialog_mock,
    run_next_mock,
    source_select,
    source_select_mock,
)

from lib.player import JacktookPLayer
from lib.utils.debrid.ed_utils import EasyDebridHelper
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    EPISODES_TYPE,
    JACKTORR_ADDON,
    SHOWS_TYPE,
    action_url_run,
    build_url,
    burst_addon_settings,
    cancel_playback,
    container_update,
    get_setting,
    kodilog,
    notification,
    play_info_hash,
    play_media,
    set_view,
    show_keyboard,
    translation,
)
from lib.utils.player.utils import resolve_playback_source
from lib.utils.views.last_files import show_last_files
from lib.utils.views.last_titles import show_last_titles
from lib.utils.views.shows import show_episode_info, show_season_info
from lib.utils.torrentio.utils import open_providers_selection
from lib.utils.debrid.rd_utils import RealDebridHelper
from lib.utils.debrid.debrid_utils import check_debrid_cached
from lib.utils.kodi.settings import auto_play_enabled, get_cache_expiration
from lib.utils.kodi.settings import addon_settings
from lib.utils.general.utils import (
    TMDB_POSTER_URL,
    Debrids,
    DialogListener,
    check_debrid_enabled,
    clean_auto_play_undesired,
    clear,
    clear_all_cache,
    get_fanart_details,
    get_password,
    get_port,
    get_random_color,
    get_service_host,
    get_username,
    list_item,
    make_listing,
    post_process,
    pre_process,
    set_content_type,
    set_watched_title,
    ssl_enabled,
)
from lib.utils.general.items_menus import (
    animation_items,
    anime_items,
    movie_items,
    tv_items,
)

from lib.updater import updates_check_addon

from xbmcgui import ListItem
from xbmcplugin import (
    addDirectoryItem,
    endOfDirectory,
    setResolvedUrl,
    setPluginCategory,
    setContent,
)
import xbmc


paginator = None

if JACKTORR_ADDON:
    torrserver_api = TorrServer(
        get_service_host(), get_port(), get_username(), get_password(), ssl_enabled()
    )

tmdb = TMDb()
tmdb.api_key = get_setting("tmdb_api_key", "b70756b7083d9ee60f849d82d94a0d80")

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
        build_url("handle_tmdb_search", mode="multi", page=1),
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

    # addDirectoryItem(
    #     ADDON_HANDLE,
    #     build_url("animation_menu"),
    #     list_item("Animation", "anime.png"),
    #     isFolder=True,
    # )

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("tv_menu"),
        list_item("Live TV", "tv.png"),
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
        build_url("downloads_menu"),
        list_item("Downloads", "cloud.png"),
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
        build_url("history_menu"),
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
    #     build_url("test_download_dialog"),
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
        build_url("search_direct", mode="direct"),
        list_item("Search", "search.png"),
        isFolder=True,
    )
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

    TmdbClient.tmdb_search_year(mode, submode, year, page)


def search_tmdb_genres(params):
    mode = params["mode"]
    submode = params["submode"]
    genre_id = params["genre_id"]
    page = int(params["page"])

    set_content_type(mode)

    TmdbClient.tmdb_search_genres(mode, genre_id, page, submode=submode)


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
    list_stremio_catalogs(menu_type="series", sub_menu_type="series")
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
    list_stremio_catalogs(menu_type="movie", sub_menu_type="movie")
    endOfDirectory(ADDON_HANDLE)


def direct_menu(params):
    search_direct({"mode": "direct"})


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


def history_menu(params):
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("files_history"),
        list_item("Files History", "history.png"),
        isFolder=True,
    )

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("titles_history"),
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
        list_stremio_catalogs(menu_type="anime", sub_menu_type="series")
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
        list_stremio_catalogs(menu_type="anime", sub_menu_type="movie")
    endOfDirectory(ADDON_HANDLE)


def tv_menu(params):
    list_stremio_catalogs(menu_type="tv")
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
    ids = json.loads(params.get("ids", "{}"))
    tv_data = json.loads(params.get("tv_data", "{}"))
    direct = params.get("direct", False)
    rescrape = params.get("rescrape", False)

    kodilog(f"Search: {query} - {ids} - {mode} - {tv_data}")

    set_content_type(mode, media_type)
    set_watched_title(query, ids, mode, media_type)

    ep_name, episode, season = extract_tv_data(tv_data)

    results = perform_search(query, ids, mode, media_type, rescrape, season, episode)
    kodilog(f"Search results: {results}", level=xbmc.LOGDEBUG)
    if not results:
        notification("No results found")
        return

    pre_results = pre_process_results(results, mode, ep_name, episode, season)
    kodilog(f"Pre-processed results: {pre_results}", level=xbmc.LOGDEBUG)
    if not pre_results:
        notification("No results found")
        return

    post_results = process_results(
        pre_results, query, mode, media_type, rescrape, episode, season
    )
    kodilog(f"Post-processed results: {post_results}", level=xbmc.LOGDEBUG)
    if not post_results:
        notification("No cached results found")
        return

    if auto_play_enabled():
        auto_play(post_results, ids, tv_data, mode)
        return

    data = handle_results(post_results, mode, ids, tv_data, direct)
    if not data:
        cancel_playback()
        return

    play_data(data)


def extract_tv_data(tv_data):
    if tv_data:
        return (
            tv_data.get("name", ""),
            tv_data.get("episode", 0),
            tv_data.get("season", 0),
        )
    return "", 0, 0


def perform_search(
    query: str,
    ids: dict,
    mode: str,
    media_type: str,
    rescrape: bool,
    season: int,
    episode: int,
) -> List[TorrentStream]:
    with DialogListener() as listener:
        return search_client(
            query, ids, mode, media_type, listener.dialog, rescrape, season, episode
        )


def pre_process_results(
    results: List[TorrentStream], mode: str, ep_name: str, episode: int, season: int
) -> List[TorrentStream]:
    return pre_process(results, mode, ep_name, episode, season)


def process_results(
    pre_results: List[TorrentStream],
    query: str,
    mode: str,
    media_type: str,
    rescrape: bool,
    episode: int,
    season: int,
) -> List[TorrentStream]:
    if get_setting("torrent_enable"):
        return post_process(pre_results)
    else:
        with DialogListener() as listener:
            return check_debrid_cached(
                query, pre_results, mode, media_type, listener.dialog, rescrape, episode
            )


def play_data(data: dict):
    player = JacktookPLayer()
    player.run(data=data)
    del player


def handle_results(
    results: List[TorrentStream],
    mode: str,
    ids: dict,
    tv_data: dict,
    direct: bool = False,
) -> dict:
    item_info = {"tv_data": tv_data, "ids": ids, "mode": mode}

    if not direct and ids:
        tmdb_id = ids.get("tmdb_id")
        tvdb_id = ids.get("tvdb_id")
        details = get_tmdb_media_details(tmdb_id, mode)
        poster = f"{TMDB_POSTER_URL}{getattr(details, 'poster_path', '') or ''}"
        overview = getattr(details, "overview", "") or ""
        fanart_data = get_fanart_details(tvdb_id=tvdb_id, tmdb_id=tmdb_id, mode=mode)
        item_info.update(
            {
                "poster": poster,
                "fanart": fanart_data.get("fanart") or poster,
                "clearlogo": fanart_data.get("clearlogo"),
                "plot": overview,
            }
        )

    xml_file_string = (
        "source_select_direct.xml" if mode == "direct" else "source_select.xml"
    )

    return source_select(
        item_info,
        xml_file=xml_file_string,
        sources=results,
    )


def play_torrent(params):
    data = json.loads(params["data"])
    player = JacktookPLayer()
    player.run(data=data)
    del player


def auto_play(results: List[TorrentStream], ids, tv_data, mode):
    filtered_results = clean_auto_play_undesired(results)
    if not filtered_results:
        notification("No suitable source found for auto play.")
        cancel_playback()
        return

    preferred_quality = get_setting("auto_play_quality")
    quality_matches = [
        r for r in filtered_results if preferred_quality.lower() in r.quality.lower()
    ]
    
    if not quality_matches:
        notification("No sources found with the preferred quality.")
        cancel_playback()
        return
    
    selected_result = quality_matches[0]

    kodilog(f"Selected result for auto play: {selected_result}")

    playback_info = resolve_playback_source(
        data={
            "title": selected_result.title,
            "mode": mode,
            "indexer": selected_result.indexer,
            "type": selected_result.type,
            "ids": ids,
            "info_hash": selected_result.infoHash,
            "tv_data": tv_data,
            "is_torrent": False,
        },
    )

    player = JacktookPLayer()
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
        downloads_method = "get_ed_downloads"
        info_method = "ed_info"

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
    RealDebridHelper().get_rd_info()


def ed_info(params):
    EasyDebridHelper().get_ed_info()


def get_rd_downloads(params):
    page = int(params.get("page", 1))
    type = Debrids.RD
    debrid_color = get_random_color(type, formatted=False)
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

    for torrent in torrserver_api.torrents():
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
    ids = json.loads(params.get("ids", "{}"))
    mode = params["mode"]
    media_type = params.get("media_type", None)

    setContent(ADDON_HANDLE, SHOWS_TYPE)
    show_season_info(ids, mode, media_type)
    set_view("widelist")
    endOfDirectory(ADDON_HANDLE)


def tv_episodes_details(params):
    ids = json.loads(params.get("ids", "{}"))
    mode = params["mode"]
    tv_name = params["tv_name"]
    season = params["season"]
    media_type = params.get("media_type", None)

    setContent(ADDON_HANDLE, EPISODES_TYPE)
    show_episode_info(tv_name, season, ids, mode, media_type)
    set_view("widelist")
    endOfDirectory(ADDON_HANDLE)


def play_from_pack(params):
    data = json.loads(params.get("data"))
    data = resolve_playback_source(data)
    list_item = make_listing(data)
    setResolvedUrl(ADDON_HANDLE, True, list_item)


def search_item(params):
    query = params.get("query", "")
    category = params.get("category", None)
    api = params["api"]
    mode = params["mode"]
    submode = params.get("submode", None)
    page = int(params.get("page", 1))

    if api == "trakt":
        result = TraktClient.handle_trakt_query(
            query, category, mode, page, submode, api
        )
        if result:
            TraktClient.process_trakt_result(
                result, query, category, mode, submode, api, page
            )
    elif api == "tmdb":
        TmdbClient.handle_tmdb_query(params)


def trakt_list_content(params):
    mode = params.get("mode")
    set_content_type(mode)
    TraktClient.show_trakt_list_content(
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
    TraktClient.show_list_trakt_page(int(params.get("page", "")), mode)


def anime_search(params):
    mode = params.get("mode")
    page = params.get("page", 1)
    category = params.get("category")
    set_content_type(mode)

    TmdbAnimeClient.handle_tmdb_anime_query(category, mode, submode=mode, page=page)


def next_page_anime(params):
    mode = params.get("mode")
    set_content_type(mode)

    TmdbAnimeClient.handle_tmdb_anime_query(
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


def downloads_menu(params):
    downloads_viewer(params)


def addon_update(params):
    updates_check_addon()


def donate(params):
    msg = "If you enjoy using Jacktook and appreciate the time and effort we are investing in developing this addon, you can support us with a contribution at:"
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


def files_history(params):
    show_last_files()


def titles_history(params):
    show_last_titles()


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
    TraktAPI().auth.trakt_authenticate()


def trakt_auth_revoke(params):
    TraktAPI().auth.trakt_revoke_authentication()


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


def test_download_dialog(params):
    download_dialog_mock()
