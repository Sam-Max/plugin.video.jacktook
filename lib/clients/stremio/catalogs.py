import json
from lib.clients.stremio.ui import get_selected_catalogs_addons
from lib.clients.tmdb.utils import tmdb_get
from lib.utils.general.utils import add_next_button
from lib.db.main import main_db
from lib.utils.stremio.catalogs_utils import catalogs_get_cache
from lib.utils.kodi.utils import ADDON_HANDLE, build_url, kodilog, notification, show_keyboard

from xbmcplugin import addDirectoryItem, endOfDirectory, setContent
from xbmcgui import ListItem



def list_stremio_catalogs(menu_type=None, sub_menu_type=None):
    selected_addons = get_selected_catalogs_addons()
    if not selected_addons:
        return

    for addon in selected_addons:
        for catalog in addon.manifest.catalogs:
            if catalog["type"] == menu_type:
                catalog_name = catalog.get("name")
                catalog_id = catalog.get("id")

                search_capabilities = any(
                    extra["name"] == "search" for extra in catalog.get("extra", [])
                )

                if search_capabilities:
                    listitem = ListItem(label=f"Search-{catalog_name}")
                    listitem.setArt({"icon": addon.manifest.logo})

                    addDirectoryItem(
                        ADDON_HANDLE,
                        build_url(
                            "search_catalog",
                            page=1,
                            addon_url=addon.url(),
                            catalog_type=catalog["type"],
                            catalog_id=catalog_id,
                        ),
                        listitem,
                        isFolder=True,
                    )

                if catalog_name or catalog_id:
                    action = "list_stremio_catalog"
                    addon_name = addon.manifest.name
                    if addon_name == "Cinemeta":
                        label = f"{addon_name} - {catalog_name or catalog_id}"
                    else:
                        label = catalog_name or catalog_id

                    listitem = ListItem(label=label)
                    listitem.setArt({"icon": addon.manifest.logo})

                    addDirectoryItem(
                        ADDON_HANDLE,
                        build_url(
                            action,
                            addon_url=addon.url(),
                            menu_type=menu_type,
                            sub_menu_type=sub_menu_type,
                            catalog_type=catalog["type"],
                            catalog_id=catalog["id"],
                        ),
                        listitem,
                        isFolder=True,
                    )


def search_catalog(params):
    page = int(params["page"])

    if page == 1:
        query = show_keyboard(id=30241)
        if not query:
            return
        main_db.set_query("search_catalog_query", query)
    else:
        query = main_db.get_query("search_catalog_query")

    response = catalogs_get_cache("search_catalog", params, query)
    if not response:
        return

    meta_data = response.get("metas", {})

    kodilog(f"Catalog response: {meta_data}")

    for meta in meta_data:
        if meta["type"] == "series":
            tmdb_id = meta.get("moviedb_id")
            imdb_id = meta.get("imdb_id")

            if tmdb_id or imdb_id:
                ids = {"tmdb_id": tmdb_id, "tvdb_id": "", "imdb_id": imdb_id}
                url = build_url(
                    "tv_seasons_details",
                    ids=ids,
                    mode="tv",
                    media_type="tv",
                )
            else:
                url = build_url(
                    "list_stremio_seasons",
                    addon_url=params["addon_url"],
                    catalog_type=params["catalog_type"],
                    video_id=meta["id"],
                )
        elif meta["type"] == "movie":
            tmdb_id = ""
            id = meta.get("id", "")
            if "tmdb" in id:
                tmdb_id = id.split(":")[1]

            ids = {"tmdb_id": tmdb_id, "tvdb_id": "", "imdb_id": meta.get("imdb_id")}
            url = build_url("search", mode="movies", query=meta["name"], ids=ids)
        else:
            continue

        list_item = ListItem(label=f"{meta['name']}")

        tags = list_item.getVideoInfoTag()
        tags.setUniqueID(
            meta["id"], type="imdb" if meta["id"].startswith("tt") else "mf"
        )
        tags.setTitle(meta["name"])
        tags.setPlot(meta.get("description", ""))
        # tags.setRating(float(meta.get("imdbRating", 0) or 0))
        tags.setGenres(meta.get("genres", []))
        tags.setMediaType("video")

        if meta["type"] == "movie":
            list_item.setProperty("IsPlayable", "true")
            isFolder = False
        else:
            isFolder = True

        list_item.setArt(
            {
                "thumb": meta.get("poster", ""),
                "poster": meta.get("poster", ""),
                "fanart": meta.get("poster", ""),
                "icon": meta.get("poster", ""),
                "banner": meta.get("background", ""),
                "landscape": meta.get("background", ""),
            }
        )

        addDirectoryItem(
            handle=ADDON_HANDLE, url=url, listitem=list_item, isFolder=isFolder
        )

    add_next_button("search_catalog", page=page, mode=params["catalog_type"])
    endOfDirectory(ADDON_HANDLE)


def list_stremio_catalog(params):
    content_type = "movies" if params["catalog_type"] == "movie" else "tvshows"
    setContent(ADDON_HANDLE, content_type)

    skip = int(params.get("skip", 0))

    response = catalogs_get_cache("list_stremio_catalog", params, skip)
    if not response:
        return

    videos = response.get("metas", [])
    if not videos:
        notification("No videos available")
        return

    process_videos(
        videos,
        params["menu_type"],
        params["sub_menu_type"],
        params["addon_url"],
        params["catalog_type"],
    )

    if len(videos) >= 25:
        next_url = build_url(
            "list_stremio_catalog",
            addon_url=params["addon_url"],
            menu_type=params["menu_type"],
            sub_menu_type=params["sub_menu_type"],
            catalog_type=params["catalog_type"],
            catalog_id=params["catalog_id"],
            skip=skip + len(videos),
        )
        list_item = ListItem(label="Next Page")
        addDirectoryItem(
            handle=ADDON_HANDLE, url=next_url, listitem=list_item, isFolder=True
        )

    endOfDirectory(ADDON_HANDLE)


def process_videos(videos, menu_type, sub_menu_type, addon_url, catalog_type):
    content_type = "movies" if catalog_type == "movie" else "tvshows"
    setContent(ADDON_HANDLE, content_type)

    if menu_type in ["anime", "movie"] and sub_menu_type == "movie":
        videos = [video for video in videos if video["type"] == "movie"]
    elif menu_type in ["anime", "series"] and sub_menu_type == "series":
        videos = [video for video in videos if video["type"] == "series"]
    elif menu_type in ["tv"]:
        videos = [video for video in videos if video["type"] == "tv"]

    for video in videos:
        if video["type"] == "series":
            tmdb_id = video.get("moviedb_id")
            imdb_id = video.get("imdb_id")

            if tmdb_id or imdb_id:
                ids = {"tmdb_id": tmdb_id, "tvdb_id": "", "imdb_id": imdb_id}
                url = build_url(
                    "tv_seasons_details",
                    ids=ids,
                    mode="tv",
                    media_type="tv",
                )
            else:
                url = build_url(
                    "list_stremio_seasons",
                    addon_url=addon_url,
                    catalog_type=catalog_type,
                    video_id=video["id"],
                )
        elif video["type"] == "tv":
            if video.get("streams"):
                url = build_url("list_stremio_tv_streams", streams=video["streams"])
            else:
                url = build_url(
                    "list_stremio_tv",
                    addon_url=addon_url,
                    catalog_type=catalog_type,
                    video_id=video["id"],
                )
        elif video["type"] == "movie":
            tmdb_id = ""
            id = video.get("id", "")
            if "tmdb" in id:
                tmdb_id = id.split(":")[1]

            ids = {"tmdb_id": tmdb_id, "tvdb_id": "", "imdb_id": video.get("imdb_id")}
            url = build_url("search", mode="movies", query=video["name"], ids=ids)
        else:
            continue

        list_item = ListItem(label=f"{video['name']}")

        tags = list_item.getVideoInfoTag()
        tags.setUniqueID(
            video["id"], type="imdb" if video["id"].startswith("tt") else "mf"
        )
        tags.setTitle(video["name"])
        tags.setPlot(video.get("description", ""))
        # tags.setRating(float(video.get("imdbRating", 0) or 0))
        tags.setGenres(video.get("genres", []))
        tags.setMediaType("video")

        if video["type"] == "movie":
            list_item.setProperty("IsPlayable", "true")
            isFolder = False
        else:
            isFolder = True

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
            handle=ADDON_HANDLE, url=url, listitem=list_item, isFolder=isFolder
        )


def list_stremio_seasons(params):
    kodilog("catalogs::list_stremio_seasons")
    response = catalogs_get_cache("list_stremio_seasons", params)
    if not response:
        return

    meta_data = response.get("meta", {})
    videos = meta_data.get("videos", [])
    if not videos:
        notification("No seasons available")
        return

    available_seasons = set(
        video["imdbSeason"] if video.get("imdbSeason") else video["season"]
        for video in videos
    )
    for season in available_seasons:
        url = build_url(
            "list_stremio_episodes",
            addon_url=params["addon_url"],
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


def list_stremio_episodes(params):
    kodilog("catalogs::list_stremio_episodes")
    response = catalogs_get_cache("list_stremio_episodes", params)
    if not response:
        return

    meta_data = response.get("meta", {})
    videos = meta_data.get("videos", [])
    if not videos:
        notification("No episodes available")
        return

    for video in videos:
        season = (
            int(video["imdbSeason"]) if video.get("imdbSeason") else video["season"]
        )
        episode = (
            int(video["imdbEpisode"]) if video.get("imdbEpisode") else video["episode"]
        )

        if season != int(params["season"]):
            continue

        title = video.get("title") or video.get("name")

        tv_data = {
            "name": title,
            "episode": episode,
            "season": season,
        }

        ids = {"tmdb_id": "", "tvdb_id": "", "imdb_id": ""}

        if imdb_id := meta_data.get("imdb_id"):
            ids["imdb_id"] = imdb_id
            res = tmdb_get("find_by_imdb_id", imdb_id)
            if res["tv_results"]:
                ids["tmdb_id"] = res["tv_results"][0]["id"]

        if video["id"].startswith("tt") and not imdb_id:
            imdb_id = meta_data["id"].split(":")[0]
            ids["imdb_id"] = imdb_id
            res = tmdb_get("find_by_imdb_id", imdb_id)
            if res["tv_results"]:
                ids["tmdb_id"] = res["tv_results"][0]["id"]

        url = build_url(
            "search",
            mode="tv",
            media_type="tv",
            query=meta_data["name"],
            ids=ids,
            tv_data=tv_data,
        )

        list_item = ListItem(label=f"{season}x{episode}. {title}")
        tags = list_item.getVideoInfoTag()
        tags.setUniqueID(
            meta_data["id"], type="imdb" if meta_data["id"].startswith("tt") else "mf"
        )
        tags.setTitle(title)
        tags.setPlot(video.get("overview", ""))
        tags.setRating(float(meta_data.get("imdbRating", 0)))
        tags.setGenres(meta_data.get("genres", []))
        tags.setTvShowTitle(title)
        tags.setSeason(season)
        tags.setEpisode(episode)

        list_item.setProperty("IsPlayable", "true")

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
            handle=ADDON_HANDLE, url=url, listitem=list_item, isFolder=False
        )

    endOfDirectory(ADDON_HANDLE)


def list_stremio_tv(params):
    response = catalogs_get_cache("list_stremio_tv", params)
    if not response:
        return

    streams = response.get("streams", [])
    if not streams:
        notification("No videos available")
        return

    for stream in streams:
        url = build_url(
            "play_torrent",
            data={"mode": "movie", "url": stream["url"]},
        )

        list_item = ListItem(label=stream["title"])
        list_item.setProperty("IsPlayable", "true")
        tags = list_item.getVideoInfoTag()
        tags.setPlot(stream.get("description", ""))

        addDirectoryItem(
            handle=ADDON_HANDLE, url=url, listitem=list_item, isFolder=False
        )

    endOfDirectory(ADDON_HANDLE)


def list_stremio_tv_streams(params):
    streams = json.loads(params.get("streams", {}))
    for stream in streams:
        url = build_url(
            "play_torrent",
            data={"mode": "movie", "url": stream["url"]},
        )

        list_item = ListItem(label=stream["name"])
        list_item.setProperty("IsPlayable", "true")
        tags = list_item.getVideoInfoTag()
        tags.setPlot(stream.get("description", ""))

        addDirectoryItem(
            handle=ADDON_HANDLE, url=url, listitem=list_item, isFolder=False
        )

    endOfDirectory(ADDON_HANDLE)
