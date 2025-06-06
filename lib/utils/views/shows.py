from lib.api.trakt.trakt_utils import add_trakt_watched_context_menu, is_trakt_auth
from lib.clients.tmdb.utils import tmdb_get
from lib.utils.kodi.utils import ADDON_HANDLE, build_url, play_media
from lib.utils.general.utils import (
    get_fanart_details,
    set_media_infoTag,
)

from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem


def show_season_info(ids, mode, media_type):
    tmdb_id, tvdb_id, imdb_id = ids.values()

    if imdb_id:
        res = tmdb_get("find_by_imdb_id", imdb_id)
        tmdb_id = res["tv_results"][0]["id"]
        ids = {"tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id}

    details = tmdb_get("tv_details", tmdb_id)
    name = details.name
    seasons = details.seasons
    fanart_details = get_fanart_details(tvdb_id=tvdb_id, mode=mode)

    for season in seasons:
        season_name = season.name
        if "Specials" in season_name:
            continue

        if "Miniseries" in season_name:
            season_name = "Season 1"

        season_number = season.season_number
        if season_number == 0:
            continue

        list_item = ListItem(label=season_name)

        set_media_infoTag(
            list_item, metadata=details, fanart_details=fanart_details, mode=mode
        )

        list_item.setProperty("IsPlayable", "false")

        if is_trakt_auth():
            list_item.addContextMenuItems(
                add_trakt_watched_context_menu("shows", season=season_number, ids=ids)
            )

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

    fanart_data = get_fanart_details(tvdb_id=ids.get("tvdb_id"), mode=mode)

    for episode in season_details.episodes:
        ep_name = episode.name
        episode_number = episode.episode_number

        tv_data = {"name": ep_name, "episode": episode_number, "season": season}

        list_item = ListItem(label=f"{season}x{episode_number}. {ep_name}")

        set_media_infoTag(
            list_item, metadata=episode, fanart_details=fanart_data, mode="episode"
        )

        list_item.setProperty("IsPlayable", "true")
        list_item.addContextMenuItems(
            [
                (
                    "Rescrape item",
                    play_media(
                        name="search",
                        mode=mode,
                        query=tv_name,
                        ids=ids,
                        tv_data=tv_data,
                        rescrape=True,
                    ),
                )
            ] + add_trakt_watched_context_menu(
                    "shows", season=season, episode=episode_number, ids=ids
                ) if is_trakt_auth() else []
        )

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
