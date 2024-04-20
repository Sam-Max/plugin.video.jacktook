from urllib.parse import quote
from lib.clients.utils import get_client
from lib.utils.kodi import (
    Keyboard,
    get_setting,
    notify,
)
from lib.utils.utils import (
    Indexer,
    Players,
    get_cached,
    set_cached,
    torrent_clients
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
            return

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
    client_player = get_setting("client_player")
    client = get_client(indexer)

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
                notify("Direct Search not supported for Torrentio")
                dialog.create("")
                return
            dialog.create(f"Jacktook [COLOR FFFF6B00]{indexer}[/COLOR]", "Searching...")
            response = client.search(imdb_id, mode, media_type, season, episode)
        elif indexer == Indexer.ELHOSTED:
            if imdb_id == -1:
                notify("Direct Search not supported for Elfhosted")
                dialog.create("")
                return
            dialog.create(f"Jacktook [COLOR FFFF6B00]{indexer}[/COLOR]", "Searching...")
            response = client.search(imdb_id, mode, media_type, season, episode)
        elif indexer == Indexer.BURST:
            response = client.search(tmdb_id, query, mode, media_type, season, episode)
            dialog.create("")
        else:
            notify(f"Select the correct indexer for the {client_player} client")
            return
    elif client_player == Players.PLEX:
        if indexer == Indexer.PLEX:
            dialog.create(f"Jacktook [COLOR FFFF6B00]{indexer}[/COLOR]", "Searching...")
            response = client.search(imdb_id, mode, media_type, season, episode)
        else:
            notify(f"Select the correct indexer for the {client_player} client")
            return
        
    if mode == "tv" or media_type == "tv":
        set_cached(response, query, params=(episode, "index"))
    else:
        set_cached(response, query, params=("index"))

    return response
