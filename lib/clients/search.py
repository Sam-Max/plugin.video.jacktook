from lib.api.jacktook.kodi import kodilog
from lib.utils.client_utils import get_client, update_dialog
from lib.utils.kodi_utils import get_setting
from lib.utils.utils import Indexer, get_cached, set_cached
from lib.clients.stremio_addon import StremioAddonClient
import lib.stremio.ui as ui
from concurrent.futures import ThreadPoolExecutor, as_completed


def stremio_addon_generator(stremio_addons, dialog):
    for addon in stremio_addons:
        update_dialog(Indexer.STREMIO, f"Searching {addon.manifest.name}", dialog)
        yield StremioAddonClient(addon)


def search_client(
    query, ids, mode, media_type, dialog, rescrape=False, season=1, episode=1
):
    def perform_search(indexer_key, dialog, *args, **kwargs):
        if indexer_key == Indexer.STREMIO:
            stremio_addons = ui.get_selected_addons()
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
        if mode == "tv" or media_type == "tv" or mode == "anime":
            cached_results = get_cached(query, params=(episode, "index"))
        else:
            cached_results = get_cached(query, params=("index"))

        if cached_results:
            dialog.create("")
            return cached_results

    if ids:
        tmdb_id, _, imdb_id = ids.values()
    else:
        tmdb_id = imdb_id = None

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
                if results:
                    total_results.extend(results)
            except Exception as e:
                kodilog(f"Error: {e}")

    if mode == "tv" or media_type == "tv" or mode == "anime":
        set_cached(total_results, query, params=(episode, "index"))
    else:
        set_cached(total_results, query, params=("index"))

    return total_results
