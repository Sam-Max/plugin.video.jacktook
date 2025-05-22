import os
import re
from lib.clients.fma import FindMyAnime, extract_season
from lib.clients.simkl import SIMKL
from lib.utils.kodi.utils import ADDON_HANDLE, ADDON_PATH
from lib.utils.general.utils import (
    get_cached,
    set_cached,
    set_media_infotag,
)

from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, endOfDirectory


IMAGE_PATH = "https://wsrv.nl/?url=https://simkl.in/episodes/%s_w.webp"


def search_simkl_episodes(title, anilist_id, mal_id, plugin):
    fma = FindMyAnime()
    data = fma.get_anime_data(anilist_id, "Anilist")
    s_id = extract_season(data[0]) if data else ""
    season = s_id[0] if s_id else 1
    try:
        res = search_simkl_api(mal_id)
        simkl_parse_show_results(res, title, season, plugin)
    except Exception as e:
        kodilog(e)


def search_simkl_api(mal_id):
    cached_results = get_cached(type, params=(mal_id))
    if cached_results:
        return cached_results

    simkl = SIMKL()
    res = simkl.get_anilist_episodes(mal_id)

    set_cached(res, type, params=(mal_id))
    return res


def simkl_parse_show_results(response, title, season, plugin):
    for res in response:
        if res["type"] == "episode":
            episode = res["episode"]
            ep_name = res.get("title")
            if ep_name:
                ep_name = f"{season}x{episode} {ep_name}"
            else:
                ep_name = f"Episode {episode}"
            
            description = res.get("description", "")

            date = res.get("date", "")
            match = re.search(r"\d{4}-\d{2}-\d{2}", date)
            if match:
                date = match.group()

            poster = IMAGE_PATH % res.get("img", "")

            list_item = ListItem(label=ep_name)
            list_item.setArt(
                {
                    "poster": poster,
                    "icon": os.path.join(
                        ADDON_PATH, "resources", "img", "trending.png"
                    ),
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

            addDirectoryItem(
                ADDON_HANDLE,
                url_for(
                    name="search",
                    mode="anime",
                    query=title,
                    ids=f"{-1}, {-1}, {-1}",
                    tv_data=f"{ep_name}(^){episode}(^){season}",
                ),
                list_item,
                isFolder=True,
            )

    endOfDirectory(ADDON_HANDLE)
