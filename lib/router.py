import sys
from urllib import parse

from lib.clients.jackgram.utils import (
    get_telegram_files,
    get_telegram_latest,
    get_telegram_latest_files,
)

from lib.clients.tmdb.tmdb import TmdbClient
from lib.clients.trakt.trakt import TraktClient
from lib.downloader import (
    handle_cancel_download,
    handle_delete_file,
    handle_download_file,
)
from lib.gui.custom_dialogs import run_next_dialog, run_resume_dialog
from lib.navigation import (
    addon_update,
    animation_item,
    animation_menu,
    anime_item,
    anime_menu,
    anime_search,
    clear_all_cached,
    clear_history,
    cloud,
    cloud_details,
    direct_menu,
    donate,
    ed_info,
    downloads_menu,
    files_history,
    get_rd_downloads,
    history_menu,
    list_trakt_page,
    movies_items,
    next_page_anime,
    open_burst_config,
    play_from_pack,
    play_url,
    pm_auth,
    rd_info,
    search_tmdb_genres,
    search_tmdb_year,
    telegram_menu,
    test_download_dialog,
    test_resume_dialog,
    test_run_next,
    test_source_select,
    titles_history,
    torrentio_selection,
    play_torrent,
    rd_auth,
    rd_remove_auth,
    root_menu,
    search,
    search_direct,
    search_item,
    settings,
    torrents,
    trakt_auth,
    trakt_auth_revoke,
    trakt_list_content,
    tv_episodes_details,
    tv_menu,
    tv_seasons_details,
    tv_shows_items,
)
from lib.clients.stremio.catalogs import (
    list_stremio_catalog,
    list_stremio_episodes,
    list_stremio_seasons,
    list_stremio_tv,
    list_stremio_tv_streams,
    search_catalog,
)
from lib.utils.kodi.utils import kodilog
from lib.utils.torrent.torrserver_utils import (
    display_picture,
    display_text,
    torrent_action,
    torrent_files,
)
from lib.clients.stremio.ui import (
    stremio_login,
    stremio_toggle_addons,
    stremio_logout,
    stremio_toggle_catalogs,
    stremio_update,
)

import xbmc


def addon_router():
    param_string = sys.argv[2][1:]
    actions = {
        "run_next_dialog": run_next_dialog,
        "run_resume_dialog": run_resume_dialog,
        "tv_shows_items": tv_shows_items,
        "tv_seasons_details": tv_seasons_details,
        "tv_episodes_details": tv_episodes_details,
        "movies_items": movies_items,
        "direct_menu": direct_menu,
        "anime_menu": anime_menu,
        "anime_item": anime_item,
        "anime_search": anime_search,
        "search": search,
        "handle_tmdb_search": TmdbClient.handle_tmdb_search,
        "search_tmdb_year": search_tmdb_year,
        "search_tmdb_genres": search_tmdb_genres,
        "handle_tmdb_query": TmdbClient.handle_tmdb_query,
        "search_direct": search_direct,
        "download_file": handle_download_file,
        "search_item": search_item,
        "next_page_anime": next_page_anime,
        "play_torrent": play_torrent,
        "play_from_pack": play_from_pack,
        "play_url": play_url,
        "trakt_list_content": trakt_list_content,
        "list_trakt_page": list_trakt_page,
        "cloud": cloud,
        "cloud_details": cloud_details,
        "settings": settings,
        "files_history": files_history,
        "titles_history": titles_history,
        "history_menu": history_menu,
        "donate": donate,
        "delete_file": handle_delete_file,
        "clear_all_cached": clear_all_cached,
        "clear_history": clear_history,
        "cancel_download": handle_cancel_download,
        "addon_update": addon_update,
        "open_burst_config": open_burst_config,
        "rd_auth": rd_auth,
        "rd_remove_auth": rd_remove_auth,
        "rd_info": rd_info,
        "ed_info": ed_info,
        "get_rd_downloads": get_rd_downloads,
        "trakt_auth": trakt_auth,
        "trakt_auth_revoke": trakt_auth_revoke,
        "trakt_add_to_watchlist": TraktClient.trakt_add_to_watchlist,
        "trakt_remove_from_watchlist": TraktClient.trakt_remove_from_watchlist,
        "trakt_mark_as_watched": TraktClient.trakt_mark_as_watched,
        "trakt_mark_as_unwatched": TraktClient.trakt_mark_as_unwatched,
        "pm_auth": pm_auth,
        "torrents": torrents,
        "torrent_action": torrent_action,
        "torrent_files": torrent_files,
        "torrentio_selection": torrentio_selection,
        "get_telegram_files": get_telegram_files,
        "get_telegram_latest": get_telegram_latest,
        "get_telegram_latest_files": get_telegram_latest_files,
        "telegram_menu": telegram_menu,
        "display_picture": display_picture,
        "display_text": display_text,
        "downloads_menu": downloads_menu,
        "test_source_select": test_source_select,
        "test_run_next": test_run_next,
        "test_resume_dialog": test_resume_dialog,
        "test_download_dialog": test_download_dialog,
        "animation_menu": animation_menu,
        "animation_item": animation_item,
        "stremio_toggle_addons": stremio_toggle_addons,
        "stremio_toggle_catalogs": stremio_toggle_catalogs,
        "list_stremio_catalog": list_stremio_catalog,
        "list_stremio_seasons": list_stremio_seasons,
        "list_stremio_episodes": list_stremio_episodes,
        "list_stremio_tv_streams": list_stremio_tv_streams,
        "list_stremio_tv": list_stremio_tv,
        "search_catalog": search_catalog,
        "tv_menu": tv_menu,
        "stremio_login": stremio_login,
        "stremio_logout": stremio_logout,
        "stremio_update": stremio_update,
    }

    if param_string:
        kodilog(f"Param string: {param_string}", level=xbmc.LOGDEBUG)
        params = dict(parse.parse_qsl(param_string))
        kodilog(f"Parsed params: {params}", level=xbmc.LOGDEBUG)
        action = params.get("action")
        action_func = actions.get(action)
        if action_func:
            action_func(params)
            return

    root_menu()
