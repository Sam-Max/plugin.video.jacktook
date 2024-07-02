from lib.clients.utils import get_client
from lib.utils.kodi_utils import (
    get_setting,
    notification,
)
from lib.utils.general_utils import (
    Indexer,
    Players,
    get_cached,
    set_cached,
    torrent_clients
)


def search_client(
    query, ids, mode, media_type, dialog, rescrape=False, season=1, episode=1
):
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

    indexer = get_setting("indexer")
    client_player = get_setting("client_player")

    client = get_client(indexer)
    if not client:
        dialog.create("")
        return

    if client_player in torrent_clients or client_player == Players.DEBRID:
        if indexer == Indexer.JACKETT:
            dialog.create(f"Jacktook [COLOR FFFF6B00]{indexer}[/COLOR]", "Searching...")
            response = client.search(query, mode, season, episode)
        
        elif indexer == Indexer.PROWLARR:
            indexers_ids = get_setting("prowlarr_indexer_ids")
            dialog.create(f"Jacktook [COLOR FFFF6B00]{indexer}[/COLOR]", "Searching...")
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
                notification("Direct Search not supported for Torrentio")
                dialog.create("")
                return
            dialog.create(f"Jacktook [COLOR FFFF6B00]{indexer}[/COLOR]", "Searching...")
            response = client.search(imdb_id, mode, media_type, season, episode)
        
        elif indexer == Indexer.ELHOSTED:
            if imdb_id == -1:
                notification("Direct Search not supported for Elfhosted")
                dialog.create("")
                return
            dialog.create(f"Jacktook [COLOR FFFF6B00]{indexer}[/COLOR]", "Searching...")
            response = client.search(imdb_id, mode, media_type, season, episode)
        
        elif indexer == Indexer.ZILEAN:
            dialog.create(f"Jacktook [COLOR FFFF6B00]{indexer}[/COLOR]", "Searching...")
            response = client.search(query)
       
        elif indexer == Indexer.BURST:
            response = client.search(tmdb_id, query, mode, media_type, season, episode)
            dialog.create("")
       
        else:
            notification(f"Select the correct indexer for the {client_player} client")
            return
    elif client_player == Players.PLEX:
        if indexer == Indexer.PLEX:
            dialog.create(f"Jacktook [COLOR FFFF6B00]{indexer}[/COLOR]", "Searching...")
            response = client.search(imdb_id, mode, media_type, season, episode)
        else:
            notification(f"Select the correct indexer for the {client_player} client")
            return
        
    if mode == "tv" or media_type == "tv" or mode == "anime":
        set_cached(response, query, params=(episode, "index"))
    else:
        set_cached(response, query, params=("index"))

    return response
