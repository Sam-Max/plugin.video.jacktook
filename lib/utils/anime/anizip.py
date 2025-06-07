import os
from lib.clients.anizip import AniZipApi
from lib.db.anime import get_all_ids
from lib.utils.kodi.utils import ADDON_HANDLE, ADDON_PATH, play_media
from lib.utils.general.utils import get_cached, set_cached, set_media_infotag

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

        tv_data = f"{ep_name}(^){episode}(^){season}"

        description = res.get("overview", "")
        date = res["airdate"]
        poster = res.get("image", "")

        ids = get_all_ids(anilist_id)
        if ids is None:
            return
        imdb_id = ids.get("imdb", -1)
        tvdb_id = ids.get("tvdb", -1)
        tmdb_id = ids.get("tmdb", -1)

        ids=f"{tmdb_id}, {tvdb_id}, {imdb_id}"

        list_item = ListItem(label=ep_name)
        list_item.setArt(
            {
                "poster": poster,
                "icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png"),
                "fanart": poster,
            }
        )
        list_item.setProperty("IsPlayable", "false")

        set_media_infotag(
            list_item,
            mode="tv",
            name=ep_name,
            overview=description,
            ep_name=ep_name,
            air_date=date,
        )

        list_item.addContextMenuItems(
            [
                (
                    "Rescrape item",
                    play_media(
                        name="search",
                        mode="anime",
                        query=title,
                        ids=ids,
                        tv_data=tv_data,
                        rescrape=True,
                    ),
                )
            ]
        )
        
        addDirectoryItem(
            ADDON_HANDLE,
            url_for(
                name="search",
                mode="anime",
                query=title,
                ids=ids,
                tv_data=tv_data,
            ),
            list_item,
            isFolder=True,
        )

    endOfDirectory(ADDON_HANDLE)
