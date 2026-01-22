from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from typing import List, Optional

from lib.clients.stremio import ui
from lib.clients.stremio.stremio import StremioAddonClient
from lib.db.cached import cache
from lib.domain.torrent import TorrentStream
from lib.gui.custom_dialogs import source_select
from lib.player import JacktookPLayer
from lib.utils.clients.utils import get_client, update_dialog
from lib.utils.general.utils import (
    DialogListener,
    Indexer,
    cache_results,
    get_cached_results,
    pre_process,
    post_process,
    build_media_metadata,
    set_content_type,
    set_watched_title,
    clean_auto_play_undesired,
)
from lib.utils.debrid.debrid_utils import check_debrid_cached
from lib.utils.kodi.settings import auto_play_enabled, get_setting
from lib.utils.player.utils import resolve_playback_url
from lib.utils.kodi.utils import (
    notification,
    cancel_playback,
    kodilog,
    translation,
)

import xbmc
from xbmcgui import Dialog


def run_search_entry(params: dict):
    if get_setting("super_quick_play", False):
        ids = json.loads(params.get("ids", "{}"))
        key = ""
        if "tmdb_id" in ids:
            key = str(ids["tmdb_id"])
            tv_data = json.loads(params.get("tv_data", "{}"))
            if "season" in tv_data and "episode" in tv_data:
                key += f'_{tv_data["season"]}_{tv_data["episode"]}'

        if key:
            cached_torrent = cache.get(key)
            if cached_torrent:
                kodilog(f"Found cached media: {cached_torrent['title']}")
                dialog = Dialog()
                if dialog.yesno(
                    translation(90142),
                    translation(90143),
                ):
                    playback_info = resolve_playback_url(cached_torrent)
                    if not playback_info:
                        notification(translation(90144))
                        return

                    player = JacktookPLayer()
                    player.run(data=playback_info)
                    del player
                    return
                else:
                    kodilog("User chose not to play cached torrent")
            else:
                kodilog("No cached media found")

    query = params.get("query", "")
    mode = params.get("mode", "")
    media_type = params.get("media_type", "")
    ids = json.loads(params.get("ids", "{}"))
    tv_data = json.loads(params.get("tv_data", "{}"))
    direct = params.get("direct", False)
    rescrape = params.get("rescrape", False)

    set_content_type(mode)
    set_watched_title(query, ids, mode, media_type)

    ep_name = tv_data.get("name", "")
    episode = tv_data.get("episode", 1)
    season = tv_data.get("season", 1)

    results = search_client(query, ids, mode, media_type, rescrape, season, episode)
    if not results:
        notification("No results found")
        return

    pre_results = pre_process_results(results, mode, ep_name, episode, season)
    if not pre_results:
        notification("No results found")
        return

    post_results = process_results(
        pre_results, query, mode, media_type, rescrape, episode
    )
    if not post_results:
        notification("No cached results found")
        return

    if auto_play_enabled():
        auto_play(post_results, ids, tv_data, mode)
        return

    show_source_select(post_results, mode, ids, tv_data, direct)


def search_client(
    query: str,
    ids: dict,
    mode: str,
    media_type: str,
    rescrape: bool,
    season: int,
    episode: int,
    show_dialog: bool = True,
) -> List[TorrentStream]:
    with DialogListener() as listener:

        def perform_search(indexer_key, dialog, *args, **kwargs):
            if indexer_key == Indexer.STREMIO:
                stremio_addons = ui.get_selected_stream_addons()
                if not stremio_addons:
                    notification("No Stremio addons selected")
                    return []
                return [
                    result
                    for client in stremio_addon_generator(
                        stremio_addons, dialog, show_dialog
                    )
                    for result in client.search(*args, **kwargs)
                ]

            client = get_client(indexer_key)
            if not client:
                return []
            return client.search(*args, **kwargs)

        if not rescrape:
            kodilog("Checking for cached results before searching")
            kodilog(
                f"Search parameters - Query: {query}, Mode: {mode}, Media Type: {media_type}, Episode: {episode}"
            )
            cached_results = get_cached_results(query, mode, media_type, episode)
            if cached_results:
                if show_dialog:
                    listener.dialog.create("")
                return cached_results

        tmdb_id, imdb_id = (
            (ids.get("tmdb_id"), ids.get("imdb_id")) if ids else (None, None)
        )

        if show_dialog:
            listener.dialog.create("")
        total_results = []
        tasks = []

        with ThreadPoolExecutor(
            max_workers=int(get_setting("thread_number", 6))
        ) as executor:
            add_task_if_enabled(
                executor,
                tasks,
                "zilean_enabled",
                Indexer.ZILEAN,
                perform_search,
                listener.dialog,
                query,
                mode,
                media_type,
                season,
                episode,
            )
            add_task_if_enabled(
                executor,
                tasks,
                "jacktookburst_enabled",
                Indexer.BURST,
                perform_search,
                listener.dialog,
                tmdb_id,
                query,
                mode,
                media_type,
                season,
                episode,
            )
            if get_setting("prowlarr_enabled"):
                indexers_ids = get_setting("prowlarr_indexer_ids")
                tasks.append(
                    executor.submit(
                        perform_search,
                        Indexer.PROWLARR,
                        listener.dialog,
                        query,
                        mode,
                        season,
                        episode,
                        indexers_ids,
                    )
                )
            add_task_if_enabled(
                executor,
                tasks,
                "jackett_enabled",
                Indexer.JACKETT,
                perform_search,
                listener.dialog,
                query,
                mode,
                season,
                episode,
            )
            add_task_if_enabled(
                executor,
                tasks,
                "jackgram_enabled",
                Indexer.JACKGRAM,
                perform_search,
                listener.dialog,
                tmdb_id,
                query,
                mode,
                media_type,
                season,
                episode,
            )
            if get_setting("stremio_enabled") and imdb_id:
                tasks.append(
                    executor.submit(
                        perform_search,
                        Indexer.STREMIO,
                        listener.dialog,
                        imdb_id,
                        mode,
                        media_type,
                        season,
                        episode,
                    )
                )

            total_tasks = len(tasks)
            completed_tasks = 0

            for future in as_completed(tasks):
                try:
                    completed_tasks += 1
                    if show_dialog and total_tasks > 0:
                        percent = int(completed_tasks / total_tasks * 100)
                        update_dialog("Searching", f"Searching... {percent}%", listener.dialog, percent)
                    
                    results = future.result()
                    kodilog(f"Results from {future}: {results}", level=xbmc.LOGDEBUG)
                    if results:
                        total_results.extend(results)
                except Exception as e:
                    import traceback

                    error_details = traceback.format_exc()
                    kodilog(f"Error in {e}\n{error_details}")

        cache_results(total_results, query, mode, media_type, episode)
        return total_results


def pre_process_results(
    results: List[TorrentStream], mode: str, ep_name: str, episode: int, season: int
) -> List[TorrentStream]:
    return pre_process(results, mode, ep_name, episode, season)


def process_results(
    pre_results: List[TorrentStream],
    query: str,
    mode: str,
    media_type: str,
    rescrape: bool,
    episode: int,
) -> List[TorrentStream]:
    torrent_results = []
    if get_setting("torrent_enable"):
        torrent_results = post_process(pre_results)
    with DialogListener() as listener:
        debrid_results = check_debrid_cached(
            query, pre_results, mode, media_type, listener.dialog, rescrape, episode
        )
    return debrid_results + torrent_results


def show_source_select(
    results: List[TorrentStream],
    mode: str,
    ids: dict,
    tv_data: dict,
    direct: bool = False,
) -> Optional[dict]:
    item_info = {"tv_data": tv_data, "ids": ids, "mode": mode}

    if not direct and ids:
        item_info.update(build_media_metadata(ids, mode))

    xml_file_string = (
        "source_select_direct.xml" if mode == "direct" else "source_select.xml"
    )

    source_select(item_info, xml_file=xml_file_string, sources=results)


def auto_play(results: List[TorrentStream], ids, tv_data, mode):
    filtered_results = clean_auto_play_undesired(results)
    if not filtered_results:
        notification("No suitable source found for auto play.")
        cancel_playback()
        return

    preferred_quality = str(get_setting("auto_play_quality"))
    quality_matches = [
        r for r in filtered_results if preferred_quality.lower() in r.quality.lower()
    ]

    if not quality_matches:
        notification("No sources found with the preferred quality.")
        cancel_playback()
        return

    selected_result = quality_matches[0]

    playback_info = resolve_playback_url(
        data={
            "title": selected_result.title,
            "mode": mode,
            "indexer": selected_result.indexer,
            "type": selected_result.type,
            "debrid_type": selected_result.debridType,
            "ids": ids,
            "info_hash": selected_result.infoHash,
            "url": selected_result.url,
            "tv_data": tv_data,
            "is_torrent": False,
        },
    )

    if not playback_info:
        cancel_playback()
        return

    player = JacktookPLayer()
    player.run(data=playback_info)
    del player


def stremio_addon_generator(stremio_addons, dialog, show_dialog):
    for addon in stremio_addons:
        if show_dialog:
            update_dialog(addon.manifest.name, "Searching...", dialog)
        yield StremioAddonClient(addon)


def add_task_if_enabled(
    executor, tasks, setting_key, indexer_key, perform_search, dialog, *args, **kwargs
):
    """Add a search task to the task list if the corresponding setting is enabled."""
    if get_setting(setting_key):
        tasks.append(
            executor.submit(perform_search, indexer_key, dialog, *args, **kwargs)
        )
