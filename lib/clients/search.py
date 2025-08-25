from lib.clients.stremio import ui
from lib.clients.stremio.stremio import StremioAddonClient
from lib.clients.base import TorrentStream
from lib.utils.clients.utils import get_client, update_dialog
from lib.utils.kodi.utils import get_setting, kodilog, notification
from lib.utils.general.utils import Indexer, cache_results, get_cached_results
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Any

import xbmc


def stremio_addon_generator(stremio_addons, dialog):
    for addon in stremio_addons:
        update_dialog(Indexer.STREMIO, f"Searching {addon.manifest.name}", dialog)
        yield StremioAddonClient(addon)


def add_task_if_enabled(
    executor, tasks, setting_key, indexer_key, perform_search, dialog, *args
):
    """Add a search task to the task list if the corresponding setting is enabled."""
    if get_setting(setting_key):
        tasks.append(executor.submit(perform_search, indexer_key, dialog, *args))


def search_client(
    query: str,
    ids: Optional[Dict[str, str]],
    mode: str,
    media_type: str,
    dialog: Any,
    rescrape: bool = False,
    season: int = 1,
    episode: int = 1,
) -> List[TorrentStream]:
    def perform_search(indexer_key, dialog, *args, **kwargs):
        if indexer_key == Indexer.STREMIO:
            stremio_addons = ui.get_selected_stream_addons()
            if not stremio_addons:
                notification("No Stremio addons selected")
                return []
            return [
                result
                for client in stremio_addon_generator(stremio_addons, dialog)
                for result in client.search(*args, **kwargs)
            ]

        if indexer_key != Indexer.BURST:
            update_dialog(indexer_key, f"Searching {indexer_key}", dialog)

        client = get_client(indexer_key)
        if not client:
            return []
        return client.search(*args, **kwargs)

    if not rescrape:
        cached_results = get_cached_results(query, mode, media_type, episode)
        if cached_results:
            dialog.create("")
            return cached_results

    tmdb_id, imdb_id = (ids.get("tmdb_id"), ids.get("imdb_id")) if ids else (None, None)

    dialog.create("")
    total_results = []
    tasks = []

    with ThreadPoolExecutor(
        max_workers=int(get_setting("thread_number", 8))
    ) as executor:
        add_task_if_enabled(
            executor,
            tasks,
            "zilean_enabled",
            Indexer.ZILEAN,
            perform_search,
            dialog,
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
            dialog,
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
                    dialog,
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
            dialog,
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
            dialog,
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
                    dialog,
                    imdb_id,
                    mode,
                    media_type,
                    season,
                    episode,
                )
            )

        for future in as_completed(tasks):
            try:
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
