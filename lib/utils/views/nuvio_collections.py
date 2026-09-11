"""Read-only Nuvio Collections browser.

Renders the profile's collections as folders, each folder's sources as
catalogs. A source whose addon is installed routes to the existing catalog
viewer; a source whose addon is missing shows a clear notice instead. There is
no write support: the push endpoint is a full replace and is out of scope.
"""

from xbmcplugin import setContent

from lib.api.nuvio import NuvioClient, is_nuvio_progress_sync_enabled
from lib.clients.catalog_hub import resolve_catalog_addon
from lib.utils.general.utils import (
    add_next_button,
    set_media_infoTag,
    set_pluging_category,
)
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    add_directory_items_batch,
    apply_section_view,
    build_url,
    end_of_directory,
    kodilog,
    make_list_item,
    notification,
    translation,
)

EMPTY_COLLECTIONS_NOTIFICATION = 91052
EMPTY_DISCOVER_NOTIFICATION = 91056

# Camel-case Nuvio filter keys to their snake_case TMDB discover equivalents.
_DISCOVER_FILTER_MAP = {
    "withGenres": "with_genres",
    "withoutGenres": "without_genres",
    "withKeywords": "with_keywords",
    "withoutKeywords": "without_keywords",
    "withOriginalLanguage": "with_original_language",
    "voteCountGte": "vote_count.gte",
    "voteAverageGte": "vote_average.gte",
}

# Release-date filters map to a different TMDB key per media mode.
_DISCOVER_RELEASE_MAP = {
    "movies": {
        "releaseDateGte": "primary_release_date.gte",
        "releaseDateLte": "primary_release_date.lte",
    },
    "tv": {
        "releaseDateGte": "first_air_date.gte",
        "releaseDateLte": "first_air_date.lte",
    },
}


def has_nuvio_collections():
    """Menu condition: sync enabled. Performs no network request."""
    return is_nuvio_progress_sync_enabled()


def _load_collections():
    """Load the profile's collections; never raises into the UI."""
    try:
        collections = NuvioClient().get_collections()
    except Exception as error:
        kodilog(f"[NUVIO] collections view load failed ({type(error).__name__})")
        return []
    if collections is None:
        kodilog("[NUVIO] collections view load failed (NoneType)")
        return []
    return collections


def _find_collection(collections, collection_id):
    for collection in collections:
        if collection.get("id") == collection_id:
            return collection
    return None


def _find_folder(folders, folder_id):
    for folder in folders:
        if folder.get("id") == folder_id:
            return folder
    return None


def _find_source(sources, source_id):
    for source in sources:
        if source.get("id") == source_id:
            return source
    return None


def _discover_params(source, page):
    """Build TMDB discover params from one source's camelCase filters.

    Unknown or empty filter values are skipped; ``page`` is always present so
    the caller can forward the dict straight to ``tmdb_get``.
    """
    mode = "tv" if source.get("media_type") == "tv" else "movies"
    params = {}
    filters = source.get("filters")
    if isinstance(filters, dict):
        mapping = dict(_DISCOVER_FILTER_MAP)
        mapping.update(_DISCOVER_RELEASE_MAP[mode])
        for source_key, tmdb_key in mapping.items():
            value = filters.get(source_key)
            if value is None or value == "":
                continue
            params[tmdb_key] = value

    sort_by = source.get("sort_by") or ""
    if sort_by:
        params["sort_by"] = sort_by
    params["page"] = page
    return params


def _set_art(list_item, image):
    if image:
        list_item.setArt({"thumb": image, "fanart": image, "icon": image})


def show_nuvio_collections(params):
    collections = _load_collections()
    set_pluging_category(translation(91051))
    setContent(ADDON_HANDLE, "files")

    directory_items = []
    for collection in collections:
        label = collection.get("title") or collection.get("id") or ""
        list_item = make_list_item(label=label)
        _set_art(list_item, collection.get("backdrop"))
        url = build_url(
            "nuvio_collection_folders",
            collection_id=collection.get("id"),
        )
        directory_items.append((url, list_item, True))

    add_directory_items_batch(directory_items)
    end_of_directory(cache=False)
    apply_section_view("view.main")

    if not directory_items:
        notification(translation(EMPTY_COLLECTIONS_NOTIFICATION))


def show_nuvio_collection_folders(params):
    params = params or {}
    collection_id = params.get("collection_id")
    collections = _load_collections()
    collection = _find_collection(collections, collection_id)
    if collection is None:
        end_of_directory(cache=False)
        return

    set_pluging_category(collection.get("title") or translation(91051))
    setContent(ADDON_HANDLE, "files")

    directory_items = []
    for folder in collection.get("folders") or []:
        title = folder.get("title") or folder.get("id") or ""
        cover = folder.get("cover") or ""
        emoji = folder.get("emoji") or ""
        label = f"{emoji} {title}" if emoji and not cover else title
        list_item = make_list_item(label=label)
        _set_art(list_item, cover)
        url = build_url(
            "nuvio_collection_sources",
            collection_id=collection_id,
            folder_id=folder.get("id"),
        )
        directory_items.append((url, list_item, True))

    add_directory_items_batch(directory_items)
    end_of_directory(cache=False)
    apply_section_view("view.main")

    if not directory_items:
        notification(translation(EMPTY_COLLECTIONS_NOTIFICATION))


def show_nuvio_collection_sources(params):
    params = params or {}
    collection_id = params.get("collection_id")
    folder_id = params.get("folder_id")
    collections = _load_collections()
    collection = _find_collection(collections, collection_id)
    if collection is None:
        end_of_directory(cache=False)
        return
    folder = _find_folder(collection.get("folders") or [], folder_id)
    if folder is None:
        end_of_directory(cache=False)
        return

    set_pluging_category(folder.get("title") or translation(91051))
    setContent(ADDON_HANDLE, "files")

    directory_items = []
    for source in folder.get("sources") or []:
        label = source.get("label") or source.get("catalog_id") or ""
        list_item = make_list_item(label=label)

        kind = source.get("kind")
        if kind == "addon":
            addon_id = source.get("addon_id") or ""
            addon = None
            if addon_id:
                try:
                    addon = resolve_catalog_addon(addon_key=addon_id)
                except Exception as error:
                    kodilog(f"[NUVIO] collections addon resolve failed ({type(error).__name__})")
                    addon = None

            provider = source.get("provider") or ""
            if addon is not None and not (provider and provider != "addon"):
                url = build_url(
                    "list_catalog",
                    addon_key=addon.key(),
                    menu_type=source.get("type"),
                    catalog_type=source.get("type"),
                    catalog_id=source.get("catalog_id"),
                )
                is_folder = True
            else:
                url = build_url("nuvio_collection_source_unavailable")
                is_folder = False
        elif kind == "tmdb":
            url = build_url(
                "nuvio_collection_discover",
                collection_id=collection_id,
                folder_id=folder_id,
                source_id=source.get("id"),
                page=1,
            )
            is_folder = True
        else:
            url = build_url(
                "nuvio_collection_source_unavailable",
                reason="unsupported",
            )
            is_folder = False
        directory_items.append((url, list_item, is_folder))

    add_directory_items_batch(directory_items)
    end_of_directory(cache=False)
    apply_section_view("view.main")

    if not directory_items:
        notification(translation(EMPTY_COLLECTIONS_NOTIFICATION))


def show_nuvio_collection_discover(params):
    """Render one TMDB discover page for a tmdb-family collection source."""
    params = params or {}
    collection_id = params.get("collection_id")
    folder_id = params.get("folder_id")
    source_id = params.get("source_id")
    try:
        page = int(params.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    if page < 1:
        page = 1

    collections = _load_collections()
    collection = _find_collection(collections, collection_id)
    if collection is None:
        end_of_directory(cache=False)
        return
    folder = _find_folder(collection.get("folders") or [], folder_id)
    if folder is None:
        end_of_directory(cache=False)
        return
    source = _find_source(folder.get("sources") or [], source_id)
    if source is None or source.get("kind") != "tmdb":
        end_of_directory(cache=False)
        return

    mode = "tv" if source.get("media_type") == "tv" else "movies"
    set_pluging_category(source.get("label") or translation(91051))
    setContent(ADDON_HANDLE, "tvshows" if mode == "tv" else "movies")

    from lib.clients.tmdb.utils.utils import tmdb_get

    tmdb_params = _discover_params(source, page)
    data = tmdb_get("discover_tv" if mode == "tv" else "discover_movie", tmdb_params)
    if not data or getattr(data, "total_results", 0) == 0:
        notification(translation(EMPTY_DISCOVER_NOTIFICATION))
        end_of_directory(cache=False)
        return

    from lib.clients.tmdb.base import BaseTmdbClient
    from lib.clients.tmdb.tmdb import TmdbClient

    directory_items = []
    for res in getattr(data, "results", []):
        metadata = TmdbClient._get_cached_tmdb_item_metadata(res, mode)
        title = getattr(res, "name", "") or getattr(res, "title", "")
        tmdb_id = getattr(res, "id", "")
        media_type = getattr(res, "media_type", "") or ""
        list_item = make_list_item(label=title)
        set_media_infoTag(list_item, data=metadata, mode=mode)
        item_tuple = BaseTmdbClient.add_media_directory_item(
            list_item=list_item,
            mode=mode,
            title=title,
            ids={"tmdb_id": tmdb_id},
            media_type=media_type,
            batch=True,
        )
        directory_items.append(item_tuple)
    add_directory_items_batch(directory_items)

    total_pages = getattr(data, "total_pages", 0) or 0
    if page < total_pages:
        add_next_button(
            "nuvio_collection_discover",
            page=page,
            collection_id=collection_id,
            folder_id=folder_id,
            source_id=source_id,
        )
    end_of_directory(cache=False)
    apply_section_view("view.main")
