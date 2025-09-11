from lib.api.trakt.trakt_utils import add_trakt_watched_context_menu, is_trakt_auth
from lib.clients.tmdb.utils.utils import (
    add_tmdb_episode_context_menu,
    add_tmdb_show_context_menu,
    tmdb_get,
)
from lib.utils.kodi.utils import ADDON_HANDLE, build_url, get_setting, kodilog
from lib.utils.general.utils import (
    get_fanart_details,
    set_media_infoTag,
)

from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem


def show_season_info(ids, mode, media_type):
    tmdb_id = ids.get("tmdb_id")
    tvdb_id = ids.get("tvdb_id")
    imdb_id = ids.get("imdb_id")

    if imdb_id:
        res = tmdb_get("find_by_imdb_id", imdb_id)
        if res and res.get("tv_results"):
            tmdb_id = res["tv_results"][0]["id"]

    ids = {"tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id}

    details = tmdb_get("tv_details", tmdb_id)
    name = getattr(details, "name")
    seasons = getattr(details, "seasons")
    fanart_details = get_fanart_details(tvdb_id=tvdb_id, mode=mode)

    for season in seasons:
        season_name = season.name
        overview = season.overview
        if not overview:
            season.update({"overview": getattr(details, "overview", "")})

        if "Miniseries" in season_name:
            season_name = "Season 1"

        season_number = season.season_number
        if season_number == 0 and not get_setting("include_tvshow_specials"):
            continue

        list_item = ListItem(label=season_name)

        set_media_infoTag(list_item, data=season, fanart_data=fanart_details, mode=mode)

        list_item.setProperty("IsPlayable", "false")

        context_menu = add_tmdb_show_context_menu(mode, ids)

        if is_trakt_auth():
            context_menu += add_trakt_watched_context_menu(
                "shows", season=season_number, ids=ids
            )

        list_item.addContextMenuItems(context_menu)

        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "tv_episodes_details",
                tv_name=name,
                ids=ids,
                mode=mode,
                media_type=media_type,
                season=season_number,
            ),
            list_item,
            isFolder=True,
        )


def show_episode_info(tv_name, season, ids, mode, media_type):
    season_details = tmdb_get(
        "season_details", {"id": ids.get("tmdb_id"), "season": season}
    )
    fanart_details = get_fanart_details(tvdb_id=ids.get("tvdb_id"), mode=mode)

    for episode in getattr(season_details, "episodes"):
        ep_name = episode.name
        episode_number = episode.episode_number

        tv_data = {"name": ep_name, "episode": episode_number, "season": season}

        list_item = ListItem(label=f"{season}x{episode_number}. {ep_name}")

        set_media_infoTag(
            list_item, data=episode, fanart_data=fanart_details, mode=mode
        )

        list_item.setProperty("IsPlayable", "true")

        context_menu = add_tmdb_episode_context_menu(mode, tv_name, tv_data, ids)

        if is_trakt_auth():
            context_menu += add_trakt_watched_context_menu(
                "shows", season=season, episode=episode_number, ids=ids
            )

        list_item.addContextMenuItems(context_menu)

        addDirectoryItem(
            ADDON_HANDLE,
            build_url(
                "search",
                mode=mode,
                media_type=media_type,
                query=tv_name,
                ids=ids,
                tv_data=tv_data,
            ),
            list_item,
            isFolder=False,
        )
