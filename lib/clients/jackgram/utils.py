from lib.clients.tmdb.utils.utils import tmdb_get
from lib.utils.general.utils import (
    Indexer,
    IndexerType,
    add_next_button,
    build_list_item,
    execute_thread_pool,
    set_content_type,
    set_media_infoTag,
    set_watched_title,
)

from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    apply_section_view,
    build_url,
    end_of_directory,
    get_setting,
    kodilog,
    make_list_item,
    notification,
    translation,
)

from xbmcplugin import addDirectoryItem
import json


def check_jackgram_active():
    jackgram_enabled = get_setting("jackgram_enabled")
    if not jackgram_enabled:
        notification(translation(90422))
        return False
    return True


def check_and_get_jackgram_client():
    if not check_jackgram_active():
        return None
    from lib.utils.clients.utils import get_client

    return get_client(Indexer.JACKGRAM)


def list_jackgram_latest_movies(query):
    page = int(query.get("page"))
    jackgram_client = check_and_get_jackgram_client()
    if not jackgram_client:
        end_of_directory(cache=False)
        return
    results = jackgram_client.get_latest_movies(page=page)
    process_results(
        results, add_jackgram_title_item, "list_jackgram_latest_movies", page
    )


def list_jackgram_latest_series(query):
    page = int(query.get("page"))
    jackgram_client = check_and_get_jackgram_client()
    if not jackgram_client:
        end_of_directory(cache=False)
        return
    results = jackgram_client.get_latest_series(page=page)
    process_results(
        results, add_jackgram_title_item, "list_jackgram_latest_series", page
    )


def list_jackgram_raw_files(query):
    page = int(query.get("page"))
    jackgram_client = check_and_get_jackgram_client()
    if not jackgram_client:
        end_of_directory(cache=False)
        return
    results = jackgram_client.get_files(page=page)
    process_results(
        results, add_jackgram_raw_file_item, "list_jackgram_raw_files", page
    )


def add_jackgram_raw_file_item(item):
    list_item = build_list_item(item["file_name"], icon="trending.png")
    list_item.setProperty("IsPlayable", "true")
    item["type"] = IndexerType.DIRECT
    item["is_torrent"] = False

    token = get_setting("jackgram_token", "")
    if token and "url" in item:
        item["url"] = f"{item['url']}|Authorization=Bearer {token}"

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("play_media", data=item),
        list_item,
        isFolder=False,
    )


def add_jackgram_title_item(entry):
    api_type = entry["type"]
    title = entry["title"]
    tmdb_id = entry["tmdb_id"]

    details = tmdb_get(f"{api_type}_details", tmdb_id)
    if details is None:
        kodilog(f"Failed to get details for {api_type} with ID {tmdb_id}")
        return

    # Normalize mode
    mode = "movies" if api_type == "movie" else api_type

    imdb_id = getattr(details, "external_ids").get("imdb_id")
    tvdb_id = getattr(details, "external_ids").get("tvdb_id")
    entry["ids"] = {"tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id}

    list_item = make_list_item(label=title)
    set_media_infoTag(list_item, data=details, mode=mode)

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("list_jackgram_title_sources", data=json.dumps(entry)),
        list_item,
        isFolder=True,
    )


def list_jackgram_title_sources(query):
    parent_data = json.loads(query["data"])
    set_watched_title(
        title=parent_data["title"],
        ids=parent_data["ids"],
        tg_data=parent_data,
        mode="tg_latest",
    )
    set_content_type(parent_data["type"])
    execute_thread_pool(parent_data["files"], add_jackgram_source_item, parent_data)
    end_of_directory()


def add_jackgram_source_item(file_entry, parent_data):
    mode = file_entry["mode"]
    title = file_entry["title"]

    list_item = make_list_item(label=title)
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

    merged_data["type"] = IndexerType.DIRECT
    merged_data["is_torrent"] = False

    token = get_setting("jackgram_token", "")
    if token and "url" in merged_data:
        merged_data["url"] = f"{merged_data['url']}|Authorization=Bearer {token}"

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("play_media", data=json.dumps(merged_data)),
        list_item,
        isFolder=False,
    )


def process_results(results, callback, next_button_action, page):
    if not results:
        kodilog("No results found or request failed.")
        end_of_directory()
        return

    # Sort results by date (newest first)
    results = sorted(results, key=lambda x: x.get("date") or "", reverse=True)

    execute_thread_pool(results, callback)
    add_next_button(next_button_action, page=page)
    end_of_directory()
    apply_section_view("view.downloads", content_type="files")
