from xbmcplugin import addDirectoryItem, endOfDirectory, setContent
from xbmcgui import ListItem
from lib.clients.stremio_addon import StremioAddonCatalogsClient
from lib.stremio.ui import get_selected_catalogs_addons
from lib.utils.kodi_utils import ADDON_HANDLE, build_url, notification


def list_stremio_catalogs(menu_type="tv"):
    selected_addons = get_selected_catalogs_addons()
    if not selected_addons:
        return

    for addon in selected_addons:
        for catalog in addon.manifest.catalogs:
            if menu_type == catalog["type"]:
                action = "list_stremio_catalog"
                listitem = ListItem(label=catalog["name"])
                listitem.setArt({"icon": addon.manifest.logo})
                addDirectoryItem(
                    ADDON_HANDLE,
                    build_url(
                        action,
                        addon_url=addon.url(),
                        catalog_type=catalog["type"],
                        catalog_id=catalog["id"],
                    ),
                    listitem,
                    isFolder=True,
                )


def list_stremio_catalog(params):
    content_type = "movies" if params["catalog_type"] == "movie" else "tvshows"
    setContent(ADDON_HANDLE, content_type)

    skip = int(params.get("skip", 0))

    addon = StremioAddonCatalogsClient(params)
    response = addon.get_catalog_info(skip)
    if not response:
        return

    videos = response.get("metas", [])
    if not videos:
        notification("No videos available")
        return

    process_videos(videos, params["catalog_type"])

    if len(videos) >= 25:
        next_url = build_url(
            "list_stremio_catalog",
            catalog_type=params["catalog_type"],
            catalog_id=params["catalog_id"],
            skip=skip + len(videos),
        )
        list_item = ListItem(label="Next Page")
        addDirectoryItem(handle=ADDON_HANDLE, url=next_url, listitem=list_item, isFolder=True)

    endOfDirectory(ADDON_HANDLE)


def process_videos(videos, catalog_type):
    content_type = "movies" if catalog_type == "movie" else "tvshows"
    setContent(ADDON_HANDLE, content_type)

    for video in videos:
        if catalog_type in ["series", "anime"]: 
            url = build_url(
                "list_stremio_seasons",
                catalog_type=catalog_type,
                video_id=video["id"],
            )
        else:
            url = build_url(
                "get_streams", video_id=video["id"], catalog_type=catalog_type
            )
        list_item = ListItem(label=video["name"])
        tags = list_item.getVideoInfoTag()
        tags.setUniqueID(
            video["id"], type="imdb" if video["id"].startswith("tt") else "mf"
        )
        tags.setTitle(video["name"])
        tags.setPlot(video.get("description", ""))
        tags.setRating(float(video.get("imdbRating", 0)))
        tags.setGenres(video.get("genres", []))

        list_item.setArt(
            {
                "thumb": video.get("poster", ""),
                "poster": video.get("poster", ""),
                "fanart": video.get("poster", ""),
                "icon": video.get("poster", ""),
                "banner": video.get("background", ""),
                "landscape": video.get("background", ""),
            }
        )

        addDirectoryItem(
            handle=ADDON_HANDLE, url=url, listitem=list_item, isFolder=True
        )


def list_stremio_seasons(params):
    addon = StremioAddonCatalogsClient(params)
    response = addon.get_season_info()
    if not response:
        return

    meta_data = response.get("meta", {})
    videos = meta_data.get("videos", [])
    if not videos:
        notification("No seasons available")
        return

    available_seasons = set(video["season"] for video in videos)

    for season in available_seasons:
        url = build_url(
            "list_episodes",
            catalog_type=params["catalog_type"],
            video_id=params["video_id"],
            season=season,
        )
        list_item = ListItem(label=f"Season {season}")
        tags = list_item.getVideoInfoTag()
        tags.setUniqueID(
            meta_data["id"], type="imdb" if meta_data["id"].startswith("tt") else "mf"
        )
        tags.setTitle(meta_data["name"])
        tags.setPlot(meta_data.get("description", ""))
        tags.setRating(float(meta_data.get("imdbRating", 0)))
        tags.setGenres(meta_data.get("genres", []))
        tags.setTvShowTitle(meta_data["name"])
        tags.setSeason(season)

        list_item.setArt(
            {
                "thumb": meta_data.get("poster", ""),
                "poster": meta_data.get("poster", ""),
                "fanart": meta_data.get("poster", ""),
                "icon": meta_data.get("poster", ""),
                "banner": meta_data.get("background", ""),
                "landscape": meta_data.get("background", ""),
            }
        )

        addDirectoryItem(
            handle=ADDON_HANDLE, url=url, listitem=list_item, isFolder=True
        )

    endOfDirectory(ADDON_HANDLE)


def get_streams(params):
    addon = StremioAddonCatalogsClient(params)
    response = addon.get_streams()
    if not response:
        return
    
    streams = response.get("streams", [])
    if not streams:
        notification("No streams available")
        return

    for stream in streams:
        list_item = ListItem(label=stream["name"], offscreen=True)
        tags = list_item.getVideoInfoTag()
        tags.setTitle(stream["name"])
        tags.setPlot(stream.get("description", ""))

        list_item.setProperty("IsPlayable", "true")

        if "url" in stream:
            video_url = stream.get("url")
        elif "infoHash" in stream:
            magnet = info_hash_to_magnet(
                stream.get("infoHash"), stream.get("sources", [])
            )
        else:
            continue

        addDirectoryItem(
            handle=ADDON_HANDLE,
            url=build_url(
                "play_video",
                video_url=video_url,
            ),
            listitem=list_item,
            isFolder=False,
            totalItems=len(streams),
        )
    endOfDirectory(ADDON_HANDLE)