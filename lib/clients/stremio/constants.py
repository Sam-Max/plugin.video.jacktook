import json


def encode_selected_ids(ids_list):
    """Encode a list of addon IDs for cache storage as JSON."""
    return json.dumps(ids_list)


def decode_selected_ids(raw):
    """Decode addon IDs from cache.

    Handles both JSON list (new format) and comma-separated (old format).
    """
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        result = json.loads(raw)
        if isinstance(result, list):
            return result
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    # Fallback: comma-separated (old format — only safe if keys don't contain commas)
    return [k for k in raw.split(",") if k]


STREMIO_ADDONS_KEY = "stremio_addons"
STREMIO_ADDONS_CATALOGS_KEY = "stremio_catalog_addons"
STREMIO_TV_ADDONS_KEY = "stremio_tv_addons"
STREMIO_USER_ADDONS = "stremio_user_addons"
TORRENTIO_PROVIDERS_KEY = "torrentio.providers"

all_torrentio_providers = [
    ("yts", "YTS", "torrentio.png"),
    ("nyaasi", "Nyaa", "torrentio.png"),
    ("eztv", "EZTV", "torrentio.png"),
    ("rarbg", "RARBG", "torrentio.png"),
    ("mejortorrent", "MejorTorrent", "torrentio.png"),
    ("wolfmax4k", "WolfMax4K", "torrentio.png"),
    ("cinecalidad", "CineCalidad", "torrentio.png"),
    ("1337x", "1337x", "torrentio.png"),
    ("thepiratebay", "The Pirate Bay", "torrentio.png"),
    ("kickasstorrents", "Kickass", "torrentio.png"),
    ("torrentgalaxy", "TorrentGalaxy", "torrentio.png"),
    ("magnetdl", "MagnetDL", "torrentio.png"),
    ("horriblesubs", "HorribleSubs", "torrentio.png"),
    ("tokyotosho", "Tokyotosho", "torrentio.png"),
    ("anidex", "Anidex", "torrentio.png"),
    ("rutor", "Rutor", "torrentio.png"),
    ("rutracker", "Rutracker", "torrentio.png"),
    ("comando", "Comando", "torrentio.png"),
    ("torrent9", "Torrent9", "torrentio.png"),
    ("ilcorsaronero", "Il Corsaro Nero", "torrentio.png"),
    ("besttorrents", "BestTorrents", "torrentio.png"),
    ("bludv", "BluDV", "torrentio.png"),
]

excluded_addons = {
    "imdb.ratings.local",
    "org.stremio.deepdivecompanion",
    "community.ratings.aggregator",
    "org.stremio.ageratings",
    "com.stremio.autostream.addon",
    "org.cinetorrent",
    "community.peario",
    "community.stremioeasynews",
    "Community-knightcrawler.elfhosted.com",
    "jackettio.elfhosted.com",
    "org.stremio.zamunda",
    "com.stremify",
    "org.anyembedaddon",
    "org.stremio.tmdbcollections",
    "org.stremio.ytztvio",
    "com.skyflix",
    "org.stremio.local",
    "com.animeflv.stremio.addon",
    "org.cinecalidad.addon",
    "org.stremio.hellspy",
    "org.prisonmike.streamvix",
    "community.SeedSphere",
    "org.moviesindetail.openlink",
    "app.torbox.stremio",
}
