from lib.clients.jackgram.client import Jackgram
from lib.clients.tmdb.utils.utils import tmdb_get
from lib.utils.clients.utils import validate_host
from lib.utils.general.utils import (
    Indexer,
    add_next_button,
    build_list_item,
    execute_thread_pool,
    set_content_type,
    set_media_infoTag,
    set_watched_title,
)

from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    build_url,
    get_setting,
    kodilog,
    notification,
    set_view,
)

from xbmcplugin import addDirectoryItem, endOfDirectory
from xbmcgui import ListItem
import xbmc
import json


def check_jackgram_active():
    jackgram_enabled = get_setting("jackgram_enabled")
    if not jackgram_enabled:
        notification("Jackgram indexer not activated.")
        return False
    return True


def check_and_get_jackgram_client():
    if not check_jackgram_active():
        return None
    host = str(get_setting("jackgram_host"))
    if not validate_host(host, Indexer.TELEGRAM):
        return None
    return Jackgram(host, notification)


def list_telegram_files(query):
    page = int(query.get("page"))
    jackgram_client = check_and_get_jackgram_client()
    if not jackgram_client:
        return
    results = jackgram_client.get_files(page=page)
    process_results(results, add_telegram_file_item, "list_telegram_files", page)


def add_telegram_file_item(item):
    list_item = build_list_item(item["file_name"], icon="trending.png")
    list_item.setProperty("IsPlayable", "true")
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("play_torrent", data=item),
        list_item,
        isFolder=False,
    )


def list_telegram_latest(query):
    page = int(query.get("page"))
    jackgram_client = check_and_get_jackgram_client()
    if not jackgram_client:
        return
    results = jackgram_client.get_latest(page=page)
    process_results(results, add_telegram_latest_item, "list_telegram_latest", page)


def add_telegram_latest_item(entry):
    mode = entry["type"]
    title = entry["title"]
    tmdb_id = entry["tmdb_id"]

    details = tmdb_get(f"{mode}_details", tmdb_id)
    if details is None:
        kodilog(f"Failed to get details for {mode} with ID {tmdb_id}")
        return

    imdb_id = getattr(details, "external_ids").get("imdb_id")
    tvdb_id = getattr(details, "external_ids").get("tvdb_id")
    entry["ids"] = {"tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id}

    list_item = ListItem(label=title)
    set_media_infoTag(list_item, data=details, mode=mode)

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("list_telegram_latest_files", data=json.dumps(entry)),
        list_item,
        isFolder=True,
    )


def list_telegram_latest_files(query):
    parent_data = json.loads(query["data"])
    set_watched_title(
        title=parent_data["title"],
        ids=parent_data["ids"],
        tg_data=parent_data,
        mode="tg_latest",
    )
    set_content_type(parent_data["type"])
    execute_thread_pool(
        parent_data["files"], add_telegram_latest_file_item, parent_data
    )
    endOfDirectory(ADDON_HANDLE)


def add_telegram_latest_file_item(file_entry, parent_data):
    mode = file_entry["mode"]
    title = file_entry["title"]

    list_item = ListItem(label=title)
    if mode == "tv":
        details = tmdb_get(
            "episode_details",
            params={
                "id": parent_data["tmdb_id"],
                "season": file_entry["season"],
                "episode": file_entry["episode"],
            },
        )
    else:
        details = tmdb_get("movie_details", parent_data["tmdb_id"])

    list_item.setProperty("IsPlayable", "true")
    set_media_infoTag(list_item, data=details, mode=mode)

    merged_data = {**parent_data, **file_entry}

    kodilog(f"Adding Telegram file item: {merged_data}", level=xbmc.LOGDEBUG)

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("play_torrent", data=json.dumps(merged_data)),
        list_item,
        isFolder=False,
    )


def process_results(results, callback, next_button_action, page):
     # Sort results by date (newest first)
    results = sorted(
        results,
        key=lambda x: x.get("date") or "",
        reverse=True
    )

    execute_thread_pool(results, callback)  
    add_next_button(next_button_action, page=page)
    endOfDirectory(ADDON_HANDLE)
    set_view("widelist")
