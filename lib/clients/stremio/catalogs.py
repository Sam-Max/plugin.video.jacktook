import json
from lib.clients.stremio.ui import get_selected_catalogs_addons
from lib.clients.tmdb.utils.utils import tmdb_get
from lib.utils.general.utils import add_next_button
from lib.db.pickle_db import PickleDatabase
from lib.utils.stremio.catalogs_utils import catalogs_get_cache
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    build_url,
    kodilog,
    notification,
    show_keyboard,
)

from xbmcplugin import addDirectoryItem, endOfDirectory, setContent
from xbmcgui import ListItem
import xbmc


def list_stremio_catalogs(menu_type="", sub_menu_type=""):
    selected_addons = get_selected_catalogs_addons()
    if not selected_addons:
        if menu_type == "tv":
            notification("No TV catalogs addons selected")
            return
        return

    for addon in selected_addons:
        if menu_type in addon.manifest.types:
            for catalog in addon.manifest.catalogs:
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
                            action="list_catalog",
                            addon_url=addon.url(),
                            menu_type=menu_type,
                            sub_menu_type=sub_menu_type,
                            catalog_type=catalog["type"],
                            catalog_id=catalog["id"],
                        ),
                        listitem,
                        isFolder=True,
                    )


def list_catalog(params):
    content_type = "movies" if params["menu_type"] == "movie" else "tvshows"
    setContent(ADDON_HANDLE, content_type)

    skip = int(params.get("skip", 0))
    response = catalogs_get_cache("list_catalog", params, skip)
    if not response:
        return

    videos = response.get("metas", [])
    if not videos:
        notification("No videos available")
        return

    add_meta_items(videos, params)

    if len(videos) >= 25:
        next_url = build_url(
            "list_catalog",
            addon_url=params["addon_url"],
            menu_type=params["menu_type"],
            sub_menu_type=params.get("sub_menu_type", ""),
            catalog_type=params["catalog_type"],
            catalog_id=params["catalog_id"],
            skip=skip + len(videos),
        )
        list_item = ListItem(label="Next Page")
        addDirectoryItem(
            handle=ADDON_HANDLE, url=next_url, listitem=list_item, isFolder=True
        )

    endOfDirectory(ADDON_HANDLE)


def search_catalog(params):
    page = int(params["page"])
    pickle_db = PickleDatabase()

    if page == 1:
        query = show_keyboard(id=30241)
        if not query:
            return
        pickle_db.set_key("search_catalog_query", query)
    else:
        query = pickle_db.get_key("search_catalog_query")

    response = catalogs_get_cache("search_catalog", params, query)
    if not response:
        return

    meta_data = response.get("metas", {})
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


def add_meta_items(videos, params):
    catalog_type = params["catalog_type"]
    menu_type = params["menu_type"]
    sub_menu_type = params.get("sub_menu_type", "")
    addon_url = params["addon_url"]

    content_type = "movies" if menu_type == "movie" else "tvshows"
    setContent(ADDON_HANDLE, content_type)

    # Filtrado por tipo de video según el menú
    def should_include(video):
        video_type = video["type"]
        if menu_type in ["anime", "movie"] and sub_menu_type == "movie":
            kodilog(f"Filtering video: {video_type} for menu type: {menu_type}")
            return video_type == "movie"
        if menu_type in ["anime", "series"] and sub_menu_type == "series":
            return video_type == "series"
        if menu_type == "tv":
            return video_type == "tv"
        return True

    videos = [v for v in videos if should_include(v)]

    kodilog(f"Filtered videos: {videos}", level=xbmc.LOGDEBUG)

    if not videos:
        notification(f"No content available for {menu_type}")
        endOfDirectory(ADDON_HANDLE)
        return

    for video in videos:
        name = video.get("name", "")
        video_type = video["type"]
        video_id = video.get("id", "")
        tmdb_id = video.get("moviedb_id", "")
        imdb_id = video.get("imdb_id", "")

        if "tmdb" in video_id:
            tmdb_id = video_id.split(":")[1]
        elif video_id.startswith("tt"):
            imdb_id = video_id
            tmdb_id = ""

        # Construcción de la URL según tipo
        if video_type == "series":
            if tmdb_id or imdb_id:
                ids = {"tmdb_id": tmdb_id, "tvdb_id": "", "imdb_id": imdb_id}
                url = build_url(
                    "tv_seasons_details", ids=ids, mode="tv", media_type="tv"
                )
            else:
                url = build_url(
                    "list_stremio_seasons",
                    addon_url=addon_url,
                    catalog_type=catalog_type,
                    video_id=video_id,
                )

        elif video_type == "tv":
            if video.get("streams"):
                url = build_url("list_stremio_tv_streams", streams=video["streams"])
            else:
                url = build_url(
                    "list_stremio_tv",
                    addon_url=addon_url,
                    catalog_type=catalog_type,
                    video_id=video_id,
                )

        elif video_type == "movie":
            ids = {"tmdb_id": tmdb_id, "tvdb_id": "", "imdb_id": imdb_id}
            url = build_url("search", mode="movies", query=name, ids=ids)
        else:
            continue

        # Creación del ListItem
        list_item = ListItem(label=name)
        tags = list_item.getVideoInfoTag()
        tags.setUniqueID(video_id, type="imdb" if video_id.startswith("tt") else "mf")
        tags.setTitle(name)
        tags.setPlot(video.get("description", ""))
        tags.setGenres(video.get("genres", []))
        tags.setMediaType("video")

        # Marcar como reproducible si es película
        is_folder = video_type != "movie"
        if not is_folder:
            list_item.setProperty("IsPlayable", "true")

        # Setear arte
        poster = video.get("poster", "")
        background = video.get("background", "")
        list_item.setArt(
            {
                "thumb": poster,
                "poster": poster,
                "fanart": poster,
                "icon": poster,
                "banner": background,
                "landscape": background,
            }
        )

        addDirectoryItem(
            handle=ADDON_HANDLE, url=url, listitem=list_item, isFolder=is_folder
        )


def list_stremio_seasons(params):
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
            if getattr(res, "tv_results", []):
                ids["tmdb_id"] = getattr(res, "tv_results")[0]["id"]

        if video["id"].startswith("tt") and not imdb_id:
            imdb_id = meta_data["id"].split(":")[0]
            ids["imdb_id"] = imdb_id
            res = tmdb_get("find_by_imdb_id", imdb_id)
            if getattr(res, "tv_results", []):
                ids["tmdb_id"] = getattr(res, "tv_results")[0]["id"]

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
