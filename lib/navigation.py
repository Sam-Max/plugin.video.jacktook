import json
import os
from lib.api.trakt.trakt import ProviderException, TraktAPI
from lib.clients.trakt.trakt import TraktClient

from lib.clients.stremio.catalog_menus import list_stremio_catalogs
from lib.clients.tmdb.tmdb import (
    TmdbClient,
)

from lib.db.cached import cache

from lib.downloader import downloads_viewer
from lib.gui.custom_dialogs import (
    CustomDialog,
    download_dialog_mock,
    resume_dialog_mock,
    run_next_mock,
    source_select_mock,
)

from lib.player import JacktookPLayer
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    CHANGELOG_PATH,
    JACKTORR_ADDON,
    action_url_run,
    build_url,
    burst_addon_settings,
    dialog_text,
    end_of_directory,
    get_setting,
    notification,
    play_info_hash,
    translation,
)
from lib.utils.player.utils import resolve_playback_url
from lib.utils.torrent.torrserver_init import get_torrserver_api
from lib.utils.torrentio.utils import open_providers_selection
from lib.utils.kodi.settings import addon_settings
from lib.utils.kodi.settings_backup import (
    export_settings_backup as kodi_export_settings_backup,
    factory_reset_action as kodi_factory_reset_action,
    reset_all_settings_action as kodi_reset_all_settings_action,
    restore_settings_backup as kodi_restore_settings_backup,
)
from lib.utils.general.utils import (
    build_list_item,
    clear_all_cache,
    clear_trakt_db_cache,
    clear_tmdb_cache as utils_clear_tmdb_cache,
    clear_stremio_cache as utils_clear_stremio_cache,
    clear_debrid_cache as utils_clear_debrid_cache,
    clear_mdblist_cache as utils_clear_mdblist_cache,
    clear_database_cache as utils_clear_database_cache,
    make_listing,
    set_content_type,
    set_pluging_category,
    show_log_export_dialog,
)
import lib.nav.debrid as debrid_navigation
import lib.nav.library_history as library_history_navigation
from lib.utils.general.items_menus import (
    animation_items,
    anime_items,
    movie_items,
    tv_items,
)

from lib.updater import updates_check_addon, downgrade_addon_menu

from xbmcgui import ListItem
from xbmcplugin import (
    addDirectoryItem,
    endOfDirectory,
    setResolvedUrl,
)


from lib.utils.general.items_menus import (
    root_menu_items,
)


def render_menu(items, cache=True):
    for item in items:
        if "condition" in item and not item["condition"]():
            continue

        name = item["name"]
        if isinstance(name, int):
            name = translation(name)

        list_item = build_list_item(name, item["icon"])

        params = item.get("params", {})

        url = build_url(item["action"], **params)

        addDirectoryItem(
            ADDON_HANDLE,
            url,
            list_item,
            isFolder=True,
        )
    end_of_directory(cache=cache)


def root_menu():
    set_pluging_category(translation(90069))
    render_menu(root_menu_items, cache=False)


def animation_menu(params):
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("animation_item", mode="tv"),
        build_list_item(translation(90007), "tv.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("animation_item", mode="movies"),
        build_list_item(translation(90008), "movies.png"),
        isFolder=True,
    )
    end_of_directory()


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
                build_list_item(item["name"], item["icon"]),
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
                    build_list_item(item["name"], item["icon"]),
                    isFolder=True,
                )
    end_of_directory()


def telegram_menu(params):
    set_pluging_category(translation(90013))
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("search_direct", mode="direct"),
        build_list_item(translation(90006), "search.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("list_jackgram_latest_movies", page=1),
        build_list_item("Latest Movies", "movies.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("list_jackgram_latest_series", page=1),
        build_list_item("Latest Series", "tv.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("list_jackgram_raw_files", page=1),
        build_list_item("Raw Files", "cloud.png"),
        isFolder=True,
    )
    end_of_directory()


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
    set_pluging_category(translation(90007))
    stremio_only = get_setting("stremio_only_catalogs", False)

    if not stremio_only:
        for item in tv_items:
            addDirectoryItem(
                ADDON_HANDLE,
                build_url(
                    "search_item",
                    mode=item["mode"],
                    submode=item.get("submode", ""),
                    query=item["query"],
                    api=item["api"],
                ),
                build_list_item(item["name"], item["icon"]),
                isFolder=True,
            )
    list_stremio_catalogs(menu_type="series", sub_menu_type="series")
    end_of_directory()


def movies_items(params):
    set_pluging_category(translation(90008))
    stremio_only = get_setting("stremio_only_catalogs", False)

    if not stremio_only:
        for item in movie_items:
            addDirectoryItem(
                ADDON_HANDLE,
                build_url(
                    "search_item",
                    mode=item["mode"],
                    submode=item.get("submode", ""),
                    query=item["query"],
                    api=item["api"],
                ),
                build_list_item(item["name"], item["icon"]),
                isFolder=True,
            )
    list_stremio_catalogs(menu_type="movie", sub_menu_type="movie")
    end_of_directory()


def direct_menu(params):
    search_direct({"mode": "direct"})


def search_menu(params):
    set_pluging_category(translation(90006))

    # -- Search Movies & TV --
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("handle_tmdb_search", mode="multi", page=1),
        build_list_item(translation(90207), "search.png"),
        isFolder=True,
    )

    # -- Direct Search --
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("search_direct", mode="direct"),
        build_list_item(translation(90011), "search.png"),
        isFolder=True,
    )

    # -- Keyword Search --
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("handle_keyword_search", mode="multi"),
        build_list_item("Search by Keyword", "tmdb.png"),
        isFolder=True,
    )

    # -- Recent TMDb Searches --
    tmdb_history = cache.get_list(key="multi")
    if tmdb_history:
        header = ListItem(label=f"[B][COLOR gray]— {translation(90208)} —[/COLOR][/B]")
        header.setProperty("IsPlayable", "false")
        addDirectoryItem(ADDON_HANDLE, "", header, isFolder=False)

        for _, text in tmdb_history[:5]:
            list_item = ListItem(label=f"[I]{text}[/I]")
            list_item.setArt(
                {"icon": os.path.join(ADDON_PATH, "resources", "img", "tmdb.png")}
            )
            list_item.setProperty("IsPlayable", "false")
            addDirectoryItem(
                ADDON_HANDLE,
                build_url("handle_tmdb_search", mode="multi", page=1, query=text),
                list_item,
                isFolder=True,
            )

    # -- Recent Direct Searches --
    direct_history = cache.get_list(key="direct")
    if direct_history:
        header = ListItem(label=f"[B][COLOR gray]— {translation(90209)} —[/COLOR][/B]")
        header.setProperty("IsPlayable", "false")
        addDirectoryItem(ADDON_HANDLE, "", header, isFolder=False)

        for mode, text in direct_history[:5]:
            list_item = ListItem(label=f"[I]{text}[/I]")
            list_item.setArt(
                {"icon": os.path.join(ADDON_PATH, "resources", "img", "search.png")}
            )
            list_item.setProperty("IsPlayable", "true")
            addDirectoryItem(
                ADDON_HANDLE,
                build_url("search", mode=mode, query=text, direct=True),
                list_item,
                isFolder=False,
            )

    # -- Clear All Search History --
    if tmdb_history or direct_history:
        clear_li = ListItem(label=translation(90210))
        clear_li.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "clear.png")}
        )
        addDirectoryItem(
            ADDON_HANDLE,
            build_url("clear_search_history"),
            clear_li,
            isFolder=True,
        )

    end_of_directory()


def anime_menu(params):
    set_pluging_category(translation(90009))
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("anime_item", mode="tv"),
        build_list_item(translation(90007), "tv.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("anime_item", mode="movies"),
        build_list_item(translation(90008), "movies.png"),
        isFolder=True,
    )
    end_of_directory()


def history_menu(params):
    return library_history_navigation.history_menu(params)


def library_menu(params):
    return library_history_navigation.library_menu(params)


def continue_watching_menu(params):
    return library_history_navigation.continue_watching_menu(params)


def remove_from_continue_watching(params):
    return library_history_navigation.remove_from_continue_watching(params)


def library_shows(params):
    return library_history_navigation.library_shows(params)


def library_movies(params):
    return library_history_navigation.library_movies(params)


def library_calendar(params):
    return library_history_navigation.library_calendar(params)


def remove_from_library(params):
    return library_history_navigation.remove_from_library(params)


def add_to_library(params):
    return library_history_navigation.add_to_library(params)


def anime_item(params):
    set_pluging_category(translation(90009))
    mode = params.get("mode")
    stremio_only = get_setting("stremio_only_catalogs", False)

    if mode == "tv":
        if not stremio_only:
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
                    build_list_item(item["name"], item["icon"]),
                    isFolder=True,
                )
        list_stremio_catalogs(menu_type="anime", sub_menu_type="series")
    if mode == "movies":
        if not stremio_only:
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
                    build_list_item(item["name"], item["icon"]),
                    isFolder=True,
                )
        list_stremio_catalogs(menu_type="anime", sub_menu_type="movie")
    end_of_directory()


def tv_menu(params):
    set_pluging_category(translation(90010))
    list_stremio_catalogs(menu_type="tv")
    end_of_directory()


def search_direct(params):
    return library_history_navigation.search_direct(params)


def search(params):
    from lib.search import run_search_entry

    run_search_entry(params)


def cloud_details(params):
    return debrid_navigation.cloud_details(params)


def cloud(params):
    return debrid_navigation.cloud(params)


def real_debrid_info(params):
    return debrid_navigation.real_debrid_info(params)


def alldebrid_info(params):
    return debrid_navigation.alldebrid_info(params)


def debrider_info(params):
    return debrid_navigation.debrider_info(params)


def easynews_info(params):
    return debrid_navigation.easynews_info(params)


def get_rd_downloads(params):
    return debrid_navigation.get_rd_downloads(params)


def torrents(params):
    if not JACKTORR_ADDON:
        notification(translation(30253))
        return

    for torrent in get_torrserver_api().torrents():
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

        torrent_li = build_list_item(torrent.get("title", ""), "download.png")
        torrent_li.addContextMenuItems(context_menu_items)
        addDirectoryItem(
            ADDON_HANDLE,
            build_url("torrent_files", info_hash=info_hash),
            torrent_li,
            isFolder=True,
        )
    end_of_directory()


def play_media(params):
    data = json.loads(params["data"])
    data = resolve_playback_url(data)
    if not data:
        notification("Failed to resolve playback URL")
        return
    player = JacktookPLayer()
    player.run(data=data)
    del player


def play_url(params):
    url = params.get("url")
    list_item = ListItem(label=params.get("name"), path=url)
    list_item.setPath(url)
    setResolvedUrl(ADDON_HANDLE, True, list_item)


def play_from_pack(params):
    data = json.loads(params.get("data"))
    data = resolve_playback_url(data)
    if not data:
        return
    list_item = make_listing(data)
    setResolvedUrl(ADDON_HANDLE, True, list_item)


def people_menu(mode):
    set_pluging_category("People")
    addDirectoryItem(
        ADDON_HANDLE,
        build_url(
            "search_item",
            mode=mode,
            api="tmdb",
            query="tmdb_people",
            subquery="search_people",
        ),
        build_list_item(translation(90081), "search.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url(
            "search_item",
            mode=mode,
            api="tmdb",
            query="tmdb_people",
            subquery="latest_people",
        ),
        build_list_item(translation(90080), "tmdb.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url(
            "search_item",
            mode=mode,
            api="tmdb",
            query="tmdb_people",
            subquery="popular_people",
        ),
        build_list_item(translation(90079), "tmdb.png"),
        isFolder=True,
    )
    end_of_directory()


def mdblist_menu(mode):
    set_pluging_category("MDblist")
    addDirectoryItem(
        ADDON_HANDLE,
        build_url(
            "search_mdbd_lists",
            mode=mode,
            page=1,
        ),
        build_list_item("Search Lists", "search.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url(
            "top_mdbd_lists",
            mode=mode,
            page=1,
        ),
        build_list_item("Top Lists", "mdblist.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url(
            "user_mdbd_lists",
            mode=mode,
            page=1,
        ),
        build_list_item("User Lists", "mdblist.png"),
        isFolder=True,
    )
    end_of_directory()


def search_item(params):
    query = params.get("query", "")
    category = params.get("category", None)
    api = params["api"]
    mode = params["mode"]
    submode = params.get("submode", "")
    page = int(params.get("page", 1))

    if api == "trakt":
        try:
            result = TraktClient.handle_trakt_query(
                query, category, mode, page, submode, api, params=params
            )
            if result is not None:
                TraktClient.process_trakt_result(
                    result,
                    query,
                    category,
                    mode,
                    submode,
                    api,
                    page,
                    search_term=params.get("search_term", ""),
                )
        except ProviderException as error:
            message = str(error)
            if "Internal Server Error" in message or "Service Unavailable" in message:
                notification("Trakt is temporarily unavailable", time=3500)
            else:
                notification(message.replace("Trakt API error: ", ""), time=3500)
            end_of_directory(cache=False)
    elif api == "tmdb":
        if submode == "people_menu":
            people_menu(mode)
        else:
            TmdbClient.handle_tmdb_query(params)
    elif api == "mdblist":
        mdblist_menu(mode)
    else:
        notification("Unsupported API")


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
        params.get("trakt_id"),
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
    TmdbClient.handle_tmdb_anime_query(category, mode, submode=mode, page=page)


def next_page_anime(params):
    mode = params.get("mode")
    set_content_type(mode)
    TmdbClient.handle_tmdb_anime_query(
        params.get("category"),
        mode,
        params.get("submode"),
        page=int(params.get("page", 1)) + 1,
    )


def download(magnet, type):
    return debrid_navigation.download(magnet, type)


def downloads_menu(params):
    downloads_viewer(params)


def addon_update(params):
    updates_check_addon()


def downgrade_addon(params):
    downgrade_addon_menu()


def show_changelog(params):
    dialog_text("Changelog", file=CHANGELOG_PATH)


def donate(params):
    from lib.utils.debrid.qrcode_utils import make_qrcode

    donation_url = "https://ko-fi.com/sammax09"
    qr_code = make_qrcode(donation_url)

    dialog = CustomDialog(
        "customdialog.xml",
        ADDON_PATH,
        heading=translation(90023),
        text=translation(90022),
        url=f"[COLOR snow]{donation_url}[/COLOR]",
        qrcode=qr_code,
    )
    dialog.doModal()


def settings(params):
    addon_settings()


def export_settings_backup(params):
    kodi_export_settings_backup(params)


def restore_settings_backup(params):
    kodi_restore_settings_backup(params)


def reset_all_settings(params):
    kodi_reset_all_settings_action(params)


def factory_reset(params):
    kodi_factory_reset_action(params)


def clear_all_cached(params):
    clear_all_cache()
    notification(translation(30244))


def clear_trakt_cache(params):
    clear_trakt_db_cache()


def clear_tmdb_cache(params):
    utils_clear_tmdb_cache()


def clear_stremio_cache(params):
    utils_clear_stremio_cache()


def clear_debrid_cache(params):
    utils_clear_debrid_cache()


def clear_mdblist_cache(params):
    utils_clear_mdblist_cache()


def clear_database_cache(params):
    utils_clear_database_cache()


def clear_history(params):
    return library_history_navigation.clear_history(params)


def clear_search_history(params):
    return library_history_navigation.clear_search_history(params)


def kodi_logs(params):
    show_log_export_dialog(params)


def files_history(params):
    return library_history_navigation.files_history(params)


def titles_history(params):
    return library_history_navigation.titles_history(params)


def titles_calendar(params):
    return library_history_navigation.titles_calendar(params)


def rd_auth(params):
    return debrid_navigation.rd_auth(params)


def ad_auth(params):
    return debrid_navigation.ad_auth(params)


def rd_remove_auth(params):
    return debrid_navigation.rd_remove_auth(params)


def ad_remove_auth(params):
    return debrid_navigation.ad_remove_auth(params)


def debrider_auth(params):
    return debrid_navigation.debrider_auth(params)


def debrider_remove_auth(params):
    return debrid_navigation.debrider_remove_auth(params)


def pm_auth(params):
    return debrid_navigation.pm_auth(params)


def trakt_auth(params):
    TraktAPI().auth.trakt_authenticate()


def trakt_auth_revoke(params):
    TraktAPI().auth.trakt_revoke_authentication()


def tb_auth(params):
    return debrid_navigation.tb_auth(params)


def tb_remove_auth(params):
    return debrid_navigation.tb_remove_auth(params)


def torbox_info(params):
    return debrid_navigation.torbox_info(params)


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
