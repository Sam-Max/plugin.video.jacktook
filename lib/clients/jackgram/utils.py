import json
import threading

from xbmcplugin import addDirectoryItem

from lib.clients.jackgram.client import Jackgram
from lib.clients.tmdb.utils.utils import tmdb_get
from lib.utils.clients.utils import validate_host
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

_tmdb_cache = {}
_tmdb_cache_lock = threading.Lock()


def _cached_tmdb_get(path, params=None):
    if isinstance(params, (str, int)):
        key = (path, params)
    elif isinstance(params, dict):
        key = (path, json.dumps(params, sort_keys=True))
    else:
        key = (path, str(params))
    with _tmdb_cache_lock:
        if key in _tmdb_cache:
            return _tmdb_cache[key]
    result = tmdb_get(path, params)
    with _tmdb_cache_lock:
        _tmdb_cache[key] = result
    return result


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


def test_jackgram_connection(params):
    host = str(get_setting("jackgram_host") or "").strip()
    token = str(get_setting("jackgram_token", "") or "").strip()
    if not validate_host(host, Indexer.JACKGRAM):
        return
    normalized_host = host.rstrip("/")
    url = f"{normalized_host}/status"
    try:
        client = Jackgram(normalized_host, notification, token if token else None)
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        res = client.session.get(url, headers=headers, timeout=(5, 15))
    except Exception as exc:
        kodilog(f"Jackgram test connection failed: {exc}")
        notification(translation(30261))
        return
    try:
        if res.status_code == 401:
            notification(f"{translation(30221)}: Jackgram")
            return
        if res.status_code == 200:
            notification(translation(30260))
            return
        notification(translation(30261))
    except Exception as exc:
        kodilog(f"Jackgram test connection error: {exc}")
        notification(translation(30261))


def _parse_page(query):
    raw = query.get("page", 1)
    try:
        page = int(raw)
        return page if page >= 1 else 1
    except (TypeError, ValueError):
        return 1


def list_jackgram_latest_movies(query):
    page = _parse_page(query)
    jackgram_client = check_and_get_jackgram_client()
    if not jackgram_client:
        end_of_directory(cache=False)
        return
    results = jackgram_client.get_latest_movies(page=page)
    process_results(results, add_jackgram_title_item, "list_jackgram_latest_movies", page)


def list_jackgram_latest_series(query):
    page = _parse_page(query)
    jackgram_client = check_and_get_jackgram_client()
    if not jackgram_client:
        end_of_directory(cache=False)
        return
    results = jackgram_client.get_latest_series(page=page)
    process_results(results, add_jackgram_title_item, "list_jackgram_latest_series", page)


def list_jackgram_raw_files(query):
    page = _parse_page(query)
    jackgram_client = check_and_get_jackgram_client()
    if not jackgram_client:
        end_of_directory(cache=False)
        return
    results = jackgram_client.get_files(page=page)
    process_results(results, add_jackgram_raw_file_item, "list_jackgram_raw_files", page)


def add_jackgram_raw_file_item(item):
    list_item = build_list_item(item["file_name"], icon="trending.png")
    list_item.setProperty("IsPlayable", "true")
    item["type"] = IndexerType.DIRECT
    item["is_torrent"] = False
    item["indexer"] = Indexer.JACKGRAM  # needed for resolve_playback_url

    addDirectoryItem(
        ADDON_HANDLE,
        build_url("play_media", data=item),
        list_item,
        isFolder=False,
    )


def _fetch_title_item(entry):
    api_type = entry["type"]
    tmdb_id = entry["tmdb_id"]
    details = _cached_tmdb_get(f"{api_type}_details", tmdb_id)
    if details is None:
        kodilog(f"Failed to get details for {api_type} with ID {tmdb_id}")
        return None
    entry["ids"] = {
        "tmdb_id": tmdb_id,
        "tvdb_id": details.external_ids.get("tvdb_id"),
        "imdb_id": details.external_ids.get("imdb_id"),
    }
    return entry, details


def add_jackgram_title_item(entry):
    result = _fetch_title_item(entry)
    if result is None:
        return
    entry, details = result
    api_type = entry["type"]
    title = entry["title"]
    mode = "movies" if api_type == "movie" else api_type
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
    files = _dedupe_source_items(parent_data.get("files") or [])
    execute_thread_pool(files, add_jackgram_source_item, parent_data)
    end_of_directory()


def add_jackgram_source_item(file_entry, parent_data):
    mode = file_entry.get("mode", "tv")
    title = file_entry.get("title", "")

    list_item = make_list_item(label=title)
    details = None
    if mode == "tv":
        season = file_entry.get("season")
        episode = file_entry.get("episode")
        if isinstance(season, list):
            season = season[0] if season else None
        if isinstance(episode, list):
            episode = episode[0] if episode else None
        try:
            season_val = int(season) if season is not None else None
        except (TypeError, ValueError):
            season_val = None
        try:
            episode_val = int(episode) if episode is not None else None
        except (TypeError, ValueError):
            episode_val = None
        if season_val is not None and episode_val is not None:
            details = _cached_tmdb_get(
                "episode_details",
                params={
                    "id": parent_data.get("tmdb_id"),
                    "season": season_val,
                    "episode": episode_val,
                },
            )
    else:
        tmdb_id = parent_data.get("tmdb_id")
        if tmdb_id is not None:
            details = _cached_tmdb_get("movie_details", tmdb_id)

    list_item.setProperty("IsPlayable", "true")
    if details is not None:
        set_media_infoTag(list_item, data=details, mode=mode)

    merged_data = {**parent_data, **file_entry}

    merged_data["type"] = IndexerType.DIRECT
    merged_data["is_torrent"] = False
    merged_data["indexer"] = Indexer.JACKGRAM

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

    results = sorted(results, key=lambda x: x.get("date") or "", reverse=True)

    if callback is add_jackgram_title_item:
        results = _dedupe_title_items(results)

    execute_thread_pool(results, callback)
    if isinstance(results, list) and len(results) >= 12:
        add_next_button(next_button_action, page=page)
    end_of_directory()
    apply_section_view("view.downloads", content_type="files")


def _dedupe_title_items(results):
    seen = set()
    deduped = []
    for entry in results:
        key = (entry.get("type"), entry.get("tmdb_id"))
        if key not in seen and key != (None, None):
            seen.add(key)
            deduped.append(entry)
    orig_count = len(results)
    if len(deduped) != orig_count:
        kodilog(f"Jackgram deduped {orig_count - len(deduped)} duplicate title(s)")
    return deduped


def _dedupe_source_items(files):
    seen = set()
    deduped = []
    for f in files:
        season = f.get("season")
        episode = f.get("episode")
        if isinstance(season, list):
            season = tuple(season)
        if isinstance(episode, list):
            episode = tuple(episode)
        key = (f.get("url"), season, episode)
        if key not in seen:
            seen.add(key)
            deduped.append(f)
    return deduped
