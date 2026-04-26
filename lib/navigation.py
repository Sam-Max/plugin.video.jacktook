import json
import os
from lib.api.trakt.trakt import ProviderException, TraktAPI
from lib.clients.trakt.trakt import TraktClient

from lib.clients.stremio.catalog_menus import list_stremio_catalogs
from lib.clients.tmdb.tmdb import (
    TmdbClient,
)

from lib.db.cached import RuntimeCache, cache

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
    add_directory_items_batch,
    apply_section_view,
    action_url_run,
    build_url,
    burst_addon_settings,
    capture_current_view_id,
    dialog_text,
    end_of_directory,
    execute_builtin,
    finish_action,
    clear_cached_settings,
    get_setting,
    is_youtube_addon_enabled,
    kodilog,
    notification,
    play_info_hash,
    reset_saved_views,
    save_view_id,
    translation,
    make_list_item,
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
from lib.clients.youtube_resolver import (
    extract_video_id,
    resolve_item_trailer,
)
import lib.nav.debrid as debrid_navigation
import lib.nav.library_history as library_history_navigation
from lib.utils.general.items_menus import (
    animation_items,
    anime_items,
    movie_items,
    trakt_movie_discovery_items,
    trakt_movie_library_items,
    trakt_tv_discovery_items,
    trakt_tv_library_items,
    tv_items,
)

from lib.updater import updates_check_addon, downgrade_addon_menu

from xbmcgui import ListItem
from xbmcplugin import (
    addDirectoryItem,
    setResolvedUrl,
)


from lib.utils.general.items_menus import (
    root_menu_items,
)


def _menu_condition_signature(items):
    signature = []
    for item in items:
        condition = item.get("condition")
        signature.append(True if condition is None else bool(condition()))
    return tuple(signature)


def _get_cached_menu_entries(cache_key, builder, *builder_args, **builder_kwargs):
    cached_menu_entries = RuntimeCache.get(cache_key)
    if cached_menu_entries is not None:
        return cached_menu_entries

    menu_entries = builder(*builder_args, **builder_kwargs)
    RuntimeCache.set(cache_key, menu_entries)
    return menu_entries


def _build_search_item_menu_entries(items, mode=None, filter_api=None):
    menu_entries = []
    for item in items:
        if filter_api and item.get("api") != filter_api:
            continue
        menu_entries.append(
            {
                "url": build_url(
                    "search_item",
                    category=item["category"],
                    mode=item["mode"],
                    submode=mode,
                    api=item["api"],
                ),
                "name": item["name"],
                "icon": item["icon"],
                "is_folder": True,
            }
        )
    return menu_entries


def _build_media_menu_entries(items):
    menu_entries = []
    for item in items:
        if item.get("action"):
            url = build_url(item["action"], **item.get("params", {}))
        else:
            url = build_url(
                "search_item",
                mode=item["mode"],
                submode=item.get("submode", ""),
                query=item["query"],
                api=item["api"],
            )
        menu_entries.append(
            {
                "url": url,
                "name": item["name"],
                "icon": item["icon"],
                "is_folder": True,
            }
        )
    return menu_entries


def _tv_menu_entries():
    return _build_media_menu_entries(tv_items)


def _movie_menu_entries():
    return _build_media_menu_entries(movie_items)


def _animation_item_menu_entries(mode):
    return _build_search_item_menu_entries(
        animation_items,
        mode=mode,
        filter_api=None if mode == "tv" else "tmdb",
    )


def _animation_menu_entries():
    return [
        {
            "url": build_url("animation_item", mode="tv"),
            "name": translation(90007),
            "icon": "tv.png",
            "is_folder": True,
        },
        {
            "url": build_url("animation_item", mode="movies"),
            "name": translation(90008),
            "icon": "movies.png",
            "is_folder": True,
        },
    ]


def _anime_menu_entries():
    return [
        {
            "url": build_url("anime_item", mode="tv"),
            "name": translation(90007),
            "icon": "tv.png",
            "is_folder": True,
        },
        {
            "url": build_url("anime_item", mode="movies"),
            "name": translation(90008),
            "icon": "movies.png",
            "is_folder": True,
        },
    ]


def _anime_item_menu_entries(mode):
    return _build_search_item_menu_entries(anime_items, mode=mode)


def _render_cached_menu_entries(menu_entries, cache=True):
    directory_items = []
    for menu_entry in menu_entries:
        directory_items.append(
            (
                menu_entry["url"],
                build_list_item(menu_entry["name"], menu_entry["icon"]),
                menu_entry.get("is_folder", True),
            )
        )
    add_directory_items_batch(directory_items)


def render_menu(items, cache=True, cache_key=None):
    def _build_menu_entries():
        menu_entries = []
        for item in items:
            if "condition" in item and not item["condition"]():
                continue
            name = item["name"]
            if isinstance(name, int):
                name = translation(name)
            menu_entries.append(
                {
                    "name": name,
                    "icon": item["icon"],
                    "url": build_url(item["action"], **item.get("params", {})),
                    "is_folder": item.get("is_folder", True),
                }
            )
        return menu_entries

    menu_entries = (
        _build_menu_entries()
        if not cache_key
        else _get_cached_menu_entries(cache_key, _build_menu_entries)
    )
    _render_cached_menu_entries(menu_entries)
    end_of_directory(cache=cache)


def _translate_view_label(label):
    if isinstance(label, str) and label.isdigit():
        return translation(int(label))
    return label or translation(90712)


def _set_chooser_content(content_type):
    chooser_modes = {
        "movies": "movies",
        "tvshows": "tv",
        "seasons": "season",
        "episodes": "episode",
        "files": "files",
    }
    chooser_mode = chooser_modes.get(content_type)
    if chooser_mode:
        set_content_type(chooser_mode)


def choose_view(params):
    view_key = params.get("view_key", "view.main")
    content_type = params.get("content_type", "")
    label = _translate_view_label(params.get("label", "90712"))
    set_pluging_category(label)
    addDirectoryItem(
        ADDON_HANDLE,
        build_url(
            "save_view",
            view_key=view_key,
            content_type=content_type,
            label=params.get("label", "90712"),
        ),
        build_list_item(translation(90721), "settings.png"),
        isFolder=False,
    )
    _set_chooser_content(content_type)
    end_of_directory(cache=False)
    apply_section_view(view_key, content_type=content_type)


def settings_menu(params):
    set_pluging_category(translation(90016))
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("settings"),
        build_list_item(translation(90742), "settings.png"),
        isFolder=False,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("views_menu"),
        build_list_item(translation(90743), "settings.png"),
        isFolder=True,
    )
    end_of_directory(cache=False)
    apply_section_view("view.main")


def views_menu(params):
    set_pluging_category(translation(90712))
    view_items = (
        ("view.main", "", "90713"),
        ("view.movies", "movies", "90714"),
        ("view.tvshows", "tvshows", "90715"),
        ("view.seasons", "seasons", "90716"),
        ("view.episodes", "episodes", "90717"),
        ("view.library", "tvshows", "90718"),
        ("view.history", "", "90719"),
        ("view.downloads", "files", "90720"),
    )
    for view_key, content_type, label in view_items:
        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "choose_view",
                view_key=view_key,
                content_type=content_type,
                label=label,
            ),
            build_list_item(_translate_view_label(label), "settings.png"),
            isFolder=True,
        )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("reset_views"),
        build_list_item(translation(90725), "settings.png"),
        isFolder=False,
    )
    end_of_directory(cache=False)
    apply_section_view("view.main")


def save_view(params):
    view_key = params.get("view_key", "view.main")
    label = _translate_view_label(params.get("label", "90712"))
    view_id = capture_current_view_id()
    if not view_id or not save_view_id(view_key, view_id):
        notification(label, translation(90723))
        return
    notification(label, translation(90722))


def reset_views(params):
    reset_saved_views()
    notification(translation(90712), translation(90724))


def root_menu():
    set_pluging_category(translation(90069))
    render_menu(
        root_menu_items,
        cache=False,
        cache_key=f"nav.root:{_menu_condition_signature(root_menu_items)}",
    )
    apply_section_view("view.main")


def animation_menu(params):
    _render_cached_menu_entries(
        _get_cached_menu_entries(
            "nav.animation_menu",
            _animation_menu_entries,
        )
    )
    end_of_directory()
    apply_section_view("view.main")


def animation_item(params):
    mode = params.get("mode")
    _render_cached_menu_entries(
        _get_cached_menu_entries(
            f"nav.animation_item:{mode}",
            _animation_item_menu_entries,
            mode,
        )
    )
    end_of_directory()
    if mode == "tv":
        apply_section_view("view.tvshows")
    else:
        apply_section_view("view.movies")


def telegram_menu(params):
    set_pluging_category(translation(90013))
    add_directory_items_batch(
        [
            (build_url("search_direct", mode="direct"), build_list_item(translation(90006), "search.png"), True),
            (build_url("list_jackgram_latest_movies", page=1), build_list_item(translation(90369), "movies.png"), True),
            (build_url("list_jackgram_latest_series", page=1), build_list_item(translation(90370), "tv.png"), True),
            (build_url("list_jackgram_raw_files", page=1), build_list_item(translation(90371), "cloud.png"), True),
        ]
    )
    end_of_directory()
    apply_section_view("view.main")


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
        _render_cached_menu_entries(
            _get_cached_menu_entries(
                "nav.tv_items:default",
                _tv_menu_entries,
            )
        )
    list_stremio_catalogs(menu_type="series", sub_menu_type="series")
    end_of_directory()
    apply_section_view("view.main")


def movies_items(params):
    set_pluging_category(translation(90008))
    stremio_only = get_setting("stremio_only_catalogs", False)

    if not stremio_only:
        _render_cached_menu_entries(
            _get_cached_menu_entries(
                "nav.movie_items:default",
                _movie_menu_entries,
            )
        )
    list_stremio_catalogs(menu_type="movie", sub_menu_type="movie")
    end_of_directory()
    apply_section_view("view.main")


def direct_menu(params):
    search_direct({"mode": "direct"})


def trakt_group_menu(params):
    mode = params["mode"]
    group = params["group"]

    def _group_items(items):
        return [
            {
                "name": item["name"],
                "icon": item["icon"],
                "action": "search_item",
                "params": {
                    "mode": item["mode"],
                    "submode": item.get("submode", ""),
                    "query": item["query"],
                    "api": item["api"],
                },
            }
            for item in items
        ]

    if mode == "tv" and group == "library":
        set_pluging_category(translation(90292))
        render_menu(_group_items(trakt_tv_library_items), cache=False)
        apply_section_view("view.tvshows")
        return

    if mode == "tv" and group == "discovery":
        set_pluging_category(translation(90293))
        render_menu(_group_items(trakt_tv_discovery_items), cache=False)
        apply_section_view("view.tvshows")
        return

    if mode == "movies" and group == "library":
        set_pluging_category(translation(90292))
        render_menu(_group_items(trakt_movie_library_items), cache=False)
        apply_section_view("view.movies")
        return

    if mode == "movies" and group == "discovery":
        set_pluging_category(translation(90293))
        render_menu(_group_items(trakt_movie_discovery_items), cache=False)
        apply_section_view("view.movies")
        return

    end_of_directory(cache=False)


def search_menu(params):
    set_pluging_category(translation(90006))
    directory_items = []

    directory_items.append(
        (build_url("handle_tmdb_search", mode="multi", page=1), build_list_item(translation(90207), "search.png"), True)
    )

    # -- Direct Search --
    directory_items.append(
        (build_url("search_direct", mode="direct"), build_list_item(translation(90011), "search.png"), True)
    )

    # -- Keyword Search --
    directory_items.append(
        (build_url("handle_keyword_search", mode="multi"), build_list_item(translation(90368), "tmdb.png"), True)
    )

    # -- Recent TMDb Searches --
    tmdb_history = cache.get_list(key="multi")
    if tmdb_history:
        header = make_list_item(label=f"[B][COLOR gray]— {translation(90208)} —[/COLOR][/B]")
        header.setProperty("IsPlayable", "false")
        directory_items.append(("", header, False))

        for _, text in tmdb_history[:5]:
            list_item = make_list_item(label=f"[I]{text}[/I]")
            list_item.setArt(
                {"icon": os.path.join(ADDON_PATH, "resources", "img", "tmdb.png")}
            )
            list_item.setProperty("IsPlayable", "false")
            directory_items.append((build_url("handle_tmdb_search", mode="multi", page=1, query=text), list_item, True))

    # -- Recent Direct Searches --
    direct_history = cache.get_list(key="direct")
    if direct_history:
        header = make_list_item(label=f"[B][COLOR gray]— {translation(90209)} —[/COLOR][/B]")
        header.setProperty("IsPlayable", "false")
        directory_items.append(("", header, False))

        for mode, text in direct_history[:5]:
            list_item = make_list_item(label=f"[I]{text}[/I]")
            list_item.setArt(
                {"icon": os.path.join(ADDON_PATH, "resources", "img", "search.png")}
            )
            list_item.setProperty("IsPlayable", "true")
            directory_items.append((build_url("search", mode=mode, query=text, direct=True), list_item, False))

    # -- Clear All Search History --
    if tmdb_history or direct_history:
        clear_li = make_list_item(label=translation(90210))
        clear_li.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "clear.png")}
        )
        directory_items.append((build_url("clear_search_history"), clear_li, False))

    add_directory_items_batch(directory_items)
    end_of_directory()
    apply_section_view("view.main")


def anime_menu(params):
    set_pluging_category(translation(90009))
    _render_cached_menu_entries(
        _get_cached_menu_entries(
            "nav.anime_menu",
            _anime_menu_entries,
        )
    )
    end_of_directory()
    apply_section_view("view.main")


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


def clear_library(params):
    return library_history_navigation.clear_library(params)


def add_to_library(params):
    return library_history_navigation.add_to_library(params)


def anime_item(params):
    set_pluging_category(translation(90009))
    mode = params.get("mode")
    stremio_only = get_setting("stremio_only_catalogs", False)

    if mode == "tv":
        if not stremio_only:
            _render_cached_menu_entries(
                _get_cached_menu_entries(
                    "nav.anime_item:tv",
                    _anime_item_menu_entries,
                    mode,
                )
            )
        list_stremio_catalogs(menu_type="anime", sub_menu_type="series")
    if mode == "movies":
        if not stremio_only:
            _render_cached_menu_entries(
                _get_cached_menu_entries(
                    "nav.anime_item:movies",
                    _anime_item_menu_entries,
                    mode,
                )
            )
        list_stremio_catalogs(menu_type="anime", sub_menu_type="movie")
    end_of_directory()
    apply_section_view("view.main")


def tv_menu(params):
    set_pluging_category(translation(90010))
    list_stremio_catalogs(menu_type="tv")
    end_of_directory()
    apply_section_view("view.main")


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


def get_tb_downloads(params):
    return debrid_navigation.get_tb_downloads(params)


def torrents(params):
    if not JACKTORR_ADDON:
        notification(translation(30253))
        end_of_directory(cache=False)
        return

    set_pluging_category(translation(90012))

    for torrent in get_torrserver_api().torrents():
        info_hash = torrent.get("hash")

        context_menu_items = [(translation(30700), play_info_hash(info_hash))]

        # Build meta for subtitle download from local cache
        parsed_data = {}
        if info_hash:
            from lib.utils.torrent.torrserver_utils import get_torrent_meta
            parsed_data = get_torrent_meta(info_hash)

        parsed_ids = parsed_data.get("ids", {}) if isinstance(parsed_data.get("ids", {}), dict) else {}
        meta = {
            "title": parsed_data.get("title") or torrent.get("title", ""),
            "mode": parsed_data.get("mode", ""),
            "ids": {
                "tmdb_id": parsed_ids.get("tmdb_id", ""),
                "tvdb_id": parsed_ids.get("tvdb_id", ""),
                "imdb_id": parsed_ids.get("imdb_id"),
                "original_id": parsed_ids.get("original_id", ""),
            },
            "tv_data": parsed_data.get("tv_data", {}),
        }
        context_menu_items.append(
            (
                translation(90082),
                action_url_run(
                    "download_torrent_subtitles",
                    hash=info_hash,
                    meta=json.dumps(meta),
                ),
            )
        )

        if torrent.get("stat") not in [0, 4, 8]:
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

        torrent_li = build_list_item(torrent.get("title", ""), "magnet.png")
        torrent_li.addContextMenuItems(context_menu_items)
        addDirectoryItem(
            ADDON_HANDLE,
            build_url("torrent_files", info_hash=info_hash),
            torrent_li,
            isFolder=True,
        )
    end_of_directory()
    apply_section_view("view.downloads", content_type="files")


def play_media(params):
    data = json.loads(params["data"])
    data = resolve_playback_url(data)
    if not data:
        notification("Failed to resolve playback URL")
        return
    player = JacktookPLayer()
    player.run(data=data)
    del player


def play_autoscraped(params):
    from lib.utils.player.utils import get_autoscrape_cache_key

    ids = json.loads(params.get("ids", "{}"))
    tv_data = json.loads(params.get("tv_data", "{}"))

    id_value = ids.get("original_id") or ids.get("imdb_id") or ids.get("tmdb_id")
    season = tv_data.get("season")
    episode = tv_data.get("episode")

    if id_value is not None and season is not None and episode is not None:
        cache_key = get_autoscrape_cache_key(id_value, season, episode)
        cached_data = cache.get(cache_key)
        if cached_data:
            player = JacktookPLayer()
            player.run(data=cached_data)
            del player
            return

    from lib.search import run_search_entry

    run_search_entry(params)


def play_url(params):
    url = params.get("url")
    list_item = ListItem(label=params.get("name"), path=url)
    list_item.setPath(url)
    setResolvedUrl(ADDON_HANDLE, True, list_item)


def play_trailer(params):
    ids = json.loads(params.get("ids", "{}")) if params.get("ids") else {}
    media_type = params.get("media_type") or params.get("mode")
    tmdb_id = params.get("tmdb_id") or ids.get("tmdb_id")
    yt_id = params.get("yt_id") or ids.get("trailer_yt_id") or ids.get("yt_id")
    youtube_url = params.get("youtube_url") or ids.get("trailer_url") or ids.get("youtube_url")
    title = params.get("title") or ids.get("title") or ids.get("name")

    kodilog(
        f"Trailer: resolving title={title!r} media_type={media_type!r} tmdb_id={tmdb_id!r} yt_id={yt_id!r} youtube_url={youtube_url!r}"
    )
    resolved = resolve_item_trailer(
        yt_id=yt_id,
        youtube_url=youtube_url,
        tmdb_id=tmdb_id,
        media_type=media_type,
    )
    playback = (resolved or {}).get("playback") or {}
    trailer = (resolved or {}).get("trailer") or {}
    video_url = playback.get("video_url") if playback else None
    if not video_url:
        fallback_yt_id = extract_video_id(
            trailer.get("yt_id") or trailer.get("youtube_url") or yt_id or youtube_url
        )
        kodilog(
            f"Trailer: fallback attempt title={title!r} media_type={media_type!r} tmdb_id={tmdb_id!r} fallback_yt_id={fallback_yt_id!r}"
        )
        addon_available = False
        if fallback_yt_id:
            addon_available = is_youtube_addon_enabled()
        if fallback_yt_id and addon_available:
            execute_builtin(
                f"PlayMedia(plugin://plugin.video.youtube/play/?video_id={fallback_yt_id})"
            )
            return
        if fallback_yt_id and not addon_available:
            kodilog(
                f"Trailer: youtube addon unavailable title={title!r} media_type={media_type!r} tmdb_id={tmdb_id!r} fallback_yt_id={fallback_yt_id!r}"
            )
        kodilog(
            f"Trailer: unavailable title={title!r} media_type={media_type!r} tmdb_id={tmdb_id!r} yt_id={yt_id!r} youtube_url={youtube_url!r}"
        )
        notification(translation(90673))
        return

    kodilog(
        f"Trailer: resolved title={title!r} source_type={playback.get('source_type')!r} video_url={video_url!r}"
    )
    list_item = ListItem(label=title, path=video_url)
    list_item.setPath(video_url)
    list_item.setProperty("IsPlayable", "true")
    if playback.get("source_type") == "adaptive" and playback.get("audio_url"):
        list_item.setProperty("inputstream.adaptive.manifest_type", "mpd")
    setResolvedUrl(ADDON_HANDLE, True, list_item)


def play_from_pack(params):
    data = json.loads(params.get("data"))
    data = resolve_playback_url(data)
    if not data:
        return
    list_item = make_listing(data)
    setResolvedUrl(ADDON_HANDLE, True, list_item)


def people_menu(mode):
    set_pluging_category(translation(90078))
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
    apply_section_view("view.main")


def mdblist_menu(mode):
    set_pluging_category(translation(90372))
    addDirectoryItem(
        ADDON_HANDLE,
        build_url(
            "search_mdbd_lists",
            mode=mode,
            page=1,
        ),
        build_list_item(translation(90076), "search.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url(
            "top_mdbd_lists",
            mode=mode,
            page=1,
        ),
        build_list_item(translation(90074), "mdblist.png"),
        isFolder=True,
    )
    addDirectoryItem(
        ADDON_HANDLE,
        build_url(
            "user_mdbd_lists",
            mode=mode,
            page=1,
        ),
        build_list_item(translation(90075), "mdblist.png"),
        isFolder=True,
    )
    end_of_directory()
    apply_section_view("view.main")


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
        dialog_text(translation(90577), file=CHANGELOG_PATH)


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
    finish_action()
    addon_settings()
    clear_cached_settings()


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


def pm_remove_auth(params):
    return debrid_navigation.pm_remove_auth(params)


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
