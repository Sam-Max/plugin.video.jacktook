from lib.api.jacktook.kodi import kodilog
from lib.utils.client_utils import get_client, show_dialog
from lib.utils.kodi_utils import get_setting
from lib.utils.utils import Indexer, get_cached, set_cached
from lib.clients.stremio_addon import StremioAddonClient
import lib.stremio.ui as ui
from concurrent.futures import ThreadPoolExecutor, as_completed


def search_client(
   item, dialog, rescrape=False
):
    def perform_search(indexer_key, dialog, *args, **kwargs):
        if indexer_key != Indexer.BURST:
            show_dialog(indexer_key, f"Searching {indexer_key}", dialog)
        client = get_client(indexer_key)
        if not client:
            return []
        return client.search(*args, **kwargs)

    if not rescrape:
        if item["mode"] == "tv" or item["media_type"] == "tv" or item["mode"] == "anime":
            cached_results = get_cached(item["query"], params=(episode, "index"))
        else:
            cached_results = get_cached(item["query"], params=("index"))

        if cached_results:
            dialog.create("")
            return cached_results

    tmdb_id = item["tmdb_id"]
    imdb_id = item["imdb_id"]
    mode = item["mode"]
    media_type = item["media_type"]
    query = item["query"]
    season = item["season"]
    episode = item["episode"]
    dialog.create("")
    total_results = []

    tasks = []

    with ThreadPoolExecutor() as executor:
        if get_setting("zilean_enabled"):
            tasks.append(
                executor.submit(
                    perform_search,
                    Indexer.ZILEAN,
                    dialog,
                    query,
                    mode,
                    media_type,
                    season,
                    episode,
                )
            )

        if get_setting("jacktookburst_enabled"):
            tasks.append(
                executor.submit(
                    perform_search,
                    Indexer.BURST,
                    dialog,
                    tmdb_id,
                    query,
                    mode,
                    media_type,
                    season,
                    episode,
                )
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

        if get_setting("jackett_enabled"):
            tasks.append(
                executor.submit(
                    perform_search,
                    Indexer.JACKETT,
                    dialog,
                    query,
                    mode,
                    season,
                    episode,
                )
            )

        if get_setting("jackgram_enabled"):
            tasks.append(
                executor.submit(
                    perform_search,
                    Indexer.JACKGRAM,
                    dialog,
                    tmdb_id,
                    query,
                    mode,
                    media_type,
                    season,
                    episode,
                )
            )

        if get_setting("stremio_enabled") and imdb_id:
            selected_stremio_addons = ui.get_selected_addons()
            for addon in selected_stremio_addons:
                stremio_client = StremioAddonClient(addon)
                tasks.append(
                    executor.submit(
                        stremio_client.search,
                        imdb_id,
                        mode,
                        media_type,
                        season,
                        episode,
                        dialog,
                    )
                )

        for future in as_completed(tasks):
            try:
                results = future.result()
                if results:
                    total_results.extend(results)
            except Exception as e:
                kodilog(f"Error: {e}")

    if mode == "tv" or media_type == "tv" or mode == "anime":
        set_cached(total_results, query, params=(episode, "index"))
    else:
        set_cached(total_results, query, params=("index"))

    return total_results
