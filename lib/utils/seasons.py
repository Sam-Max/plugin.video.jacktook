import os
from lib.utils.kodi_utils import ADDON_HANDLE, ADDON_PATH, build_url, play_media
from lib.utils.tmdb_utils import tmdb_get
from lib.utils.utils import (
    TMDB_POSTER_URL,
    get_fanart_details,
    set_media_infotag,
)
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem


def show_season_info(ids, mode, media_type):
    tmdb_id, tvdb_id, _ = [id.strip() for id in ids.split(',')]

    details = tmdb_get("tv_details", tmdb_id)
    name = details.name
    seasons = details.seasons
    overview = details.overview

    show_poster = f"{TMDB_POSTER_URL}{details.poster_path or ''}"
    fanart_data = get_fanart_details(tvdb_id=tvdb_id, mode=mode)

    for s in seasons:
        season_name = s.name
        if "Specials" in season_name:
            continue

        if "Miniseries" in season_name:
            season_name = "Season 1"

        season_number = s.season_number
        if season_number == 0:
            continue

        if s.poster_path:
            poster = TMDB_POSTER_URL + s.poster_path
        else:
            poster = show_poster

        list_item = ListItem(label=season_name)

        set_media_infotag(
            list_item, mode, name, overview, season=season_number, ids=ids
        )

        list_item.setArt(
            {
                "poster": poster,
                "tvshow.poster": poster,
                "fanart": fanart_data["fanart"],
                "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
            }
        )
        list_item.setProperty("IsPlayable", "false")

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
    tmdb_id, tvdb_id, _ = [id.strip() for id in ids.split(',')]
    season_details = tmdb_get("season_details", {"id": tmdb_id, "season": season})
    fanart_data = get_fanart_details(tvdb_id=tvdb_id, mode=mode)

    for ep in season_details.episodes:
        ep_name = ep.name
        episode = ep.episode_number
        air_date = ep.air_date
        duration = ep.runtime
        tv_data = f"{ep_name}(^){episode}(^){season}"
        label = f"{season}x{episode}. {ep_name}"
        still_path = ep.get("still_path", "")
        if still_path:
            poster = TMDB_POSTER_URL + still_path
        else:
            poster = fanart_data.get("fanart", "") if fanart_data else ""

        list_item = ListItem(label=label)

        set_media_infotag(
            list_item,
            mode,
            tv_name,
            ep.overview,
            season=season,
            episode=episode,
            ep_name=ep_name,
            duration=duration,
            air_date=air_date,
            ids=ids,
        )

        list_item.setProperty("IsPlayable", "true")

        list_item.setArt(
            {
                "poster": poster,
                "tvshow.poster": poster,
                "fanart": poster,
                "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
            }
        )
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
            ]
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
