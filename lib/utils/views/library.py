# -*- coding: utf-8 -*-
import os

from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, setContent

from lib.clients.tmdb.utils.utils import tmdb_get
from lib.db.cached import cache
from lib.db.pickle_db import PickleDatabase
from lib.jacktook.utils import kodilog
from lib.utils.general.utils import remove_from_library, set_media_infoTag, set_pluging_category
from lib.utils.kodi.utils import ADDON_HANDLE, ADDON_PATH, add_directory_items_batch, apply_section_view, build_url, end_of_directory, make_list_item, notification, translation
from lib.utils.views.last_titles import parse_time


def _library_cache_key(mode):
    return "library_view|{}".format(mode)


def _is_stremio_library_item(data):
    return data.get("source") == "stremio_catalog" or (
        data.get("addon_url")
        and data.get("catalog_type")
        and (data.get("meta_id") or data.get("ids", {}).get("original_id"))
    )


def _normalize_library_mode(mode):
    return "tv" if mode == "tv" else "movies"


def _build_stremio_details(data, mode):
    ids = data.get("ids", {})
    details = {
        "title": data.get("title", ""),
        "name": data.get("title", ""),
        "overview": data.get("overview", ""),
        "poster": data.get("poster", ""),
        "fanart": data.get("fanart", ""),
        "banner": data.get("fanart", ""),
        "landscape": data.get("fanart", ""),
        "clearart": "",
        "clearlogo": "",
        "imdb_id": ids.get("imdb_id", ""),
        "tvdb_id": ids.get("tvdb_id", ""),
        "id": ids.get("tmdb_id", "") or ids.get("original_id", ""),
        "genres": data.get("genres", []),
    }
    if mode == "tv":
        details["original_name"] = data.get("title", "")
    else:
        details["original_title"] = data.get("title", "")
    return details


def _build_tmdb_entry(title, data, mode):
    ids = data.get("ids", {})
    details_path = "tv_details" if mode == "tv" else "movie_details"
    details = tmdb_get(details_path, ids.get("tmdb_id"))
    if not details:
        return None
    return {"title": title, "data": data, "details": details, "is_stremio": False}


def _build_stremio_entry(title, data, mode):
    return {
        "title": title,
        "data": data,
        "details": _build_stremio_details(data, mode),
        "is_stremio": True,
    }


def _get_library_entries(items, mode):
    cached_entries = cache.get(_library_cache_key(mode))
    if cached_entries:
        return cached_entries

    entries = []
    for title, data in items:
        if _is_stremio_library_item(data):
            entries.append(_build_stremio_entry(title, data, mode))
            continue

        entry = _build_tmdb_entry(title, data, mode)
        if entry:
            entries.append(entry)

    cache.set(_library_cache_key(mode), entries)
    return entries


def _build_library_context_menu(title):
    remove_url = build_url("remove_from_library", title=title)
    return [(translation(90204), f"RunPlugin({remove_url})")]


def _library_mode_matches(item_mode, mode):
    if mode == "tv":
        return item_mode == "tv"
    return item_mode in ["movie", "movies"]


def _get_stremio_library_url(data, mode):
    ids = data.get("ids", {})
    meta_id = data.get("meta_id") or ids.get("original_id", "")
    if mode == "tv":
        if data.get("addon_url") and data.get("catalog_type") and meta_id:
            return build_url(
                "list_stremio_seasons",
                addon_url=data.get("addon_url"),
                catalog_type=data.get("catalog_type"),
                meta_id=meta_id,
            )
        return build_url("show_seasons_details", ids=ids, mode=mode)

    if data.get("addon_url") and data.get("catalog_type") and meta_id:
        return build_url(
            "list_stremio_movie",
            addon_url=data.get("addon_url"),
            catalog_type=data.get("catalog_type"),
            meta_id=meta_id,
            ids=data.get("ids", {}),
            title=data.get("title", ""),
            overview=data.get("overview", ""),
            poster=data.get("poster", ""),
            fanart=data.get("fanart", ""),
            genres=data.get("genres", []),
        )

    return build_url("search", mode=mode, query=data.get("title", ""), ids=ids)


def _get_library_item_url(entry, mode):
    data = entry["data"]
    ids = data.get("ids", {})
    if entry["is_stremio"]:
        return _get_stremio_library_url(data, mode)
    if mode == "tv":
        return build_url("show_seasons_details", ids=ids, mode=mode)
    return build_url("search", mode=mode, query=entry["title"], ids=ids)


def show_library_items(mode="tv"):
    category = translation(90202) if mode == "tv" else translation(90203)
    set_pluging_category(category)
    setContent(ADDON_HANDLE, mode)

    all_items = list(reversed(PickleDatabase().get_key("jt:lib").items()))
    items = []
    for title, data in all_items:
        item_mode = data.get("mode")
        if _library_mode_matches(item_mode, mode):
            items.append((title, data))

    items = sorted(items, key=parse_time, reverse=True)

    directory_items = []
    for entry in _get_library_entries(items, mode):
        title = entry["title"]
        data = entry["data"]
        details = entry["details"]

        list_item = make_list_item(label=title)
        set_media_infoTag(list_item, data=details, mode=_normalize_library_mode(mode))
        list_item.addContextMenuItems(_build_library_context_menu(title))

        # Keep a simple local fallback icon for entries without artwork.
        list_item.setArt(
            {"icon": os.path.join(ADDON_PATH, "resources", "img", "trending.png")}
        )

        item_url = _get_library_item_url(entry, mode)
        is_folder = mode == "tv"
        if mode == "movies":
            list_item.setProperty("IsPlayable", "true" if not entry["is_stremio"] else "false")
        directory_items.append((item_url, list_item, is_folder))

    add_directory_items_batch(directory_items)

    end_of_directory(cache=False)
    if mode == "tv":
        apply_section_view("view.library", content_type="tvshows", fallback="poster")
    else:
        apply_section_view("view.library", content_type="movies", fallback="poster")


def remove_library_item(params):
    title = params.get("title")
    if title:
        remove_from_library(title)
        from xbmc import executebuiltin

        executebuiltin("Container.Refresh")


def clear_library_items(params):
    mode = params.get("mode", "tv")
    pickle_db = PickleDatabase()
    library_items = dict(pickle_db.get_key("jt:lib") or {})
    titles_to_remove = []
    removed_count = 0
    for title, data in library_items.items():
        if _library_mode_matches(data.get("mode"), mode):
            titles_to_remove.append(title)
            removed_count += 1
    for title in titles_to_remove:
        pickle_db.delete_item("jt:lib", title, commit=False)
    if titles_to_remove:
        pickle_db.commit()

    cache.delete(_library_cache_key("tv"))
    cache.delete(_library_cache_key("movies"))

    if removed_count:
        notification("", translation(90692))
    else:
        notification("", translation(90693))
    return removed_count
