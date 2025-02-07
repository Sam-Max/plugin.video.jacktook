from lib.api.jacktook.kodi import kodilog
from lib.clients.jacktook_burst import Burst
from lib.clients.jackett import Jackett
from lib.clients.jackgram import Jackgram
from lib.clients.prowlarr import Prowlarr
from lib.clients.zilean import Zilean
from lib.utils.kodi_utils import get_setting, notification, translation
from lib.utils.utils import Indexer
from lib.utils.settings import get_int_setting


def validate_host(host, indexer):
    if not host:
        notification(f"{translation(30223)}: {indexer}")
        return None
    return True


def validate_key(api_key, indexer):
    if not api_key:
        notification(f"{translation(30221)}: {indexer}")
        return None
    return True


def update_dialog(title, message, dialog):
    dialog.update(0, f"Jacktook [COLOR FFFF6B00]{title}[/COLOR]", message)

    
def get_client(indexer):
    if indexer == Indexer.JACKETT:
        host = get_setting("jackett_host")
        api_key = get_setting("jackett_apikey")
        if not validate_host(host, indexer):
            return
        if not validate_key(api_key, indexer):
            return
        return Jackett(host, api_key, notification)

    elif indexer == Indexer.PROWLARR:
        host = get_setting("prowlarr_host")
        api_key = get_setting("prowlarr_apikey")
        if not validate_host(host, indexer):
            return
        if not validate_key(api_key, indexer):
            return
        return Prowlarr(host, api_key, notification)

    elif indexer == Indexer.JACKGRAM:
        host = get_setting("jackgram_host")
        if not validate_host(host, indexer):
            return
        return Jackgram(host, notification)

    elif indexer == Indexer.ZILEAN:
        timeout = get_int_setting("zilean_timeout")
        host = get_setting("zilean_host")
        if not validate_host(host, indexer):
            return
        return Zilean(host, timeout, notification)

    elif indexer == Indexer.BURST:
        return Burst(notification)
