from typing import Optional
from lib.clients.jackett import Jackett
from lib.clients.jackgram.client import Jackgram
from lib.clients.prowlarr import Prowlarr
from lib.clients.zilean import Zilean
from lib.jacktook.client import Burst
from lib.utils.kodi.utils import get_setting, notification, translation
from lib.utils.general.utils import Indexer
from lib.utils.kodi.settings import get_int_setting


def validate_host(host: Optional[str], indexer: str) -> Optional[bool]:
    if not host:
        notification(f"{translation(30223)}: {indexer}")
        return None
    return True


def validate_key(api_key: Optional[str], indexer: str) -> Optional[bool]:
    if not api_key:
        notification(f"{translation(30221)}: {indexer}")
        return None
    return True


def update_dialog(title: str, message: str, dialog: object) -> None:
    dialog.update(0, f"Jacktook [COLOR FFFF6B00]{title}[/COLOR]", message)


def validate_credentials(
    indexer: str, host: Optional[str], api_key: Optional[str] = None
) -> bool:
    """
    Validates the host and API key for a given indexer.
    """
    if not validate_host(host, indexer):
        return False
    if api_key is not None and not validate_key(api_key, indexer):
        return False
    return True


def get_client(indexer: str) -> Optional[object]:
    if indexer == Indexer.JACKETT:
        host = str(get_setting("jackett_host", ""))
        api_key = str(get_setting("jackett_apikey", ""))
        port = str(get_setting("jackett_port", "9117"))

        if not validate_credentials(indexer, host, api_key):
            return
        return Jackett(host, api_key, port, notification)

    elif indexer == Indexer.PROWLARR:
        host = str(get_setting("prowlarr_host"))
        api_key = str(get_setting("prowlarr_apikey"))
        port = str(get_setting("prowlarr_port", "9696"))

        if not validate_credentials(indexer, host, api_key):
            return
        return Prowlarr(host, api_key, port, notification)

    elif indexer == Indexer.JACKGRAM:
        host = str(get_setting("jackgram_host"))
        if not validate_credentials(indexer, host):
            return
        return Jackgram(host, notification)

    elif indexer == Indexer.ZILEAN:
        timeout = get_int_setting("zilean_timeout")
        host = str(get_setting("zilean_host"))
        if not validate_credentials(indexer, host):
            return
        return Zilean(host, timeout, notification)

    elif indexer == Indexer.BURST:
        return Burst(notification)
