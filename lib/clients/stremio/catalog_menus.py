import json
from dataclasses import asdict
from lib.clients.stremio.helpers import get_selected_catalogs_addons, get_selected_tv_addons
from lib.clients.tmdb.utils.utils import tmdb_get
from lib.utils.general.utils import add_next_button
from lib.db.pickle_db import PickleDatabase
from lib.utils.stremio.catalogs_utils import catalogs_get_cache
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    build_url,
    end_of_directory,
    notification,
    show_keyboard,
)

from xbmcplugin import addDirectoryItem, setContent
from xbmcgui import ListItem


def list_stremio_catalogs(menu_type="", sub_menu_type=""):
    if menu_type == "tv":
        selected_addons = get_selected_tv_addons()
    else:
        selected_addons = get_selected_catalogs_addons()
    if not selected_addons:
        notification("No catalogs addons selected")
        return
        
    for addon in selected_addons:
        if menu_type in addon.manifest.types:
            for catalog in addon.manifest.catalogs:
                catalog_name = catalog.name
                catalog_id = catalog.id
                catalog_type = catalog.type

                # Filter catalogs by type to prevent duplicates and ensure correct content (e.g. Anime Movies vs Series)
                target_type = sub_menu_type if sub_menu_type else menu_type
                if target_type in ["movie", "series", "tv"] and catalog_type != target_type:
                    continue

                search_capabilities = any(
                    extra.get("name") == "search" for extra in catalog.extra
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
                            catalog_type=catalog.type,
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
                            catalog_type=catalog.type,
                            catalog_id=catalog.id,
                        ),
                        listitem,
                        isFolder=True,
                    )


def list_catalog(params):
    content_type = "movies" if params["menu_type"] == "movie" else "tvshows"
    setContent(ADDON_HANDLE, content_type)

    skip = int(params.get("skip", 0))
    
    # Extract known extra params
    extras = {}
    # Common Stremio extra params
    for key in ["genre", "search"]: 
        if key in params:
             extras[key] = params[key]

    response = catalogs_get_cache("list_catalog", params, skip=skip, **extras)
    if not response:
        return

    metas = response.get("metas", [])
    if not metas:
        notification("No metas available")
        return

    add_meta_items(metas, params)

    if len(metas) >= 25:
        next_url = build_url(
            "list_catalog",
            addon_url=params["addon_url"],
            menu_type=params["menu_type"],
            sub_menu_type=params.get("sub_menu_type", ""),
            catalog_type=params["catalog_type"],
            catalog_id=params["catalog_id"],
            skip=skip + len(metas),
        )
        list_item = ListItem(label="Next Page")
        addDirectoryItem(
            handle=ADDON_HANDLE, url=next_url, listitem=list_item, isFolder=True
        )

    end_of_directory()


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
        if meta.type == "series":
            tmdb_id = meta.moviedb_id
            imdb_id = meta.imdb_id

            if tmdb_id or imdb_id:
                ids = {"tmdb_id": tmdb_id, "tvdb_id": "", "imdb_id": imdb_id}
                url = build_url(
                    "show_seasons_details",
                    ids=ids,
                    mode="tv",
                    media_type="tv",
                )
            else:
                url = build_url(
                    "list_stremio_seasons",
                    addon_url=params["addon_url"],
                    catalog_type=params["catalog_type"],
                    video_id=meta.id,
                )
        elif meta.type == "movie":
            tmdb_id = ""
            id = meta.id
            if "tmdb" in id:
                tmdb_id = id.split(":")[1]

            ids = {"tmdb_id": tmdb_id, "tvdb_id": "", "imdb_id": meta.imdb_id}
            url = build_url("search", mode="movies", query=meta.name, ids=ids)
        else:
            continue

        list_item = ListItem(label=f"{meta.name}")
        info_tag = list_item.getVideoInfoTag()
        info_tag.setUniqueID(
            meta.id, type="imdb" if meta.id.startswith("tt") else "mf"
        )
        info_tag.setTitle(meta.name)
        info_tag.setPlot(meta.description or "")
        info_tag.setGenres(meta.genres)
        info_tag.setMediaType("video")

        if meta.type == "movie":
            list_item.setProperty("IsPlayable", "true")
            isFolder = False
        else:
            isFolder = True

        list_item.setArt(
            {
                "thumb": meta.poster or "",
                "poster": meta.poster or "",
                "fanart": meta.poster or "",
                "icon": meta.poster or "",
                "banner": meta.background or "",
                "landscape": meta.background or "",
            }
        )

        addDirectoryItem(
            handle=ADDON_HANDLE, url=url, listitem=list_item, isFolder=isFolder
        )

    add_next_button("search_catalog", page=page, mode=params["catalog_type"])
    end_of_directory()


def add_meta_items(metas, params):
    catalog_type = params["catalog_type"]
    menu_type = params["menu_type"]
    sub_menu_type = params.get("sub_menu_type", "")
    addon_url = params["addon_url"]

    content_type = "movies" if menu_type == "movie" else "tvshows"
    setContent(ADDON_HANDLE, content_type)

    def should_include(meta):
        meta_type = meta.type
        if menu_type in ["anime", "movie"] and sub_menu_type == "movie":
            return meta_type == "movie"
        if menu_type in ["anime", "series"] and sub_menu_type == "series":
            return meta_type == "series"
        if menu_type == "tv":
            return meta_type == "tv"
        return True

    metas = [m for m in metas if should_include(m)]
    if not metas:
        notification(f"No content available for {menu_type}")
        end_of_directory()
        return

    for meta in metas:
        name = meta.name
        video_type = meta.type
        video_id = meta.id
        tmdb_id = meta.moviedb_id
        imdb_id = meta.imdb_id

        if "tmdb" in video_id:
            tmdb_id = video_id.split(":")[1]
        elif video_id.startswith("tt"):
            imdb_id = video_id
            tmdb_id = ""

        if video_type == "series":
            if tmdb_id or imdb_id:
                ids = {"tmdb_id": tmdb_id, "tvdb_id": "", "imdb_id": imdb_id}
                url = build_url(
                    "show_seasons_details", ids=ids, mode="tv", media_type="tv"
                )
            else:
                url = build_url(
                    "list_stremio_seasons",
                    addon_url=addon_url,
                    catalog_type=catalog_type,
                    video_id=video_id,
                )

        elif video_type == "tv":
            if meta.streams:
                # Serialize streams to list of dicts for URL params
                streams_data = [asdict(s) for s in meta.streams]
                url = build_url("list_stremio_tv_streams", streams=json.dumps(streams_data))
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

        list_item = ListItem(label=name)
        info_tag = list_item.getVideoInfoTag()
        info_tag.setUniqueID(video_id, type="imdb" if video_id.startswith("tt") else "mf")
        info_tag.setTitle(name)
        info_tag.setPlot(meta.description or "")
        info_tag.setGenres(meta.genres)
        info_tag.setMediaType("video")

        is_folder = video_type != "movie"
        if not is_folder:
            list_item.setProperty("IsPlayable", "true")

        poster = meta.poster or ""
        background = meta.background or ""
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

    meta_data = response.get("meta")
    if not meta_data:
        notification("No meta available")
        return

    videos = meta_data.videos
    if not videos:
        notification("No seasons available")
        return

    available_seasons = set(
        video.imdbSeason if video.imdbSeason else video.season
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
        info_tag = list_item.getVideoInfoTag()
        info_tag.setUniqueID(
            meta_data.id, type="imdb" if meta_data.id.startswith("tt") else "mf"
        )
        info_tag.setTitle(meta_data.name)
        info_tag.setPlot(meta_data.description or "")
        info_tag.setRating(float(meta_data.imdbRating or 0))
        info_tag.setGenres(meta_data.genres)
        info_tag.setTvShowTitle(meta_data.name)
        info_tag.setSeason(season)

        list_item.setArt(
            {
                "thumb": meta_data.poster or "",
                "poster": meta_data.poster or "",
                "fanart": meta_data.poster or "",
                "icon": meta_data.poster or "",
                "banner": meta_data.background or "",
                "landscape": meta_data.background or "",
            }
        )

        addDirectoryItem(
            handle=ADDON_HANDLE, url=url, listitem=list_item, isFolder=True
        )
    end_of_directory()


def list_stremio_episodes(params):
    response = catalogs_get_cache("list_stremio_episodes", params)
    if not response:
        return

    meta_data = response.get("meta")
    if not meta_data:
        notification("No meta available")
        return

    videos = meta_data.videos
    if not videos:
        notification("No episodes available")
        return

    for video in videos:
        season = (
            int(video.imdbSeason) if video.imdbSeason else video.season
        )
        episode = (
            int(video.imdbEpisode) if video.imdbEpisode else video.episode
        )

        if season != int(params["season"]):
            continue

        title = video.title or video.name

        tv_data = {
            "name": title,
            "episode": episode,
            "season": season,
        }

        ids = {"tmdb_id": "", "tvdb_id": "", "imdb_id": ""}

        if imdb_id := meta_data.imdb_id:
            ids["imdb_id"] = imdb_id
            res = tmdb_get("find_by_imdb_id", imdb_id)
            if getattr(res, "tv_results", []):
                ids["tmdb_id"] = getattr(res, "tv_results")[0]["id"]

        if video.id.startswith("tt") and not imdb_id:
            imdb_id = meta_data.id.split(":")[0]
            ids["imdb_id"] = imdb_id
            res = tmdb_get("find_by_imdb_id", imdb_id)
            if getattr(res, "tv_results", []):
                ids["tmdb_id"] = getattr(res, "tv_results")[0]["id"]

        url = build_url(
            "search",
            mode="tv",
            media_type="tv",
            query=meta_data.name,
            ids=ids,
            tv_data=tv_data,
        )

        list_item = ListItem(label=f"{season}x{episode}. {title}")
        info_tag = list_item.getVideoInfoTag()
        info_tag.setUniqueID(
            meta_data.id, type="imdb" if meta_data.id.startswith("tt") else "mf"
        )
        info_tag.setTitle(title)
        info_tag.setPlot(video.overview or "")
        info_tag.setRating(float(meta_data.imdbRating or 0))
        info_tag.setGenres(meta_data.genres)
        info_tag.setTvShowTitle(title)
        info_tag.setSeason(season)
        info_tag.setEpisode(episode)

        list_item.setProperty("IsPlayable", "true")

        list_item.setArt(
            {
                "thumb": meta_data.poster or "",
                "poster": meta_data.poster or "",
                "fanart": meta_data.poster or "",
                "icon": meta_data.poster or "",
                "banner": meta_data.background or "",
                "landscape": meta_data.background or "",
            }
        )

        addDirectoryItem(
            handle=ADDON_HANDLE, url=url, listitem=list_item, isFolder=False
        )
    end_of_directory()


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
            data={"mode": "movie", "url": stream.url},
        )

        list_item = ListItem(label=stream.title)
        list_item.setProperty("IsPlayable", "true")
        info_tag = list_item.getVideoInfoTag()
        info_tag.setPlot(stream.description or "")

        addDirectoryItem(
            handle=ADDON_HANDLE, url=url, listitem=list_item, isFolder=False
        )
    end_of_directory()


def list_stremio_tv_streams(params):
    streams = json.loads(params.get("streams", {}))
    for stream in streams:
        url = build_url(
            "play_torrent",
            data={"mode": "movie", "url": stream["url"]},
        )

        list_item = ListItem(label=stream["name"])
        list_item.setProperty("IsPlayable", "true")
        info_tag = list_item.getVideoInfoTag()
        info_tag.setPlot(stream.get("description", ""))

        addDirectoryItem(
            handle=ADDON_HANDLE, url=url, listitem=list_item, isFolder=False
        )

    end_of_directory()
