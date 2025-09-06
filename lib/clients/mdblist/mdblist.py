from urllib.parse import quote
from lib.clients.tmdb.utils.utils import mdblist_get
from lib.utils.general.utils import build_list_item, set_pluging_category
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    build_url,
    notification,
    show_keyboard,
)

from xbmcplugin import addDirectoryItem, endOfDirectory


def search_mdbd_lists(params):
    mode = params.get("mode", "movie")
    page = int(params.get("page", 1))
    set_pluging_category("MDblist - Search Lists")

    query = ""
    # Show keyboard for search query
    query = show_keyboard(id=90006, default=query)
    if not query:
        return
    results = mdblist_get(path="search_lists", params={"query": query, "page": page})
    if not results:
        notification("No results found")
        return
    if not results:
        notification("No lists found")
        return
    for item in results:
        label = item.get("name", "Unnamed List")
        list_id = item.get("id")
        li = build_list_item(label, "mdblist.png")
        addDirectoryItem(
            ADDON_HANDLE,
            build_url("show_mdblist_list", list_id=list_id, mode=mode),
            li,
            isFolder=True,
        )
    endOfDirectory(ADDON_HANDLE)


def user_mdbd_lists(params):
    mode = params.get("mode", "movie")
    set_pluging_category("MDblist - User Lists")
    results = mdblist_get(path="get_user_lists")
    if not results:
        notification("No results found")
        return
    if not results:
        notification("No user lists found")
        return
    for item in results:
        label = item.get("name", "Unnamed List")
        list_id = item.get("id")
        li = build_list_item(label, "mdblist.png")
        addDirectoryItem(
            ADDON_HANDLE,
            build_url("show_mdblist_list", list_id=list_id, mode=mode),
            li,
            isFolder=True,
        )
    endOfDirectory(ADDON_HANDLE)


def top_mdbd_lists(params):
    mode = params.get("mode", "movie")
    set_pluging_category("MDblist - Top Lists")
    results = mdblist_get(path="top_mdbd_lists")
    if not results:
        notification("No results found")
        return
    if not results:
        notification("No top lists found")
        return
    for item in results:
        label = item.get("name", "Unnamed List")
        list_id = item.get("id")
        li = build_list_item(label, "mdblist.png")
        addDirectoryItem(
            ADDON_HANDLE,
            build_url("show_mdblist_list", list_id=list_id, mode=mode),
            li,
            isFolder=True,
        )
    endOfDirectory(ADDON_HANDLE)


def show_mdblist_list(params):
    list_id = params.get("list_id")
    mode = params.get("mode", "movie")
    offset = int(params.get("offset", 0))
    limit = int(params.get("limit", 10))
    set_pluging_category(f"MDblist List {list_id}")

    result = mdblist_get(
        "get_list_items",
        params={
            "list_id": list_id,
            "limit": limit,
            "offset": offset,
            "append_to_response": "genre,poster",
            "unified": True,
        },
    )
    if not result:
        notification("No items found in this list")
        return

    for item in result:
        li = make_li(item, mode)
        ids = {
            "tmdb_id": "",
            "tvdb_id": item.get("tvdb_id", ""),
            "imdb_id": item.get("imdb_id", ""),
        }
        if item.get("mediatype") == "show":
            url = build_url(
                "tv_seasons_details",
                ids=ids,
                mode="tv",
            )
            is_folder = True
        else:
            url = build_url(
                "search",
                mode="movies",
                query=quote(item.get("title", "")),
                ids=ids,
            )
            is_folder = False

        addDirectoryItem(
            ADDON_HANDLE,
            url,
            li,
            isFolder=is_folder,
        )

    li = build_list_item("Next Page", "nextpage.png")
    addDirectoryItem(
        ADDON_HANDLE,
        build_url(
            "show_mdblist_list",
            list_id=list_id,
            mode=mode,
            offset=offset + limit,
            limit=limit,
        ),
        li,
        isFolder=True,
    )
    endOfDirectory(ADDON_HANDLE)


def make_li(item, mode):
    label = item.get("title", "Untitled")
    genre = ", ".join(item.get("genre", [])) if item.get("genre") else ""
    poster = item.get("poster")
    li = build_list_item(label, "mdblist.png")
    if genre:
        li.setInfo("video", {"genre": genre})
    if poster:
        li.setArt({"poster": poster, "thumb": poster})
    return li
