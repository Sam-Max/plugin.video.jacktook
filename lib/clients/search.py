from lib.api.jacktook.kodi import kodilog
from lib.utils.client_utils import get_client
from lib.utils.kodi_utils import get_setting
from lib.utils.utils import Indexer, get_cached, set_cached
from lib.utils.tmdb_utils import get_tmdb_media_details

def show_dialog(title, message, dialog):
    dialog.update(0, f"Jacktook [COLOR FFFF6B00]{title}[/COLOR]", message)


def getLocalizedTitle(details, iso_639_1, iso_3166_1 = None):
    """
    Helper function for retrieving titles from TMDb media details for a specific language/region.
    """
    translations = details.get("translations", {}).get("translations", [])
    for translation in translations:
        if translation["iso_639_1"] == iso_639_1 and (iso_3166_1 is None or translation["iso_3166_1"] == iso_3166_1):
            title = translation["data"].get("title") or translation["data"].get("name") or None
            if title: 
                return translation["data"].get("title") or translation["data"].get("name") or None
    return None


def expand_query(query, tmdb_id, mode):
    """
    Expand a search query by adding related titles based on TMDb media details.

    This function generates a list of search queries by including the original title
    and localized title of a media item if certain conditions are met. It ensures 
    the queries are unique and removes any empty entries.
    """
    queries = [query]
    if not tmdb_id:
        return queries
    
    if not mode in ["tv", "movies"]:
        return queries

    if not any(get_setting(setting) for setting in [
        "zilean_enabled",
        "jacktookburst_enabled",
        "prowlarr_enabled",
        "jackett_enabled",
        "jackgram_enabled"]):
        return queries

    details = get_tmdb_media_details(tmdb_id, mode)
    original = details.get("original_title", "") or details.get("original_name", "") or None
    localized = getLocalizedTitle(details, "es", "ES")
    queries.append(original)
    queries.append(localized)
    
    # Remove empty or duplicated queries
    queries = filter(None, queries)
    queries = list(set(queries))
    
    return queries

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

    queries = expand_query(query, tmdb_id, mode)
            
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
        for query in queries:
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
        for query in queries:
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
        for query in queries:
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
        for query in queries:
            perform_search(
                Indexer.JACKETT,
                dialog,
                query,
                mode,
                season,
                episode,
            )

    if get_setting("jackgram_enabled"):
        for query in queries:
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
