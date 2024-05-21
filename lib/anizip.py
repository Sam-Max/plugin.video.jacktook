import os
from lib.api.anizip_api import AniZipApi
from lib.db.anime_db import get_all_ids
from lib.utils.kodi_utils import ADDON_PATH, get_kodi_version, url_for
from lib.utils.general_utils import get_cached, set_cached, set_video_info, set_video_infotag, tvdb_get
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory


def search_anizip_episodes(title, anilist_id, plugin):
    res = search_anizip_api(anilist_id)
    anizip_parse_show_results(res, title, anilist_id, plugin)


def search_anizip_api(anilist_id):
    cached_results = get_cached(type, params=(anilist_id))
    if cached_results:
        return cached_results

    anizip = AniZipApi()
    res = anizip.episodes(anilist_id)

    set_cached(res, type, params=(anilist_id))
    return res


def anizip_parse_show_results(response, title, anilist_id, plugin):
    for res in response.values():
        season = res.get("seasonNumber", 0)
        if season == 0:
            continue
        episode = res["episodeNumber"]

        ep_name = res["title"]["en"]
        if ep_name:
            ep_name = f"{season}x{episode} {ep_name}"
        else:
            ep_name = f"Episode {episode}"

        description = res.get("overview", "")
        date = res["airdate"]
        poster = res.get("image", "")

        ids = get_all_ids(anilist_id)
        if ids is None:
            return
        imdb_id = ids.get("imdb", -1)
        tvdb_id = ids.get("tvdb", -1)
        tmdb_id = ids.get("tmdb", -1)

        list_item = ListItem(label=ep_name)
        list_item.setArt(
            {
                "poster": poster,
                "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
                "fanart": poster,
            }
        )
        list_item.setProperty("IsPlayable", "false")

        if get_kodi_version() >= 20:
            set_video_infotag(
                list_item,
                mode="tv",
                name=ep_name,
                overview=description,
                ep_name=ep_name,
                air_date=date,
            )
        else:
            set_video_info(
                list_item,
                mode="tv",
                name=ep_name,
                overview=description,
                ep_name=ep_name,
                air_date=date,
            )

        addDirectoryItem(
            plugin.handle,
            url_for(
                name="search",
                mode="anime",
                query=title,
                ids=f"{tmdb_id}, {tvdb_id}, {imdb_id}",
                tv_data=f"{ep_name}(^){episode}(^){season}",
            ),
            list_item,
            isFolder=True,
        )

    endOfDirectory(plugin.handle)
