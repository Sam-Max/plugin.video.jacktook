from lib.clients.burst import Burst
from lib.clients.jackett import Jackett
from lib.clients.prowlarr import Prowlarr
from lib.clients.torrentio import Elfhosted, Torrentio
from lib.utils.kodi import get_setting, notify, translation
from lib.utils.utils import Indexer


def get_client(indexer):
    if indexer == Indexer.JACKETT:
        host = get_setting("jackett_host")
        api_key = get_setting("jackett_apikey")
        if not host or not api_key:
            notify(translation(30220))
            return
        if len(api_key) != 32:
            notify(translation(30221))
            return
        return Jackett(host, api_key, notify)

    elif indexer == Indexer.PROWLARR:
        host = get_setting("prowlarr_host")
        api_key = get_setting("prowlarr_apikey")
        if not host or not api_key:
            notify(translation(30223))
            return
        if len(api_key) != 32:
            notify(translation(30224))
            return
        return Prowlarr(host, api_key, notify)

    elif indexer == Indexer.TORRENTIO:
        host = get_setting("torrentio_host")
        if not host:
            notify(translation(30227))
            return
        return Torrentio(host, notify)

    elif indexer == Indexer.ELHOSTED:
        host = get_setting("elfhosted_host")
        if not host:
            notify(translation(30227))
            return
        return Elfhosted(host, notify)

    elif indexer == Indexer.BURST:
        return Burst(notify)