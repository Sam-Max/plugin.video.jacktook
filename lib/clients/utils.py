from lib.clients.burst import Burst
from lib.clients.elhosted import Elfhosted
from lib.clients.jackett import Jackett
from lib.clients.jackgram import Jackgram
from lib.clients.prowlarr import Prowlarr
from lib.clients.torrentio import Torrentio
from lib.clients.zilean import Zilean
from lib.utils.kodi_utils import ADDON, get_setting, notification, translation
from lib.utils.utils import Indexer
from lib.utils.settings import get_int_setting
from lib.api.jacktook.kodi import kodilog


def load_indexer_state():
    previous_indexer = ADDON.getSetting("previous_indexer")
    return {"previous_indexer": previous_indexer if previous_indexer else ""}


indexer_state = load_indexer_state()


def check_indexer(current_indexer):
    if current_indexer != indexer_state["previous_indexer"]:
        indexer_state["previous_indexer"] = current_indexer
        ADDON.setSetting("previous_indexer", indexer_state["previous_indexer"])
        ADDON.setSetting("debrid_cached_check", "false")
        return True
    ADDON.setSetting("debrid_cached_check", "true")
    return False


def get_client(indexer):
    if indexer == Indexer.JACKETT:
        host = get_setting("jackett_host")
        api_key = get_setting("jackett_apikey")
        if not host or not api_key:
            notification(translation(30220))
            return
        if len(api_key) != 32:
            notification(translation(30221))
            return
        return Jackett(host, api_key, notification)

    elif indexer == Indexer.PROWLARR:
        host = get_setting("prowlarr_host")
        api_key = get_setting("prowlarr_apikey")
        if not host or not api_key:
            notification(translation(30223))
            return
        if len(api_key) != 32:
            notification(translation(30224))
            return
        return Prowlarr(host, api_key, notification)

    elif indexer == Indexer.TORRENTIO:
        host = get_setting("torrentio_host")
        if not host:
            notification(translation(30227))
            return
        return Torrentio(host, notification)

    elif indexer == Indexer.JACKGRAM:
        host = get_setting("jackgram_host")
        if not host:
            notification(translation(30227))
            return
        return Jackgram(host, notification)

    elif indexer == Indexer.ELHOSTED:
        host = get_setting("elfhosted_host")
        if not host:
            notification(translation(30225))
            return
        return Elfhosted(host, notification)

    elif indexer == Indexer.ZILEAN:
        timeout = get_int_setting("zilean_timeout")
        host = get_setting("zilean_host")
        if not host:
            notification(translation(30225))
            return
        return Zilean(host, timeout, notification, kodilog)

    elif indexer == Indexer.BURST:
        return Burst(notification)
