import json
from datetime import datetime
from dataclasses import asdict
from time import perf_counter
from lib.clients.stremio.helpers import (
    get_addon_by_base_url,
    get_selected_catalogs_addons,
    get_selected_tv_addons,
)
from lib.clients.tmdb.utils.utils import (
    add_tmdb_episode_context_menu,
    add_tmdb_movie_context_menu,
    add_tmdb_show_context_menu,
)
from lib.clients.tmdb.utils.utils import tmdb_get
from lib.utils.general.utils import add_next_button
from lib.db.cached import cache
from lib.db.pickle_db import PickleDatabase
from lib.utils.stremio.catalogs_utils import catalogs_get_cache
from lib.utils.kodi.utils import (
    build_url,
    container_update,
    end_of_directory,
    kodi_play_media,
    notification,
    show_keyboard,
    kodilog,
    translation,
)
from lib.utils.general.utils import info_hash_to_magnet, IndexerType

from xbmcplugin import addDirectoryItem, setContent
from xbmcgui import ListItem
from lib.utils.kodi.utils import ADDON_HANDLE


CATALOG_PAGE_SIZE = 25


def _build_stremio_ids(meta_id, tmdb_id="", imdb_id=""):
    return {
        "tmdb_id": tmdb_id or "",
        "tvdb_id": "",
        "imdb_id": imdb_id or "",
        "original_id": meta_id if ":" in str(meta_id or "") else "",
    }


def _build_stremio_meta_payload(
    *,
    name,
    meta_type,
    meta_id,
    tmdb_id="",
    imdb_id="",
    overview="",
    poster="",
    fanart="",
    genres=None,
    addon_url="",
    catalog_type="",
    meta_id_for_nav="",
    tv_data=None,
):
    return {
        "source": "stremio_catalog",
        "title": name,
        "overview": overview or "",
        "poster": poster or "",
        "fanart": fanart or poster or "",
        "genres": genres or [],
        "ids": _build_stremio_ids(meta_id, tmdb_id, imdb_id),
        "mode": "tv" if meta_type in ["series", "anime"] else "movies",
        "addon_url": addon_url,
        "catalog_type": catalog_type,
        "meta_id": meta_id_for_nav or meta_id,
        "tv_data": tv_data or {},
        "timestamp": datetime.now().strftime("%a, %d %b %Y %I:%M %p"),
    }


def _has_reliable_tmdb_ids(ids):
    return bool((ids or {}).get("tmdb_id"))


def _resolve_tmdb_ids_for_context_menu(ids, meta_type):
    if _has_reliable_tmdb_ids(ids):
        return ids

    imdb_id = (ids or {}).get("imdb_id")
    if not imdb_id:
        return ids

    result = cache.get(f"find_by_imdb_id|{imdb_id}")
    if not result:
        return ids

    resolved_tmdb_id = ""
    if meta_type == "movie":
        movie_results = getattr(result, "movie_results", []) or []
        if movie_results:
            resolved_tmdb_id = str(movie_results[0].get("id", ""))
    elif meta_type in ["series", "anime"]:
        tv_results = getattr(result, "tv_results", []) or []
        if tv_results:
            resolved_tmdb_id = str(tv_results[0].get("id", ""))

    if not resolved_tmdb_id:
        return ids

    resolved_ids = dict(ids or {})
    resolved_ids["tmdb_id"] = resolved_tmdb_id
    return resolved_ids


def _filter_tmdb_context_menu(context_menu):
    excluded_labels = {translation(90205), translation(90116)}
    return [item for item in context_menu if item[0] not in excluded_labels]


def _build_stremio_library_menu_item(payload):
    return (
        translation(90205),
        kodi_play_media(name="add_to_library", data=json.dumps(payload)),
    )


def _build_stremio_settings_menu_item():
    return (
        translation(90116),
        container_update(name="settings"),
    )


def _append_context_menu_items(list_item, context_menu):
    if not context_menu:
        return
    list_item.addContextMenuItems(context_menu, False)


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
                listitem = ListItem(label=f"{translation(90006)} {catalog_name}")
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


def _get_manifest_catalog(addon_url, catalog_type, catalog_id):
    addon = get_addon_by_base_url(addon_url)
    if not addon:
        return None

    for catalog in addon.manifest.catalogs:
        if catalog.type == catalog_type and catalog.id == catalog_id:
            return catalog

    return None


def _catalog_supports_extra(addon_url, catalog_type, catalog_id, extra_name):
    catalog = _get_manifest_catalog(addon_url, catalog_type, catalog_id)
    if not catalog:
        return False

    return any(extra.get("name") == extra_name for extra in (catalog.extra or []))


def list_catalog(params):
    total_start = perf_counter()
    content_type = "movies" if params["menu_type"] == "movie" else "tvshows"
    setContent(ADDON_HANDLE, content_type)

    skip = int(params.get("skip", 0))

    extras = {}
    # Common Stremio extra params
    for key in ["genre", "search"]:
        if key in params:
            extras[key] = params[key]

    supports_skip = _catalog_supports_extra(
        params["addon_url"], params["catalog_type"], params["catalog_id"], "skip"
    )

    request_kwargs = dict(extras)
    if supports_skip and skip:
        request_kwargs["skip"] = skip

    kodilog(
        "Stremio list_catalog start: addon={!r} catalog={!r}/{!r} menu_type={!r} skip={} supports_skip={} extras={}".format(
            params.get("addon_url", ""),
            params.get("catalog_type", ""),
            params.get("catalog_id", ""),
            params.get("menu_type", ""),
            skip,
            supports_skip,
            request_kwargs,
        )
    )

    fetch_start = perf_counter()
    response = catalogs_get_cache("list_catalog", params, **request_kwargs)
    fetch_elapsed_ms = (perf_counter() - fetch_start) * 1000
    if not response:
        kodilog(
            f"Stremio list_catalog empty response: fetch_ms={fetch_elapsed_ms:.1f}"
        )
        end_of_directory()
        return

    metas = response.get("metas", [])
    total_metas = len(metas)

    if not supports_skip:
        metas = metas[skip : skip + CATALOG_PAGE_SIZE]

    if not metas:
        notification(translation(90516))
        end_of_directory()
        return

    render_start = perf_counter()
    add_meta_items(metas, params)
    render_elapsed_ms = (perf_counter() - render_start) * 1000

    has_next_page = False
    if supports_skip:
        has_next_page = len(metas) >= CATALOG_PAGE_SIZE
    else:
        has_next_page = total_metas > skip + len(metas)

    if has_next_page:
        next_url = build_url(
            "list_catalog",
            addon_url=params["addon_url"],
            menu_type=params["menu_type"],
            sub_menu_type=params.get("sub_menu_type", ""),
            catalog_type=params["catalog_type"],
            catalog_id=params["catalog_id"],
            skip=skip + len(metas),
        )
        list_item = ListItem(label=translation(90515))
        addDirectoryItem(
            handle=ADDON_HANDLE, url=next_url, listitem=list_item, isFolder=True
        )

    total_elapsed_ms = (perf_counter() - total_start) * 1000
    kodilog(
        "Stremio list_catalog complete: addon={!r} catalog={!r}/{!r} fetched={} rendered={} fetch_ms={:.1f} render_ms={:.1f} total_ms={:.1f}".format(
            params.get("addon_url", ""),
            params.get("catalog_type", ""),
            params.get("catalog_id", ""),
            total_metas,
            len(metas),
            fetch_elapsed_ms,
            render_elapsed_ms,
            total_elapsed_ms,
        )
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
                    meta_id=meta.id,
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


def _addon_has_resource(addon, resource_name, content_type):
    if not addon:
        return False
    for resource in addon.manifest.resources:
        if resource.name == resource_name and content_type in resource.types:
            return True
    return False


def addon_has_meta(addon_url, content_type, addon=None):
    """Check if the addon serves its own meta (seasons/episodes) for the given type."""
    addon = addon or get_addon_by_base_url(addon_url)
    return _addon_has_resource(addon, "meta", content_type)


def addon_has_stream(addon_url, content_type, addon=None):
    """Check if the addon serves its own streams for the given type."""
    addon = addon or get_addon_by_base_url(addon_url)
    return _addon_has_resource(addon, "stream", content_type)


def add_meta_items(metas, params):
    start = perf_counter()
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
        notification(f"{translation(90511)} {menu_type}")
        end_of_directory()
        return

    addon = get_addon_by_base_url(addon_url)
    has_meta_resource = addon_has_meta(addon_url, catalog_type, addon=addon)
    has_stream_resource = addon_has_stream(addon_url, catalog_type, addon=addon)

    tmdb_id_count = 0
    imdb_only_count = 0
    no_external_id_count = 0

    for meta in metas:
        name = meta.name
        meta_type = meta.type
        meta_id = meta.id
        tmdb_id = meta.moviedb_id
        imdb_id = meta.imdb_id

        if "tmdb" in meta_id:
            tmdb_id = meta_id.split(":")[1]
        elif meta_id.startswith("tt"):
            imdb_id = meta_id
            tmdb_id = ""

        if tmdb_id:
            tmdb_id_count += 1
        elif imdb_id:
            imdb_only_count += 1
        else:
            no_external_id_count += 1

        ids = _build_stremio_ids(meta_id, tmdb_id, imdb_id)
        poster = meta.poster or ""
        background = meta.background or ""
        library_payload = _build_stremio_meta_payload(
            name=name,
            meta_type=meta_type,
            meta_id=meta_id,
            tmdb_id=tmdb_id,
            imdb_id=imdb_id,
            overview=meta.description or "",
            poster=poster,
            fanart=background,
            genres=meta.genres,
            addon_url=addon_url,
            catalog_type=catalog_type,
            meta_id_for_nav=meta_id,
        )

        if meta_type == "series":
            if has_meta_resource:
                url = build_url(
                    "list_stremio_seasons",
                    addon_url=addon_url,
                    catalog_type=catalog_type,
                    meta_id=meta_id,
                )
            elif tmdb_id or imdb_id:
                url = build_url(
                    "show_seasons_details", ids=ids, mode="tv", media_type="tv"
                )
            else:
                url = build_url(
                    "list_stremio_seasons",
                    addon_url=addon_url,
                    catalog_type=catalog_type,
                    meta_id=meta_id,
                )
        elif meta_type == "movie":
            if has_stream_resource:
                is_custom_movie = True
                url = build_url(
                    "list_stremio_movie",
                    addon_url=addon_url,
                    catalog_type=catalog_type,
                    meta_id=meta_id,
                    ids=json.dumps(ids),
                    title=name,
                    overview=meta.description or "",
                    poster=poster,
                    fanart=background,
                    genres=json.dumps(meta.genres or []),
                )
            elif tmdb_id or imdb_id or ":" in meta_id:
                is_custom_movie = False
                url = build_url("search", mode="movies", query=name, ids=ids)
            else:
                is_custom_movie = True
                url = build_url(
                    "list_stremio_movie",
                    addon_url=addon_url,
                    catalog_type=catalog_type,
                    meta_id=meta_id,
                    ids=json.dumps(ids),
                    title=name,
                    overview=meta.description or "",
                    poster=poster,
                    fanart=background,
                    genres=json.dumps(meta.genres or []),
                )
        elif meta_type == "tv":
            if meta.streams:
                streams_data = [asdict(s) for s in meta.streams]
                url = build_url(
                    "list_stremio_tv_streams",
                    streams=json.dumps(streams_data),
                    ids=json.dumps(ids),
                    title=name,
                    overview=meta.description or "",
                    poster=poster,
                    fanart=background,
                    genres=json.dumps(meta.genres or []),
                    addon_url=addon_url,
                    catalog_type=catalog_type,
                    meta_id=meta_id,
                )
            else:
                url = build_url(
                    "list_stremio_tv",
                    addon_url=addon_url,
                    catalog_type=catalog_type,
                    meta_id=meta_id,
                    ids=json.dumps(ids),
                    title=name,
                    overview=meta.description or "",
                    poster=poster,
                    fanart=background,
                    genres=json.dumps(meta.genres or []),
                )
        else:
            continue

        list_item = ListItem(label=name)
        info_tag = list_item.getVideoInfoTag()
        info_tag.setUniqueID(meta_id, type="imdb" if meta_id.startswith("tt") else "mf")
        info_tag.setTitle(name)
        info_tag.setPlot(meta.description or "")
        info_tag.setGenres(meta.genres)
        info_tag.setMediaType("video")

        is_folder = meta_type != "movie" or (meta_type == "movie" and is_custom_movie)
        if not is_folder:
            list_item.setProperty("IsPlayable", "true")

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

        context_menu_ids = _resolve_tmdb_ids_for_context_menu(ids, meta_type)

        context_menu = [
            _build_stremio_library_menu_item(library_payload),
            _build_stremio_settings_menu_item(),
        ]
        if _has_reliable_tmdb_ids(context_menu_ids):
            if meta_type == "movie":
                context_menu.extend(
                    _filter_tmdb_context_menu(
                        add_tmdb_movie_context_menu(
                            mode="movies",
                            media_type="movie",
                            title=name,
                            ids=context_menu_ids,
                        )
                    )
                )
            elif meta_type in ["series", "anime"]:
                context_menu.extend(
                    _filter_tmdb_context_menu(
                        add_tmdb_show_context_menu(
                            mode="tv", ids=context_menu_ids, title=name
                        )
                    )
                )

        _append_context_menu_items(list_item, context_menu)

        addDirectoryItem(
            handle=ADDON_HANDLE, url=url, listitem=list_item, isFolder=is_folder
        )

    elapsed_ms = (perf_counter() - start) * 1000
    kodilog(
        "Stremio add_meta_items complete: addon={!r} catalog={!r} count={} tmdb_ids={} imdb_only={} no_external_ids={} elapsed_ms={:.1f}".format(
            addon_url,
            catalog_type,
            len(metas),
            tmdb_id_count,
            imdb_only_count,
            no_external_id_count,
            elapsed_ms,
        )
    )


def list_stremio_seasons(params):
    kodilog("list_stremio_seasons")
    response = catalogs_get_cache("list_stremio_seasons", params)
    if not response:
        return

    meta_data = response.get("meta")
    if not meta_data:
        notification(translation(90517))
        return

    videos = meta_data.videos
    if not videos:
        notification(translation(90517))
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
            meta_id=params["meta_id"],
            season=season,
        )
        list_item = ListItem(label=f"{translation(90512)} {season}")
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
    kodilog("list_stremio_episodes")
    total_start = perf_counter()
    response = catalogs_get_cache("list_stremio_episodes", params)
    if not response:
        return

    meta_data = response.get("meta")
    if not meta_data:
        notification(translation(90510))
        return

    videos = meta_data.videos
    if not videos:
        notification(translation(90513))
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

    addon = get_addon_by_base_url(params["addon_url"])
    has_stream_resource = addon_has_stream(
        params["addon_url"], params["catalog_type"], addon=addon
    )
    rendered_count = 0

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

        title = video.title or getattr(video, "name", "") or meta_data.name

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

        scoped_addon_url = params["addon_url"] if has_stream_resource else ""

        url = build_url(
            "search",
            mode="tv",
            media_type="tv",
            query=meta_data.name,
            ids=ids,
            tv_data=tv_data,
            scoped_addon_url=scoped_addon_url,
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

        context_menu = [
            _build_stremio_library_menu_item(
                _build_stremio_meta_payload(
                    name=meta_data.name,
                    meta_type="series",
                    meta_id=meta_data.id,
                    tmdb_id=tmdb_id,
                    imdb_id=imdb_id,
                    overview=meta_data.description or video.overview or "",
                    poster=meta_data.poster or video.thumbnail or "",
                    fanart=meta_data.background or meta_data.poster or video.thumbnail or "",
                    genres=meta_data.genres,
                    addon_url=params["addon_url"],
                    catalog_type=params["catalog_type"],
                    meta_id_for_nav=params["meta_id"],
                    tv_data=tv_data,
                )
            ),
            _build_stremio_settings_menu_item(),
        ]
        context_menu_ids = _resolve_tmdb_ids_for_context_menu(ids, "series")
        if _has_reliable_tmdb_ids(context_menu_ids):
            context_menu = _filter_tmdb_context_menu(
                add_tmdb_episode_context_menu(
                    mode="tv",
                    tv_name=meta_data.name,
                    tv_data=tv_data,
                    ids=context_menu_ids,
                )
            ) + context_menu
        else:
            context_menu.insert(
                0,
                (
                    translation(90049),
                    kodi_play_media(
                        name="search",
                        mode="tv",
                        media_type="tv",
                        query=meta_data.name,
                        ids=ids,
                        tv_data=tv_data,
                        scoped_addon_url=scoped_addon_url,
                        rescrape=True,
                    ),
                ),
            )
        _append_context_menu_items(list_item, context_menu)

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
        rendered_count += 1

    total_elapsed_ms = (perf_counter() - total_start) * 1000
    kodilog(
        "Stremio list_stremio_episodes complete: addon={!r} catalog={!r} season={} rendered={} has_stream_resource={} tmdb_id={!r} imdb_id={!r} total_ms={:.1f}".format(
            params.get("addon_url", ""),
            params.get("catalog_type", ""),
            params.get("season", ""),
            rendered_count,
            has_stream_resource,
            tmdb_id,
            imdb_id,
            total_elapsed_ms,
        )
    )
    end_of_directory()


def list_stremio_movie(params):
    response = catalogs_get_cache("list_stremio_movie", params)
    if not response:
        return

    streams = response.get("streams", [])
    if not streams:
        notification(translation(90514))
        return

    for stream in streams:
        playback_data = {
            "mode": "movie",
            "source": "stremio_catalog",
            "title": stream.title,
            "overview": stream.description or params.get("overview", ""),
            "poster": params.get("poster", ""),
            "fanart": params.get("fanart", params.get("poster", "")),
            "genres": json.loads(params.get("genres", "[]") or "[]"),
            "ids": json.loads(params.get("ids", "{}") or "{}"),
            "addon_url": params.get("addon_url", ""),
            "catalog_type": params.get("catalog_type", ""),
            "meta_id": params.get("meta_id", ""),
        }

        if stream.url:
            if stream.url.startswith("magnet:"):
                playback_data["magnet"] = stream.url
                playback_data["is_torrent"] = True
            else:
                playback_data["url"] = stream.url
                playback_data["type"] = IndexerType.DIRECT
        elif stream.infoHash:
            playback_data["magnet"] = info_hash_to_magnet(stream.infoHash)
            playback_data["info_hash"] = stream.infoHash
            playback_data["is_torrent"] = True
        else:
            continue

        url = build_url(
            "play_media",
            data=json.dumps(playback_data),
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
        notification(translation(90514))
        return

    for stream in streams:
        playback_data = {
            "mode": "movie",
            "url": stream.url,
            "type": IndexerType.DIRECT,
            "source": "stremio_catalog",
            "title": stream.title,
            "overview": stream.description or params.get("overview", ""),
            "poster": params.get("poster", ""),
            "fanart": params.get("fanart", params.get("poster", "")),
            "genres": json.loads(params.get("genres", "[]") or "[]"),
            "ids": json.loads(params.get("ids", "{}") or "{}"),
            "addon_url": params.get("addon_url", ""),
            "catalog_type": params.get("catalog_type", ""),
            "meta_id": params.get("meta_id", ""),
        }
        url = build_url(
            "play_media",
            data=json.dumps(playback_data),
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
        playback_data = {
            "mode": "movie",
            "url": stream["url"],
            "type": IndexerType.DIRECT,
            "source": "stremio_catalog",
            "title": stream["name"],
            "overview": stream.get("description", "") or params.get("overview", ""),
            "poster": params.get("poster", ""),
            "fanart": params.get("fanart", params.get("poster", "")),
            "genres": json.loads(params.get("genres", "[]") or "[]"),
            "ids": json.loads(params.get("ids", "{}") or "{}"),
            "addon_url": params.get("addon_url", ""),
            "catalog_type": params.get("catalog_type", ""),
            "meta_id": params.get("meta_id", ""),
        }
        url = build_url(
            "play_media",
            data=json.dumps(playback_data),
        )

        list_item = ListItem(label=stream["name"])
        list_item.setProperty("IsPlayable", "true")
        info_tag = list_item.getVideoInfoTag()
        info_tag.setPlot(stream.get("description", ""))

        addDirectoryItem(
            handle=ADDON_HANDLE, url=url, listitem=list_item, isFolder=False
        )

    end_of_directory()
