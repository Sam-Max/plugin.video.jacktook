from lib.api.jacktook.kodi import kodilog
from lib.utils.client_utils import get_client
from lib.utils.kodi_utils import get_setting
from lib.utils.utils import Indexer, get_cached, set_cached


def show_dialog(title, message, dialog):
    dialog.update(0, f"Jacktook [COLOR FFFF6B00]{title}[/COLOR]", message)


def search_client(
    query, ids, mode, media_type, dialog, rescrape=False, season=1, episode=1
):

    def perform_search(indexer_key, dialog, *args, **kwargs):
        if indexer_key != Indexer.BURST:
            show_dialog(indexer_key, f"Searching {indexer_key}", dialog)
        client = get_client(indexer_key)
        if not client:
            return
        results = client.search(*args, **kwargs)
        if results:
            total_results.extend(results)

    if not rescrape:
        if mode == "tv" or media_type == "tv" or mode == "anime":
            cached_results = get_cached(query, params=(episode, "index"))
        else:
            cached_results = get_cached(query, params=("index"))

        if cached_results:
            dialog.create("")
            return cached_results

    if ids:
        tmdb_id, _, imdb_id = ids.split(", ")
    else:
        tmdb_id = imdb_id = -1

    dialog.create("")
    total_results = []

    if get_setting("torrentio_enabled"):
        if imdb_id != -1:
            perform_search(
                Indexer.TORRENTIO,
                dialog,
                imdb_id,
                mode,
                media_type,
                season,
                episode,
            )

    if get_setting("mediafusion_enabled"):
        if imdb_id != -1:
            perform_search(
                Indexer.MEDIAFUSION,
                dialog,
                imdb_id,
                mode,
                media_type,
                season,
                episode,
            )

    if get_setting("elfhosted_enabled"):
        if imdb_id != -1:
            perform_search(
                Indexer.ELHOSTED,
                dialog,
                imdb_id,
                mode,
                media_type,
                season,
                episode,
            )

    if get_setting("zilean_enabled"):
        if imdb_id != -1:
            perform_search(
                Indexer.ZILEAN,
                dialog,
                query,
                mode,
                media_type,
                season,
                episode,
            )

    if get_setting("jacktookburst_enabled"):
        perform_search(
            Indexer.BURST,
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
        perform_search(
            Indexer.PROWLARR,
            dialog,
            query,
            mode,
            season,
            episode,
            indexers_ids,
        )

    if get_setting("jackett_enabled"):
        perform_search(
            Indexer.JACKETT,
            dialog,
            query,
            mode,
            season,
            episode,
        )

    if get_setting("jackgram_enabled"):
        perform_search(
            Indexer.JACKGRAM,
            dialog,
            tmdb_id,
            query,
            mode,
            media_type,
            season,
            episode,
        )

    if mode == "tv" or media_type == "tv" or mode == "anime":
        set_cached(total_results, query, params=(episode, "index"))
    else:
        set_cached(total_results, query, params=("index"))

    return total_results
