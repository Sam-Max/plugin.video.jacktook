from datetime import timedelta
from lib.api.jacktook.kodi import kodilog
from lib.db.cached import cache
from lib.utils.settings import get_cache_expiration, is_cache_enabled
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
    kodilog("torrentio::open_providers_selection")
    cached_providers = cache.get(identifier, hashed_key=True)
    if cached_providers:
        choice = xbmcgui.Dialog().yesno(
            "Providers Selection Dialog",
            f"Your current Providers are: \n{','.join(cached_providers)}\n\nDo you want to change?",
            yeslabel="Ok",
            nolabel="No",
        )
        if choice:
            providers_selection()
        else:
            pass
    else:
        providers_selection()


def providers_selection(identifier="torrentio_providers"):
    selected = xbmcgui.Dialog().multiselect("Select Providers", items)
    if selected:
        providers = [items[i] for i in selected]
        cache.set(
            identifier,
            providers,
            timedelta(hours=get_cache_expiration() if is_cache_enabled() else 0),
            hashed_key=True,
        )
        xbmcgui.Dialog().ok(
            "Selection Dialog", f"Successfully selected: {',' .join(providers)}"
        )
    else:
        xbmcgui.Dialog().notification(
            "Selection", "No providers selected", xbmcgui.NOTIFICATION_INFO
        )


def filter_torrentio_provider(results, identifier="torrentio_providers"):
    selected_providers = cache.get(identifier, hashed_key=True)
    if not selected_providers:
        return results

    for res in results:
        if (
            res["indexer"] == "Torrentio"
            and res["provider"] not in selected_providers
        ):
            results.remove(res)
