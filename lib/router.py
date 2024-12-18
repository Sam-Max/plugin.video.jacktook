import sys
from urllib import parse
from lib.api.jacktook.kodi import kodilog
from lib.navigation import (
    addon_update,
    anime_item,
    anime_menu,
    anime_search,
    clear_all_cached,
    clear_history,
    cloud,
    cloud_details,
    direct_menu,
    donate,
    files,
    get_rd_downloads,
    history,
    list_trakt_page,
    movies_items,
    next_page_anime,
    open_burst_config,
    play_from_pack,
    play_url,
    pm_auth,
    rd_info,
    show_pack_info,
    torrentio_selection,
    play_torrent,
    rd_auth,
    rd_remove_auth,
    root_menu,
    search,
    search_direct,
    search_item,
    search_tmdb,
    settings,
    status,
    titles,
    torrents,
    trakt_auth,
    trakt_auth_revoke,
    trakt_list_content,
    tv_episodes_details,
    tv_seasons_details,
    tv_shows_items,
)
from lib.utils.torrent_utils import (
    display_picture,
    display_text,
    torrent_action,
    torrent_files,
)


def addon_router():
    kodilog("addon_router")
    param_string = sys.argv[2][1:]
    actions = {
        "tv_shows_items": tv_shows_items,
        "tv_seasons_details": tv_seasons_details,
        "tv_episodes_details": tv_episodes_details,
        "movies_items": movies_items,
        "direct_menu": direct_menu,
        "anime_menu": anime_menu,
        "anime_item": anime_item,
        "anime_search": anime_search,
        "search": search,
        "search_tmdb": search_tmdb,
        "search_direct": search_direct,
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
        "status": status,
        "files": files,
        "titles": titles,
        "history": history,
        "donate": donate,
        "clear_all_cached": clear_all_cached,
        "clear_history": clear_history,
        "addon_update": addon_update,
        "open_burst_config": open_burst_config,
        "rd_auth": rd_auth,
        "rd_remove_auth": rd_remove_auth,
        "rd_info": rd_info,
        "get_rd_downloads": get_rd_downloads,
        "trakt_auth": trakt_auth,
        "trakt_auth_revoke": trakt_auth_revoke,
        "pm_auth": pm_auth,
        "torrents": torrents,
        "torrent_action": torrent_action,
        "torrent_files": torrent_files,
        "torrentio_selection": torrentio_selection,
        "display_picture": display_picture,
        "display_text": display_text,
        "show_pack_info": show_pack_info,
    }

    if param_string:
        params = dict(parse.parse_qsl(param_string))
        kodilog(params)
        action = params.get("action")
        action_func = actions.get(action)
        if action_func:
            action_func(params)
            return

    root_menu()
