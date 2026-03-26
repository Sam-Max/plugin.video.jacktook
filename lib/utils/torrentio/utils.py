from datetime import timedelta
from lib.db.cached import cache
from lib.utils.kodi.settings import get_cache_expiration, is_cache_enabled
from lib.utils.kodi.utils import translation
import xbmcgui


items = [
    "YTS",
    "EZTV",
    "RARBG",
    "1337x",
    "ThePirateBay",
    "KickassTorrents",
    "TorrentGalaxy",
    "MagnetDL",
    "HorribleSubs",
    "NyaaSi",
    "TokyoTosho",
    "AniDex",
    "Rutor",
    "Rutracker",
    "Comando",
    "BluDV",
    "Torrent9",
    "MejorTorrent",
    "Wolfmax4k",
    "Cinecalidad",
]


def open_providers_selection(identifier="torrentio_providers"):
    cached_providers = cache.get(identifier)
    if cached_providers:
        choice = xbmcgui.Dialog().yesno(
            translation(90570),
            translation(90571) % ",".join(cached_providers),
            yeslabel=translation(90605),
            nolabel=translation(90606),
        )
        if not choice:
            return
        providers_selection()
    else:
        providers_selection()


def providers_selection(identifier="torrentio_providers"):
    selected = xbmcgui.Dialog().multiselect(translation(90572), items)
    if selected:
        providers = [items[i] for i in selected]
        cache.set(
            identifier,
            providers,
            timedelta(hours=get_cache_expiration() if is_cache_enabled() else 0),
        )
        xbmcgui.Dialog().ok(
            translation(90573), translation(90574) % ",".join(providers)
        )
    else:
        xbmcgui.Dialog().notification(
            translation(90575), translation(90576), xbmcgui.NOTIFICATION_INFO
        )


def filter_torrentio_provider(results, identifier="torrentio_providers"):
    selected_providers = cache.get(identifier)
    if not selected_providers:
        return results

    filtered_results = [
        res
        for res in results
        if res["indexer"] != "Torrentio"
        or (res["indexer"] == "Torrentio" and res["provider"] in selected_providers)
    ]
    return filtered_results
