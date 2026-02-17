# -*- coding: utf-8 -*-
"""
Jacktook addon router — lazy-loading dispatcher.

Uses prefix-based routing with lazy imports to avoid loading all addon
modules on every invocation. Only the modules needed for the current
action are imported.
"""
import sys
from urllib import parse


# ---------------------------------------------------------------------------
# Action sets for set-based lookups
# ---------------------------------------------------------------------------

_TRAKT_EXTRAS = frozenset(
    {
        "add_to_collection",
        "remove_from_collection",
        "list_trakt_page",
    }
)

_DEBRID_ACTIONS = frozenset(
    {
        "rd_auth",
        "rd_remove_auth",
        "ad_auth",
        "ad_remove_auth",
        "real_debrid_info",
        "alldebrid_info",
        "debrider_auth",
        "debrider_remove_auth",
        "debrider_info",
        "get_rd_downloads",
        "cloud",
        "cloud_details",
        "pm_auth",
        "tb_auth",
        "tb_remove_auth",
        "torbox_info",
    }
)

_TORRSERVER_ACTIONS = frozenset(
    {
        "torrents",
        "torrent_action",
        "torrent_files",
        "torrentio_selection",
        "display_picture",
        "display_text",
    }
)

_WEBDAV_ACTIONS = frozenset(
    {
        "list_webdav",
        "webdav_provider_test",
        "display_text_webdav",
        "show_picture_webdav",
    }
)

_DOWNLOAD_ACTIONS = frozenset(
    {
        "download_video",
        "handle_cancel_download",
        "handle_delete_file",
        "downloads_menu",
    }
)

_GUI_ACTIONS = frozenset(
    {
        "run_next_dialog",
        "run_resume_dialog",
        "run_skip_intro_dialog",
        "test_source_select",
        "test_run_next",
        "test_resume_dialog",
        "test_download_dialog",
    }
)

_MDBLIST_ACTIONS = frozenset(
    {
        "search_mdbd_lists",
        "user_mdbd_lists",
        "top_mdbd_lists",
        "show_mdblist_list",
    }
)


# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------


def addon_router():
    param_string = sys.argv[2][1:]

    if param_string:
        params = dict(parse.parse_qsl(param_string))
        action = params.get("action", "")

        from lib.utils.tmdb_init import ensure_tmdb_init

        ensure_tmdb_init()

        # --- Stremio routes ---
        if action.startswith(("stremio_", "list_stremio")) or action in (
            "list_catalog",
            "search_catalog",
            "add_custom_stremio_addon",
            "remove_custom_stremio_addon",
            "torrentio_toggle_providers",
        ):
            _route_stremio(action, params)

        # --- TMDB routes ---
        elif action.startswith(
            (
                "handle_tmdb",
                "search_tmdb",
                "search_tmbd",
                "rescrape_tmdb",
                "show_tmdb",
                "handle_collection",
                "search_people",
            )
        ):
            _route_tmdb(action, params)

        # --- Trakt routes ---
        elif action.startswith("trakt_") or action in _TRAKT_EXTRAS:
            _route_trakt(action, params)

        # --- Debrid / Cloud routes ---
        elif action in _DEBRID_ACTIONS:
            _route_debrid(action, params)

        # --- Telegram routes ---
        elif action.startswith(("telegram_", "list_telegram")):
            _route_telegram(action, params)

        # --- TorrServer routes ---
        elif action in _TORRSERVER_ACTIONS:
            _route_torrserver(action, params)

        # --- WebDAV routes ---
        elif action in _WEBDAV_ACTIONS:
            _route_webdav(action, params)

        # --- Download routes ---
        elif action in _DOWNLOAD_ACTIONS:
            _route_downloads(action, params)

        # --- MDBList routes ---
        elif action in _MDBLIST_ACTIONS:
            _route_mdblist(action, params)

        # --- Cache / Clear routes ---
        elif action.startswith("clear_"):
            _route_cache(action, params)

        # --- GUI / Dialog routes ---
        elif action in _GUI_ACTIONS:
            _route_gui(action, params)

        # --- Core navigation (fallback) ---
        else:
            _route_core(action, params)
        return

    from lib.navigation import root_menu

    root_menu()


# ---------------------------------------------------------------------------
# Route handlers — each lazily imports only the modules it needs
# ---------------------------------------------------------------------------


def _route_stremio(action, params):
    if action in (
        "stremio_toggle_addons",
        "stremio_toggle_catalogs",
        "stremio_toggle_tv_addons",
        "stremio_filtered_selection",
        "add_custom_stremio_addon",
        "remove_custom_stremio_addon",
    ):
        from lib.clients.stremio.addon_selection import (
            stremio_toggle_addons,
            stremio_toggle_catalogs,
            stremio_toggle_tv_addons,
            stremio_filtered_selection,
            add_custom_stremio_addon,
            remove_custom_stremio_addon,
        )

        actions = {
            "stremio_toggle_addons": stremio_toggle_addons,
            "stremio_toggle_catalogs": stremio_toggle_catalogs,
            "stremio_toggle_tv_addons": stremio_toggle_tv_addons,
            "stremio_filtered_selection": stremio_filtered_selection,
            "add_custom_stremio_addon": add_custom_stremio_addon,
            "remove_custom_stremio_addon": remove_custom_stremio_addon,
        }
        actions[action](params)
    elif action in ("stremio_login", "stremio_logout", "stremio_update"):
        from lib.clients.stremio.authentication import (
            stremio_login,
            stremio_logout,
            stremio_update,
        )

        actions = {
            "stremio_login": stremio_login,
            "stremio_logout": stremio_logout,
            "stremio_update": stremio_update,
        }
        actions[action](params)
    elif action == "torrentio_toggle_providers":
        from lib.clients.stremio.torrentio import torrentio_toggle_providers

        torrentio_toggle_providers(params)
    else:
        from lib.clients.stremio.catalog_menus import (
            list_catalog,
            list_stremio_episodes,
            list_stremio_movie,
            list_stremio_seasons,
            list_stremio_tv,
            list_stremio_tv_streams,
            search_catalog,
        )

        actions = {
            "list_catalog": list_catalog,
            "list_stremio_seasons": list_stremio_seasons,
            "list_stremio_episodes": list_stremio_episodes,
            "list_stremio_movie": list_stremio_movie,
            "list_stremio_tv_streams": list_stremio_tv_streams,
            "list_stremio_tv": list_stremio_tv,
            "search_catalog": search_catalog,
        }
        action_func = actions.get(action)
        if action_func:
            action_func(params)


def _route_tmdb(action, params):

    if action in ("search_tmdb_year", "search_tmdb_genres"):
        from lib.clients.tmdb.tmdb import TmdbClient
        from lib.utils.general.utils import set_content_type

        if action == "search_tmdb_year":
            mode = params["mode"]
            set_content_type(mode)
            TmdbClient.tmdb_search_year(
                mode, params["submode"], int(params["year"]), int(params["page"])
            )
        else:
            mode = params["mode"]
            set_content_type(mode)
            TmdbClient.tmdb_search_genres(
                mode,
                params["genre_id"],
                int(params["page"]),
                submode=params.get("submode"),
            )
    elif action in ("search_people_by_id", "handle_tmdb_person_details"):
        from lib.clients.tmdb.people_client import PeopleClient

        actions = {
            "search_people_by_id": PeopleClient.search_people_by_id,
            "handle_tmdb_person_details": PeopleClient.handle_tmdb_person_details,
        }
        actions[action](params)
    elif action == "handle_collection_details":
        from lib.clients.tmdb.collections import TmdbCollections

        TmdbCollections.add_collection_details(params)
    else:
        from lib.clients.tmdb.tmdb import TmdbClient

        actions = {
            "handle_tmdb_search": TmdbClient.handle_tmdb_search,
            "handle_tmdb_query": TmdbClient.handle_tmdb_query,
            "search_tmdb_lang": TmdbClient.show_lang_items,
            "search_tmbd_network": TmdbClient.show_network_items,
            "search_tmdb_recommendations": TmdbClient.search_tmdb_recommendations,
            "search_tmdb_similar": TmdbClient.search_tmdb_similar,
            "rescrape_tmdb_media": TmdbClient.rescrape_tmdb_media,
            "show_tmdb_item": TmdbClient.show_tmdb_item,
            "handle_collection_query": TmdbClient.handle_collection_query,
        }
        action_func = actions.get(action)
        if action_func:
            action_func(params)


def _route_trakt(action, params):
    if action in (
        "trakt_add_to_watchlist",
        "trakt_remove_from_watchlist",
        "trakt_mark_as_watched",
        "trakt_mark_as_unwatched",
        "add_to_collection",
        "remove_from_collection",
    ):
        from lib.clients.trakt.trakt import TraktClient

        actions = {
            "trakt_add_to_watchlist": TraktClient.trakt_add_to_watchlist,
            "trakt_remove_from_watchlist": TraktClient.trakt_remove_from_watchlist,
            "trakt_mark_as_watched": TraktClient.trakt_mark_as_watched,
            "trakt_mark_as_unwatched": TraktClient.trakt_mark_as_unwatched,
            "add_to_collection": TraktClient.trakt_add_to_collection,
            "remove_from_collection": TraktClient.trakt_remove_from_collection,
        }
        actions[action](params)
    else:
        from lib.navigation import (
            trakt_auth,
            trakt_auth_revoke,
            trakt_list_content,
            list_trakt_page,
        )

        actions = {
            "trakt_auth": trakt_auth,
            "trakt_auth_revoke": trakt_auth_revoke,
            "trakt_list_content": trakt_list_content,
            "list_trakt_page": list_trakt_page,
        }
        action_func = actions.get(action)
        if action_func:
            action_func(params)


def _route_debrid(action, params):
    from lib.navigation import (
        rd_auth,
        rd_remove_auth,
        ad_auth,
        ad_remove_auth,
        real_debrid_info,
        alldebrid_info,
        debrider_auth,
        debrider_remove_auth,
        debrider_info,
        get_rd_downloads,
        cloud,
        cloud_details,
        pm_auth,
        tb_auth,
        tb_remove_auth,
        torbox_info,
    )

    actions = {
        "rd_auth": rd_auth,
        "rd_remove_auth": rd_remove_auth,
        "ad_auth": ad_auth,
        "ad_remove_auth": ad_remove_auth,
        "real_debrid_info": real_debrid_info,
        "alldebrid_info": alldebrid_info,
        "debrider_auth": debrider_auth,
        "debrider_remove_auth": debrider_remove_auth,
        "debrider_info": debrider_info,
        "get_rd_downloads": get_rd_downloads,
        "cloud": cloud,
        "cloud_details": cloud_details,
        "pm_auth": pm_auth,
        "tb_auth": tb_auth,
        "tb_remove_auth": tb_remove_auth,
        "torbox_info": torbox_info,
    }
    actions[action](params)


def _route_telegram(action, params):
    if action == "telegram_menu":
        from lib.navigation import telegram_menu

        telegram_menu(params)
    else:
        from lib.clients.jackgram.utils import (
            list_telegram_files,
            list_telegram_latest,
            list_telegram_latest_files,
        )

        actions = {
            "list_telegram_files": list_telegram_files,
            "list_telegram_latest": list_telegram_latest,
            "list_telegram_latest_files": list_telegram_latest_files,
        }
        action_func = actions.get(action)
        if action_func:
            action_func(params)


def _route_torrserver(action, params):
    if action in ("torrent_action", "torrent_files", "display_picture", "display_text"):
        from lib.utils.torrent.torrserver_utils import (
            torrent_action,
            torrent_files,
            display_picture,
            display_text,
        )

        actions = {
            "torrent_action": torrent_action,
            "torrent_files": torrent_files,
            "display_picture": display_picture,
            "display_text": display_text,
        }
        actions[action](params)
    elif action == "torrents":
        from lib.navigation import torrents

        torrents(params)
    elif action == "torrentio_selection":
        from lib.navigation import torrentio_selection

        torrentio_selection(params)


def _route_webdav(action, params):
    from lib.clients.webdav.client import (
        list_webdav,
        webdav_provider_test,
        display_text_webdav,
        show_picture_webdav,
    )

    actions = {
        "list_webdav": list_webdav,
        "webdav_provider_test": webdav_provider_test,
        "display_text_webdav": display_text_webdav,
        "show_picture_webdav": show_picture_webdav,
    }
    actions[action](params)


def _route_downloads(action, params):
    if action in ("download_video", "handle_cancel_download", "handle_delete_file"):
        from lib.downloader import (
            download_video,
            handle_cancel_download,
            handle_delete_file,
        )

        actions = {
            "download_video": download_video,
            "handle_cancel_download": handle_cancel_download,
            "handle_delete_file": handle_delete_file,
        }
        actions[action](params)
    elif action == "downloads_menu":
        from lib.navigation import downloads_menu

        downloads_menu(params)


def _route_mdblist(action, params):
    from lib.clients.mdblist.mdblist import (
        search_mdbd_lists,
        show_mdblist_list,
        top_mdbd_lists,
        user_mdbd_lists,
    )

    actions = {
        "search_mdbd_lists": search_mdbd_lists,
        "user_mdbd_lists": user_mdbd_lists,
        "top_mdbd_lists": top_mdbd_lists,
        "show_mdblist_list": show_mdblist_list,
    }
    actions[action](params)


def _route_cache(action, params):
    from lib.navigation import (
        clear_all_cached,
        clear_trakt_cache,
        clear_tmdb_cache,
        clear_stremio_cache,
        clear_debrid_cache,
        clear_mdblist_cache,
        clear_database_cache,
        clear_history,
    )

    actions = {
        "clear_all_cached": clear_all_cached,
        "clear_trakt_cache": clear_trakt_cache,
        "clear_tmdb_cache": clear_tmdb_cache,
        "clear_stremio_cache": clear_stremio_cache,
        "clear_debrid_cache": clear_debrid_cache,
        "clear_mdblist_cache": clear_mdblist_cache,
        "clear_database_cache": clear_database_cache,
        "clear_history": clear_history,
    }
    action_func = actions.get(action)
    if action_func:
        action_func(params)


def _route_gui(action, params):
    if action in ("run_next_dialog", "run_resume_dialog", "run_skip_intro_dialog"):
        from lib.gui.custom_dialogs import (
            run_next_dialog,
            run_resume_dialog,
            run_skip_intro_dialog,
        )

        actions = {
            "run_next_dialog": run_next_dialog,
            "run_resume_dialog": run_resume_dialog,
            "run_skip_intro_dialog": run_skip_intro_dialog,
        }
        actions[action](params)
    else:
        from lib.navigation import (
            test_source_select,
            test_run_next,
            test_resume_dialog,
            test_download_dialog,
        )

        actions = {
            "test_source_select": test_source_select,
            "test_run_next": test_run_next,
            "test_resume_dialog": test_resume_dialog,
            "test_download_dialog": test_download_dialog,
        }
        action_func = actions.get(action)
        if action_func:
            action_func(params)


def _route_core(action, params):
    if action in ("resolve_for_pack_selection", "resolve_for_subtitles"):
        from lib.actions import resolve_for_pack_selection, resolve_for_subtitles

        actions = {
            "resolve_for_pack_selection": resolve_for_pack_selection,
            "resolve_for_subtitles": resolve_for_subtitles,
        }
        actions[action](params)
    elif action in ("show_episodes_details", "show_seasons_details"):
        from lib.utils.views.shows import (
            show_episodes_details,
            show_seasons_details,
        )

        actions = {
            "show_episodes_details": show_episodes_details,
            "show_seasons_details": show_seasons_details,
        }
        actions[action](params)
    elif action == "delete_last_title_entry":
        from lib.utils.views.last_titles import delete_last_title_entry

        delete_last_title_entry(params)
    else:
        from lib.navigation import (
            tv_shows_items,
            movies_items,
            direct_menu,
            anime_menu,
            anime_item,
            anime_search,
            animation_menu,
            animation_item,
            tv_menu,
            search,
            search_direct,
            search_item,
            next_page_anime,
            play_media,
            play_from_pack,
            play_url,
            settings,
            history_menu,
            files_history,
            titles_history,
            titles_calendar,
            donate,
            addon_update,
            show_changelog,
            open_burst_config,
            kodi_logs,
        )

        actions = {
            "tv_shows_items": tv_shows_items,
            "movies_items": movies_items,
            "direct_menu": direct_menu,
            "anime_menu": anime_menu,
            "anime_item": anime_item,
            "anime_search": anime_search,
            "animation_menu": animation_menu,
            "animation_item": animation_item,
            "tv_menu": tv_menu,
            "search": search,
            "search_direct": search_direct,
            "search_item": search_item,
            "next_page_anime": next_page_anime,
            "play_media": play_media,
            "play_from_pack": play_from_pack,
            "play_url": play_url,
            "settings": settings,
            "history_menu": history_menu,
            "files_history": files_history,
            "titles_history": titles_history,
            "titles_calendar": titles_calendar,
            "donate": donate,
            "addon_update": addon_update,
            "show_changelog": show_changelog,
            "open_burst_config": open_burst_config,
            "kodi_logs": kodi_logs,
        }
        action_func = actions.get(action)
        if action_func:
            action_func(params)
