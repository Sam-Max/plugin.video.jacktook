from lib.utils.client_utils import check_indexer, get_client
from lib.utils.kodi_utils import (
    get_setting,
    notification,
)
from lib.utils.utils import Indexer, Players, get_cached, set_cached, torrent_clients


def search_client(
    query, ids, mode, media_type, dialog, rescrape=False, season=1, episode=1
):
    current_indexer = get_setting("indexer")
    is_indexer_changed = check_indexer(current_indexer)

    if not is_indexer_changed and not rescrape: 
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

    client_player = get_setting("client_player")
    client = get_client(current_indexer)
    if not client:
        dialog.create("")
        return

    if client_player in torrent_clients or client_player == Players.DEBRID:
        if current_indexer == Indexer.JACKETT:
            dialog.create(
                f"Jacktook [COLOR FFFF6B00]{current_indexer}[/COLOR]", "Searching..."
            )
            response = client.search(query, mode, season, episode)

        elif current_indexer == Indexer.PROWLARR:
            indexers_ids = get_setting("prowlarr_indexer_ids")
            dialog.create(
                f"Jacktook [COLOR FFFF6B00]{current_indexer}[/COLOR]", "Searching..."
            )
            response = client.search(
                query,
                mode,
                imdb_id,
                season,
                episode,
                indexers_ids,
            )

        elif current_indexer == Indexer.TORRENTIO:
            if imdb_id == -1:
                notification("Direct Search not supported for Torrentio")
                dialog.create("")
                return
            dialog.create(
                f"Jacktook [COLOR FFFF6B00]{current_indexer}[/COLOR]", "Searching..."
            )
            response = client.search(imdb_id, mode, media_type, season, episode)

        elif current_indexer == Indexer.ELHOSTED:
            if imdb_id == -1:
                notification("Direct Search not supported for Elfhosted")
                dialog.create("")
                return
            dialog.create(
                f"Jacktook [COLOR FFFF6B00]{current_indexer}[/COLOR]", "Searching..."
            )
            response = client.search(imdb_id, mode, media_type, season, episode)

        elif current_indexer == Indexer.ZILEAN:
            dialog.create(
                f"Jacktook [COLOR FFFF6B00]{current_indexer}[/COLOR]", "Searching..."
            )
            response = client.search(query, mode, media_type, season, episode)

        elif current_indexer == Indexer.BURST:
            response = client.search(tmdb_id, query, mode, media_type, season, episode)
            dialog.create("")

        else:
            notification(f"Select the correct indexer for the {client_player} client")
            return
    elif client_player == Players.JACKGRAM:
        if current_indexer == Indexer.JACKGRAM:
            dialog.create(
                f"Jackgram [COLOR FFFF6B00]{current_indexer}[/COLOR]", "Searching..."
            )
            response = client.search(tmdb_id, query, mode, media_type, season, episode)
        else:
            notification(f"Select the correct indexer for the {client_player} client")
            return

    if mode == "tv" or media_type == "tv" or mode == "anime":
        set_cached(response, query, params=(episode, "index"))
    else:
        set_cached(response, query, params=("index"))

    return response
