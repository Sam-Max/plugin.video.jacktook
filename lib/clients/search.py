from urllib.parse import quote
from lib.clients.utils import get_client
from lib.utils.kodi import (
    Keyboard,
    get_setting,
    notify,
)
from lib.utils.utils import (
    Indexer,
    get_cached,
    set_cached,
)


def search_client(
    query, ids, mode, media_type, dialog, rescrape=False, season=1, episode=1
):
    if not query:
        text = Keyboard(id=30243)
        if text:
            query = quote(text)
        else:
            dialog.create("")
            return None

    if not rescrape:
        if mode == "tv" or media_type == "tv":
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
    
    indexer = get_setting("indexer")
    client = get_client(indexer)
    if not client:
        dialog.create("")
        return None

    if indexer == Indexer.JACKETT:
        dialog.create("Jacktook [COLOR FFFF6B00]Jackett[/COLOR]", "Searching...")
        response = client.search(query, mode, season, episode)

    elif indexer == Indexer.PROWLARR:
        indexers_ids = get_setting("prowlarr_indexer_ids")
        dialog.create("Jacktook [COLOR FFFF6B00]Prowlarr[/COLOR]", "Searching...")
        response = client.search(
            query,
            mode,
            imdb_id,
            season,
            episode,
            indexers_ids,
        )
    elif indexer == Indexer.TORRENTIO:
        if imdb_id == -1:
            notify("Direct Search not supported for Torrentio")
            dialog.create("")
            return None
        dialog.create("Jacktook [COLOR FFFF6B00]Torrentio[/COLOR]", "Searching...")
        response = client.search(imdb_id, mode, media_type, season, episode)

    elif indexer == Indexer.ELHOSTED:
        if imdb_id == -1:
            notify("Direct Search not supported for Elfhosted")
            dialog.create("")
            return None
        dialog.create("Jacktook [COLOR FFFF6B00]Elfhosted[/COLOR]", "Searching...")
        response = client.search(imdb_id, mode, media_type, season, episode)

    elif indexer == Indexer.BURST:
        response = client.search(tmdb_id, query, mode, media_type, season, episode)
        dialog.create("")

    if mode == "tv" or media_type == "tv":
        set_cached(response, query, params=(episode, "index"))
    else:
        set_cached(response, query, params=("index"))

    return response
