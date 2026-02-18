from datetime import timedelta
import json
import os
from threading import Thread
from lib.api.debrid.alldebrid import AllDebrid
from lib.api.debrid.debrider import Debrider
from lib.api.trakt.trakt import TraktAPI
from lib.clients.debrid.alldebrid import AllDebridHelper
from lib.clients.debrid.torbox import TorboxHelper
from lib.clients.trakt.trakt import TraktClient

from lib.api.debrid.premiumize import Premiumize
from lib.api.debrid.realdebrid import RealDebrid
from lib.api.debrid.torbox import Torbox
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
from lib.clients.debrid.debrider import DebriderHelper
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    ADDON_PATH,
    CHANGELOG_PATH,
    JACKTORR_ADDON,
    action_url_run,
    build_url,
    burst_addon_settings,
    container_update,
    dialog_text,
    end_of_directory,
    get_setting,
    notification,
    play_info_hash,
    kodi_play_media,
    show_keyboard,
    translation,
)
from lib.utils.player.utils import resolve_playback_url
from lib.utils.views.last_files import show_last_files
from lib.utils.views.last_titles import show_last_titles
from lib.utils.views.weekly_calendar import show_weekly_calendar
from lib.utils.torrentio.utils import open_providers_selection
from lib.clients.debrid.realdebrid import RealDebridHelper
from lib.utils.kodi.settings import get_cache_expiration
from lib.utils.kodi.settings import addon_settings
from lib.utils.general.utils import (
    DebridType,
    build_list_item,
    check_debrid_enabled,
    clear_all_cache,
    clear_trakt_db_cache,
    clear_tmdb_cache as utils_clear_tmdb_cache,
    clear_stremio_cache as utils_clear_stremio_cache,
    clear_debrid_cache as utils_clear_debrid_cache,
    clear_mdblist_cache as utils_clear_mdblist_cache,
    clear_database_cache as utils_clear_database_cache,
    clear_history_by_type,
    get_random_color,
    make_listing,
    set_content_type,
    set_pluging_category,
    show_log_export_dialog,
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
)


from lib.utils.general.items_menus import (
    root_menu_items,
    history_menu_items,
    library_menu_items,
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
        build_url("list_telegram_latest", page=1),
        build_list_item("Latest", "cloud.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("list_telegram_files", page=1),
        build_list_item("Video Files", "cloud.png"),
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
    set_pluging_category(translation(90017))
    render_menu(history_menu_items)


def library_menu(params):
    set_pluging_category(translation(90201))
    render_menu(library_menu_items)


def continue_watching_menu(params):
    from lib.utils.views.continue_watching import show_continue_watching

    show_continue_watching()


def remove_from_continue_watching(params):
    from lib.utils.views.continue_watching import remove_continue_watching_item

    remove_continue_watching_item(params)


def library_shows(params):
    from lib.utils.views.library import show_library_items

    show_library_items(mode="tv")


def library_movies(params):
    from lib.utils.views.library import show_library_items

    show_library_items(mode="movies")


def library_calendar(params):
    from lib.utils.views.weekly_calendar import show_weekly_calendar

    show_weekly_calendar(library=True)


def remove_from_library(params):
    from lib.utils.views.library import remove_library_item

    remove_library_item(params)


def add_to_library(params):
    from lib.utils.general.utils import add_to_library as add_lib

    import json

    data = params.get("data")
    if data:
        add_lib(json.loads(data))

    from xbmcgui import Dialog

    Dialog().notification("Jacktook", translation(90205))


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
    set_pluging_category(translation(90011))
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

    list_item = ListItem(label=translation(90006))
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
                    translation(90049),
                    kodi_play_media(
                        name="search",
                        mode=mode,
                        query=text,
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
            build_url("search", mode=mode, query=text, direct=True),
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
    from lib.search import run_search_entry

    run_search_entry(params)


def cloud_details(params):
    debrid_name = params.get("debrid_name")
    if debrid_name == DebridType.RD:
        downloads_method = "get_rd_downloads"
        info_method = "real_debrid_info"
    elif debrid_name == DebridType.DB:
        downloads_method = "get_db_downloads"
        info_method = "debrider_info"
    elif debrid_name == DebridType.AD:
        downloads_method = "get_ad_downloads"
        info_method = "alldebrid_info"
    elif debrid_name == DebridType.PM:
        notification("Not yet implemented")
        return
    elif debrid_name == DebridType.TB:
        downloads_method = (
            "get_tb_downloads"  # Placeholder, will implement later if needed
        )
        info_method = "torbox_info"
    else:
        notification("Unsupported debrid type")
        return

    addDirectoryItem(
        ADDON_HANDLE,
        build_url(downloads_method),
        build_list_item("Downloads", "download.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url(info_method),
        build_list_item("Account Info", "download.png"),
        isFolder=True,
    )
    end_of_directory()


def cloud(params):
    set_pluging_category(translation(90014))
    activated_debrids = [
        debrid for debrid in DebridType.values() if check_debrid_enabled(debrid)
    ]
    for d in activated_debrids:
        torrent_li = build_list_item(d, "download.png")
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "cloud_details",
                debrid_name=d,
            ),
            torrent_li,
            isFolder=True,
        )

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("list_webdav"),
        build_list_item("Webdav", "download.png"),
        isFolder=True,
    )

    end_of_directory()


def real_debrid_info(params):
    RealDebridHelper().get_info()


def alldebrid_info(params):
    AllDebridHelper().get_info()


def debrider_info(params):
    DebriderHelper().get_info()


def get_rd_downloads(params):
    page = int(params.get("page", 1))
    type = DebridType.RD
    debrid_color = get_random_color(type, formatted=False)
    formated_type = f"[B][COLOR {debrid_color}]{type}[/COLOR][/B]"

    rd_client = RealDebrid(token=str(get_setting("real_debrid_token", "")))
    downloads = rd_client.get_user_downloads_list(page=page)

    sorted_downloads = sorted(
        downloads, key=lambda x: x.get("filename", ""), reverse=False
    )
    for d in sorted_downloads:
        torrent_li = build_list_item(
            f"{formated_type} - {d.get('filename')}", "download.png"
        )
        torrent_li.setProperty("IsPlayable", "true")
        addDirectoryItem(
            ADDON_HANDLE,
            build_url("play_url", url=d.get("download"), name=d.get("filename")),
            torrent_li,
            isFolder=False,
        )

    page = page + 1
    next_li = build_list_item("Next", icon="nextpage.png")
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("get_rd_downloads", page=page),
        next_li,
        isFolder=True,
    )
    end_of_directory()


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
        result = TraktClient.handle_trakt_query(
            query, category, mode, page, submode, api
        )
        if result is not None:
            TraktClient.process_trakt_result(
                result, query, category, mode, submode, api, page
            )
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
    if type == "RD":
        rd_client = RealDebrid(token=str(get_setting("real_debrid_token", "")))
        thread = Thread(
            target=rd_client.download, args=(magnet,), kwargs={"pack": False}
        )
    elif type == "TB":
        tb_client = Torbox(token=str(get_setting("torbox_token")))
        thread = Thread(target=tb_client.download, args=(magnet,))
    elif type == "PM":
        pm_client = Premiumize(token=str(get_setting("premiumize_token")))
        thread = Thread(
            target=pm_client.download, args=(magnet,), kwargs={"pack": False}
        )
    else:
        notification("Unsupported debrid type")
        return

    thread.start()


def downloads_menu(params):
    downloads_viewer(params)


def addon_update(params):
    updates_check_addon()


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
    clear_history_by_type(type=params.get("type"))
    notification(translation(90114))


def clear_search_history(params):
    cache.clear_list(key="multi")
    cache.clear_list(key="direct")
    notification(translation(90114))
    import xbmc

    xbmc.executebuiltin("Container.Refresh")


def kodi_logs(params):
    show_log_export_dialog(params)


def files_history(params):
    show_last_files()


def titles_history(params):
    show_last_titles(params)


def titles_calendar(params):
    show_weekly_calendar()


def rd_auth(params):
    rd_client = RealDebrid(token=str(get_setting("real_debrid_token", "")))
    rd_client.auth()


def ad_auth(params):
    ad_client = AllDebrid(token=str(get_setting("all_debrid_token", "")))
    ad_client.auth()


def rd_remove_auth(params):
    rd_client = RealDebrid(token=str(get_setting("real_debrid_token", "")))
    rd_client.remove_auth()


def ad_remove_auth(params):
    ad_client = AllDebrid(token=str(get_setting("all_debrid_token", "")))
    ad_client.remove_auth()


def debrider_auth(params):
    debrider_client = Debrider(token=str(get_setting("debrider_token")))
    debrider_client.auth()


def debrider_remove_auth(params):
    debrider_client = Debrider(token=str(get_setting("debrider_token")))
    debrider_client.remove_auth()


def pm_auth(params):
    pm_client = Premiumize(token=str(get_setting("premiumize_token")))
    pm_client.auth()


def trakt_auth(params):
    TraktAPI().auth.trakt_authenticate()


def trakt_auth_revoke(params):
    TraktAPI().auth.trakt_revoke_authentication()


def tb_auth(params):
    torbox_client = Torbox(token=str(get_setting("torbox_token")))
    torbox_client.auth()


def tb_remove_auth(params):
    torbox_client = Torbox(token=str(get_setting("torbox_token")))
    torbox_client.remove_auth()


def torbox_info(params):
    TorboxHelper().get_info()


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
