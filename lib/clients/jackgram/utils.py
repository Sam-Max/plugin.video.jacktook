import json
from lib.clients.jackgram.client import Jackgram
from lib.clients.tmdb.utils import tmdb_get
from lib.utils.clients.utils import validate_host
from lib.utils.general.utils import (
    Indexer,
    add_next_button,
    execute_thread_pool,
    list_item,
    set_content_type,
    set_media_infoTag,
    set_watched_title
)

from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    build_url,
    get_setting,
    notification,
    set_view,
)

from xbmcplugin import addDirectoryItem, endOfDirectory
from xbmcgui import ListItem


def check_jackgram_active():
    jackgram_enabled = get_setting("jackgram_enabled")
    if not jackgram_enabled:
        notification("You need to activate Jackgram indexer")
        return False
    return True


def check_and_get_jackgram_client():
    if not check_jackgram_active():
        return None
    host = get_setting("jackgram_host")
    if not validate_host(host, Indexer.TELEGRAM):
        return None
    return Jackgram(host, notification)


def process_results(results, callback, next_button_action, page):
    execute_thread_pool(results, callback)
    add_next_button(next_button_action, page=page)
    endOfDirectory(ADDON_HANDLE)
    set_view("widelist")


def get_telegram_files(params):
    page = int(params.get("page"))
    jackgram_client = check_and_get_jackgram_client()
    if not jackgram_client:
        return
    results = jackgram_client.get_files(page=page)
    process_results(results, telegram_files, "get_telegram_files", page)


def telegram_files(res):
    item = list_item(res["file_name"], icon="trending.png")
    item.setProperty("IsPlayable", "true")
    addDirectoryItem(
        ADDON_HANDLE,
        build_url("play_torrent", data=res),
        item,
        isFolder=False,
    )


def get_telegram_latest(params):
    page = int(params.get("page"))
    jackgram_client = check_and_get_jackgram_client()
    if not jackgram_client:
        return
    results = jackgram_client.get_latest(page=page)
    process_results(results, telegram_latest_items, "get_telegram_latest", page)


def telegram_latest_items(res):
    mode = res["type"]
    title = res["title"]
    details = tmdb_get(f"{mode}_details", res["tmdb_id"])

    tmdb_id = res["tmdb_id"]
    imdb_id = details.external_ids.get("imdb_id")
    tvdb_id = details.external_ids.get("tvdb_id")
    res["ids"] = {"tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id}

    list_item = ListItem(label=title)
    set_media_infoTag(list_item, metadata=details, mode=mode)

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("get_telegram_latest_files", data=json.dumps(res)),
        list_item,
        isFolder=True,
    )


def get_telegram_latest_files(params):
    res = json.loads(params["data"])
    set_watched_title(title=res["title"], ids=res["ids"], tg_data=res, mode="tg_latest")
    set_content_type(res["type"])
    execute_thread_pool(res["files"], telegram_latest_files, res)
    endOfDirectory(ADDON_HANDLE)


def telegram_latest_files(file, data):
    mode = file["mode"]
    title = file["title"]

    list_item = ListItem(label=title)
    if mode == "tv":
        details = tmdb_get(
            "episode_details",
            params={
                "id": data["tmdb_id"],
                "season": file["season"],
                "episode": file["episode"],
            },
        )
    else:
        details = tmdb_get("movie_details", data["tmdb_id"])

    list_item.setProperty("IsPlayable", "true")
    set_media_infoTag(list_item, metadata=details, mode=mode)

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("play_torrent", data=file),
        list_item,
        isFolder=False,
    )
