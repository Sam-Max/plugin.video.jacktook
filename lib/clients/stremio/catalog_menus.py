from lib.utils.kodi.utils import ADDON_HANDLE
import json
from dataclasses import asdict
from lib.clients.stremio.helpers import (
    get_selected_catalogs_addons,
    get_selected_tv_addons,
)
from lib.clients.tmdb.utils.utils import tmdb_get
from lib.utils.general.utils import add_next_button
from lib.db.pickle_db import PickleDatabase
from lib.utils.stremio.catalogs_utils import catalogs_get_cache
from lib.utils.kodi.utils import (
    build_url,
    end_of_directory,
    notification,
    show_keyboard,
    kodilog,
)
from lib.utils.general.utils import info_hash_to_magnet

from xbmcplugin import addDirectoryItem, setContent
from xbmcgui import ListItem


def list_stremio_catalogs(menu_type="", sub_menu_type=""):
    if menu_type == "tv":
        selected_addons = get_selected_tv_addons()
    else:
        selected_addons = get_selected_catalogs_addons()

    if not selected_addons:
        kodilog(f"No addons found for menu_type={menu_type}")
        return

    for addon in selected_addons:
        addon_name = addon.manifest.name
        addon_types = addon.manifest.types

        kodilog(f"Addon url: {addon.url()}")

        if menu_type not in addon_types:
            continue

        for catalog in addon.manifest.catalogs:
            catalog_name = catalog.name
            catalog_id = catalog.id
            catalog_type = catalog.type

            target_type = sub_menu_type if sub_menu_type else menu_type

            # Allow 'anime' catalogs when target is 'series' and we are in 'anime' menu
            allowed_types = [target_type]
            if menu_type == "anime" and target_type == "series":
                allowed_types.append("anime")

            if (
                target_type in ["movie", "series", "tv"]
                and catalog_type not in allowed_types
            ):
                continue

            search_capabilities = any(
                extra.get("name") == "search" for extra in catalog.extra
            )

            if search_capabilities:
                listitem = ListItem(label=f"Search {catalog_name}")
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

    extras = {}
    # Common Stremio extra params
    for key in ["genre", "search"]:
        if key in params:
            extras[key] = params[key]

    response = catalogs_get_cache("list_catalog", params, skip=skip, **extras)
    kodilog(f"Response: {response}")
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
        info_tag.setUniqueID(meta.id, type="imdb" if meta.id.startswith("tt") else "mf")
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
    kodilog(f"Add meta items")
    kodilog(f"Params: {params}")
    kodilog(f"Metas: {metas}")
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
            return meta_type in ["series", "anime"]
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
                streams_data = [asdict(s) for s in meta.streams]
                url = build_url(
                    "list_stremio_tv_streams", streams=json.dumps(streams_data)
                )
            else:
                url = build_url(
                    "list_stremio_tv",
                    addon_url=addon_url,
                    catalog_type=catalog_type,
                    video_id=video_id,
                )

        elif video_type == "movie":
            if not tmdb_id and not imdb_id and ":" in video_id:
                is_custom_movie = True
                url = build_url(
                    "list_stremio_movie",
                    addon_url=addon_url,
                    catalog_type=catalog_type,
                    video_id=video_id,
                )
            else:
                is_custom_movie = False
                ids = {"tmdb_id": tmdb_id, "tvdb_id": "", "imdb_id": imdb_id}
                url = build_url("search", mode="movies", query=name, ids=ids)
        else:
            continue

        list_item = ListItem(label=name)
        info_tag = list_item.getVideoInfoTag()
        info_tag.setUniqueID(
            video_id, type="imdb" if video_id.startswith("tt") else "mf"
        )
        info_tag.setTitle(name)
        info_tag.setPlot(meta.description or "")
        info_tag.setGenres(meta.genres)
        info_tag.setMediaType("video")

        is_folder = video_type != "movie" or (video_type == "movie" and is_custom_movie)
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
        int(video.imdbSeason) if video.imdbSeason else int(video.season)
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

    # Resolve IDs once for the show
    tmdb_id = ""
    imdb_id = ""
    # Store original ID (e.g. kitsu:123) for addons that support it
    original_id = meta_data.id if ":" in meta_data.id else ""

    if meta_data.imdb_id:
        imdb_id = meta_data.imdb_id
        res = tmdb_get("find_by_imdb_id", imdb_id)
        if getattr(res, "tv_results", []):
            tmdb_id = str(getattr(res, "tv_results")[0]["id"])

    if not tmdb_id and not imdb_id and meta_data.name:
        kodilog(f"No IDs found for {meta_data.name}. Searching TMDB...")
        year = meta_data.releaseInfo.split("-")[0] if meta_data.releaseInfo else ""
        results = tmdb_get(
            "search_tv", {"query": meta_data.name, "page": 1, "year": year}
        )
        if results and results.results:
            try:
                tmdb_id = str(results.results[0].id)
                kodilog(f"Fallback found TMDB ID: {tmdb_id} for {meta_data.name}")
            except Exception:
                pass

    if tmdb_id and not imdb_id:
        details = tmdb_get("tv_details", tmdb_id)
        if details and getattr(details, "external_ids", None):
            imdb_id = details.external_ids.get("imdb_id", "")
            kodilog(f"Resolved IMDB ID: {imdb_id} from TMDB ID: {tmdb_id}")

    for video in videos:
        try:
            season = int(video.imdbSeason) if video.imdbSeason else int(video.season)
            episode = (
                int(video.imdbEpisode) if video.imdbEpisode else int(video.episode)
            )
        except (ValueError, TypeError):
            continue

        if season != int(params["season"]):
            continue

        title = video.title or video.name

        tv_data = {
            "name": title,
            "episode": episode,
            "season": season,
        }

        ids = {
            "tmdb_id": tmdb_id,
            "tvdb_id": "",
            "imdb_id": imdb_id,
            "original_id": original_id,
        }

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


def list_stremio_movie(params):
    response = catalogs_get_cache("list_stremio_movie", params)
    if not response:
        return

    streams = response.get("streams", [])
    if not streams:
        notification("No videos available")
        return

    for stream in streams:
        playback_data = {"mode": "movie"}

        if stream.url:
            if stream.url.startswith("magnet:"):
                playback_data["magnet"] = stream.url
                playback_data["is_torrent"] = True
            else:
                playback_data["url"] = stream.url
        elif stream.infoHash:
            playback_data["magnet"] = info_hash_to_magnet(stream.infoHash)
            playback_data["info_hash"] = stream.infoHash
            playback_data["is_torrent"] = True
        else:
            continue

        url = build_url(
            "play_media",
            data=playback_data,
        )

        list_item = ListItem(label=stream.title)
        list_item.setProperty("IsPlayable", "true")
        info_tag = list_item.getVideoInfoTag()
        info_tag.setPlot(stream.description or "")

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
            "play_media",
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
            "play_media",
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
