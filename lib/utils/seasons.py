import os
from lib.utils.kodi_utils import ADDON_PATH, container_update, get_kodi_version, url_for
from lib.utils.utils import (
    TMDB_POSTER_URL,
    get_fanart,
    set_media_infotag,
    set_video_info,
    set_watched_title,
    tmdb_get,
)
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem


def show_season_info(ids, mode, media_type, plugin):
    tmdb_id, tvdb_id, _ = ids.split(", ")

    details = tmdb_get("tv_details", tmdb_id)
    name = details.name
    seasons = details.seasons
    overview = details.overview

    set_watched_title(name, ids, mode=mode, media_type=media_type)

    show_poster = TMDB_POSTER_URL + details.poster_path if details.poster_path else ""
    fanart_data = get_fanart(tvdb_id)
    fanart = fanart_data["fanart"] if fanart_data else ""

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

        if get_kodi_version() >= 20:
            set_media_infotag(
                list_item, mode, name, overview, season_number=season_number, ids=ids
            )
        else:
            set_video_info(
                list_item, mode, name, overview, season_number=season_number, ids=ids
            )

        list_item.setArt(
            {
                "poster": poster,
                "tvshow.poster": poster,
                "fanart": fanart,
                "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
            }
        )
        list_item.setProperty("IsPlayable", "false")

        addDirectoryItem(
            plugin.handle,
            url_for(
                name="tv/details/season",
                tv_name=name,
                ids=ids,
                mode=mode,
                media_type=media_type,
                season=season_number,
            ),
            list_item,
            isFolder=True,
        )


def show_episode_info(tv_name, season, ids, mode, media_type, plugin):
    tmdb_id, tvdb_id, _ = ids.split(", ")
    season_details = tmdb_get("season_details", {"id": tmdb_id, "season": season})
    fanart_data = get_fanart(tvdb_id)

    for ep in season_details.episodes:
        ep_name = ep.name
        episode = ep.episode_number
        label = f"{season}x{episode}. {ep_name}"
        air_date = ep.air_date
        duration = ep.runtime
        tv_data = f"{ep_name}(^){episode}(^){season}"

        still_path = ep.get("still_path", "")
        if still_path:
            poster = TMDB_POSTER_URL + still_path
        else:
            poster = fanart_data.get("fanart", "") if fanart_data else ""

        list_item = ListItem(label=label)

        if get_kodi_version() >= 20:
            set_media_infotag(
                list_item,
                mode,
                tv_name,
                ep.overview,
                episode=episode,
                duration=duration,
                air_date=air_date,
                ids=ids,
            )
        else:
            set_video_info(
                list_item,
                mode,
                tv_name,
                ep.overview,
                episode=episode,
                duration=duration,
                air_date=air_date,
                ids=ids,
            )

        list_item.setArt(
            {
                "poster": poster,
                "tvshow.poster": poster,
                "fanart": poster,
                "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
            }
        )
        list_item.setProperty("IsPlayable", "false")
        list_item.addContextMenuItems(
            [
                (
                    "Rescrape item",
                    container_update(
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
            plugin.handle,
             url_for(
                name="search",
                mode=mode,
                media_type=media_type,
                query=tv_name,
                ids=ids,
                tv_data=tv_data,
            ),
            list_item,
            isFolder=True,
        )