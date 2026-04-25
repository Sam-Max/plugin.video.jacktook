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
        "get_tb_downloads",
        "cloud",
        "cloud_details",
        "pm_auth",
        "pm_remove_auth",
        "tb_auth",
        "tb_remove_auth",
        "torbox_info",
        "easynews_info",
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
        "handle_download_file",
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
        "extras",
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


def _is_stremio_action(action):
    return action.startswith(("stremio_", "list_stremio")) or action in {
        "clear_stremio_search_history",
        "list_catalog",
        "search_catalog",
        "add_custom_stremio_addon",
        "remove_custom_stremio_addon",
        "torrentio_toggle_providers",
        "stremio_bypass_addons_select",
    }


def _is_tmdb_action(action):
    return action in ("tmdb_search_modes", "tmdb_episode_search_modes") or action.startswith(
        (
            "handle_tmdb",
            "search_tmdb",
            "search_tmbd",
            "rescrape_tmdb",
            "show_tmdb",
            "handle_collection",
            "search_people",
            "handle_keyword",
            "show_keyword",
        )
    )


def _is_trakt_action(action):
    return action.startswith("trakt_") or action in _TRAKT_EXTRAS


def _is_debrid_action(action):
    return action in _DEBRID_ACTIONS


def _is_telegram_action(action):
    return action.startswith(("telegram_", "list_telegram", "list_jackgram"))


def _is_torrserver_action(action):
    return action in _TORRSERVER_ACTIONS


def _is_webdav_action(action):
    return action in _WEBDAV_ACTIONS


def _is_download_action(action):
    return action in _DOWNLOAD_ACTIONS


def _is_mdblist_action(action):
    return action in _MDBLIST_ACTIONS


def _is_cache_action(action):
    return action.startswith("clear_")


def _is_gui_action(action):
    return action in _GUI_ACTIONS


def _is_source_manager_action(action):
    return action == "source_manager_toggle"


def _get_route_handler(action):
    for matcher, handler in ROUTE_GROUPS:
        if matcher(action):
            return handler
    return _route_core


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

        route_handler = _get_route_handler(action)
        route_handler(action, params)
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
        "stremio_bypass_addons_select",
    ):
        from lib.clients.stremio.addon_selection import (
            stremio_toggle_addons,
            stremio_toggle_catalogs,
            stremio_toggle_tv_addons,
            stremio_filtered_selection,
            add_custom_stremio_addon,
            remove_custom_stremio_addon,
            stremio_bypass_addons_select,
        )

        actions = {
            "stremio_toggle_addons": stremio_toggle_addons,
            "stremio_toggle_catalogs": stremio_toggle_catalogs,
            "stremio_toggle_tv_addons": stremio_toggle_tv_addons,
            "stremio_filtered_selection": stremio_filtered_selection,
            "add_custom_stremio_addon": add_custom_stremio_addon,
            "remove_custom_stremio_addon": remove_custom_stremio_addon,
            "stremio_bypass_addons_select": stremio_bypass_addons_select,
        }
        actions[action](params)
    elif action == "stremio_manage_phone":
        from lib.clients.stremio.manage_phone import stremio_manage_phone

        stremio_manage_phone(params)
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
            clear_stremio_search_history,
            list_catalog,
            list_stremio_episodes,
            list_stremio_movie,
            list_stremio_seasons,
            list_stremio_tv,
            list_stremio_tv_streams,
            search_catalog,
        )

        actions = {
            "clear_stremio_search_history": clear_stremio_search_history,
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
    elif action in (
        "search_people_by_id",
        "handle_tmdb_person_details",
        "handle_tmdb_person_info",
    ):
        from lib.clients.tmdb.people_client import PeopleClient

        actions = {
            "search_people_by_id": PeopleClient.search_people_by_id,
            "handle_tmdb_person_details": PeopleClient.handle_tmdb_person_details,
            "handle_tmdb_person_info": PeopleClient.handle_tmdb_person_info,
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
            "tmdb_search_modes": TmdbClient.tmdb_search_modes,
            "tmdb_episode_search_modes": TmdbClient.tmdb_episode_search_modes,
            "rescrape_tmdb_media": TmdbClient.rescrape_tmdb_media,
            "show_tmdb_item": TmdbClient.show_tmdb_item,
            "handle_collection_query": TmdbClient.handle_collection_query,
            "handle_keyword_search": TmdbClient.handle_keyword_search,
            "show_keyword_results": TmdbClient.show_keyword_results,
        }
        action_func = actions.get(action)
        if action_func:
            action_func(params)


def _route_trakt(action, params):
    if action in (
        "trakt_add_to_watchlist",
        "trakt_remove_from_watchlist",
        "trakt_add_to_favorites",
        "trakt_remove_from_favorites",
        "trakt_mark_as_watched",
        "trakt_mark_as_unwatched",
        "add_to_collection",
        "remove_from_collection",
        "trakt_create_list",
        "trakt_delete_list",
        "trakt_like_list",
        "trakt_unlike_list",
        "trakt_add_item_to_list",
        "trakt_remove_item_from_list",
    ):
        from lib.clients.trakt.trakt import TraktClient

        actions = {
            "trakt_add_to_watchlist": TraktClient.trakt_add_to_watchlist,
            "trakt_remove_from_watchlist": TraktClient.trakt_remove_from_watchlist,
            "trakt_add_to_favorites": TraktClient.trakt_add_to_favorites,
            "trakt_remove_from_favorites": TraktClient.trakt_remove_from_favorites,
            "trakt_mark_as_watched": TraktClient.trakt_mark_as_watched,
            "trakt_mark_as_unwatched": TraktClient.trakt_mark_as_unwatched,
            "add_to_collection": TraktClient.trakt_add_to_collection,
            "remove_from_collection": TraktClient.trakt_remove_from_collection,
            "trakt_create_list": TraktClient.trakt_create_list,
            "trakt_delete_list": TraktClient.trakt_delete_list,
            "trakt_like_list": TraktClient.trakt_like_list,
            "trakt_unlike_list": TraktClient.trakt_unlike_list,
            "trakt_add_item_to_list": TraktClient.trakt_add_item_to_list,
            "trakt_remove_item_from_list": TraktClient.trakt_remove_item_from_list,
        }
        actions[action](params)
    else:
        from lib.navigation import (
            trakt_auth,
            trakt_auth_revoke,
            trakt_group_menu,
            trakt_list_content,
            list_trakt_page,
        )

        actions = {
            "trakt_auth": trakt_auth,
            "trakt_auth_revoke": trakt_auth_revoke,
            "trakt_group_menu": trakt_group_menu,
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
        get_tb_downloads,
        cloud,
        cloud_details,
        pm_auth,
        pm_remove_auth,
        tb_auth,
        tb_remove_auth,
        torbox_info,
        easynews_info,
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
        "get_tb_downloads": get_tb_downloads,
        "cloud": cloud,
        "cloud_details": cloud_details,
        "pm_auth": pm_auth,
        "pm_remove_auth": pm_remove_auth,
        "tb_auth": tb_auth,
        "tb_remove_auth": tb_remove_auth,
        "torbox_info": torbox_info,
        "easynews_info": easynews_info,
    }
    actions[action](params)


def _route_telegram(action, params):
    if action == "telegram_menu":
        from lib.navigation import telegram_menu

        telegram_menu(params)
    else:
        from lib.clients.jackgram.utils import (
            list_jackgram_raw_files,
            list_jackgram_latest_movies,
            list_jackgram_latest_series,
            list_jackgram_title_sources,
        )

        actions = {
            "list_jackgram_raw_files": list_jackgram_raw_files,
            "list_jackgram_latest_movies": list_jackgram_latest_movies,
            "list_jackgram_latest_series": list_jackgram_latest_series,
            "list_jackgram_title_sources": list_jackgram_title_sources,
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
    if action in (
        "download_video",
        "handle_download_file",
        "handle_cancel_download",
        "handle_delete_file",
    ):
        from lib.downloader import (
            download_video,
            handle_download_file,
            handle_cancel_download,
            handle_delete_file,
        )

        actions = {
            "download_video": download_video,
            "handle_download_file": handle_download_file,
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
        clear_search_history,
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
        "clear_search_history": clear_search_history,
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
    elif action == "extras":
        from lib.gui.extras_window import ExtrasWindow
        from lib.jacktook.utils import ADDON_PATH

        # Load the metadata properties needed by the Extras window
        item_information = {
            "tmdb_id": params.get("id"),
            "imdb_id": params.get("imdb_id"),
            "media_type": params.get("media_type"),
            "title": params.get("title"),
            "plot": params.get("plot", ""),
            "genre": params.get("genre", ""),
            "rating": params.get("rating", ""),
            "tv_data": params.get("tv_data", "{}"),
        }
        xml_file = "extras.xml"
        window = ExtrasWindow(xml_file, ADDON_PATH, item_information=item_information)
        window.doModal()
        del window
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


def _route_source_manager(action, params):
    from lib.gui.source_manager_dialog import open_source_manager_dialog

    open_source_manager_dialog()


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
            trakt_group_menu,
            direct_menu,
            search_menu,
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
            play_autoscraped,
            play_from_pack,
            play_trailer,
            play_url,
            settings_menu,
            settings,
            export_settings_backup,
            restore_settings_backup,
            reset_all_settings,
            factory_reset,
            history_menu,
            files_history,
            titles_history,
            titles_calendar,
            library_menu,
            continue_watching_menu,
            library_shows,
            library_movies,
            library_calendar,
            remove_from_library,
            clear_library,
            remove_from_continue_watching,
            add_to_library,
            donate,
            addon_update,
            downgrade_addon,
            show_changelog,
            open_burst_config,
            kodi_logs,
            easynews_info,
            choose_view,
            save_view,
            reset_views,
            views_menu,
        )

        actions = {
            "tv_shows_items": tv_shows_items,
            "movies_items": movies_items,
            "trakt_group_menu": trakt_group_menu,
            "direct_menu": direct_menu,
            "search_menu": search_menu,
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
            "play_autoscraped": play_autoscraped,
            "play_from_pack": play_from_pack,
            "play_trailer": play_trailer,
            "play_url": play_url,
            "settings_menu": settings_menu,
            "settings": settings,
            "export_settings_backup": export_settings_backup,
            "restore_settings_backup": restore_settings_backup,
            "reset_all_settings": reset_all_settings,
            "factory_reset": factory_reset,
            "history_menu": history_menu,
            "files_history": files_history,
            "titles_history": titles_history,
            "titles_calendar": titles_calendar,
            "library_menu": library_menu,
            "continue_watching_menu": continue_watching_menu,
            "library_shows": library_shows,
            "library_movies": library_movies,
            "library_calendar": library_calendar,
            "remove_from_library": remove_from_library,
            "clear_library": clear_library,
            "remove_continue_watching": remove_from_continue_watching,
            "add_to_library": add_to_library,
            "donate": donate,
            "addon_update": addon_update,
            "downgrade_addon": downgrade_addon,
            "show_changelog": show_changelog,
            "open_burst_config": open_burst_config,
            "kodi_logs": kodi_logs,
            "easynews_info": easynews_info,
            "choose_view": choose_view,
            "save_view": save_view,
            "reset_views": reset_views,
            "views_menu": views_menu,
        }
        action_func = actions.get(action)
        if action_func:
            action_func(params)


ROUTE_GROUPS = (
    (_is_stremio_action, _route_stremio),
    (_is_tmdb_action, _route_tmdb),
    (_is_trakt_action, _route_trakt),
    (_is_debrid_action, _route_debrid),
    (_is_telegram_action, _route_telegram),
    (_is_torrserver_action, _route_torrserver),
    (_is_webdav_action, _route_webdav),
    (_is_download_action, _route_downloads),
    (_is_mdblist_action, _route_mdblist),
    (_is_cache_action, _route_cache),
    (_is_gui_action, _route_gui),
    (_is_source_manager_action, _route_source_manager),
)
