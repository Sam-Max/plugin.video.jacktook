from typing import Optional
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


def update_dialog(title: str, message: str, dialog: object, percent: int = 0) -> None:
    if dialog:
        dialog.update(percent, f"Jacktook [COLOR FFFF6B00]{title}[/COLOR]", message)


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
        from lib.clients.jackett import Jackett

        host = str(get_setting("jackett_host", ""))
        api_key = str(get_setting("jackett_apikey", ""))
        port = str(get_setting("jackett_port", "9117"))

        if not validate_credentials(indexer, host, api_key):
            return
        return Jackett(host, api_key, port, notification)

    elif indexer == Indexer.PROWLARR:
        from lib.clients.prowlarr import Prowlarr

        host = str(get_setting("prowlarr_host"))
        api_key = str(get_setting("prowlarr_apikey"))
        port = str(get_setting("prowlarr_port", "9696"))

        if not validate_credentials(indexer, host, api_key):
            return
        return Prowlarr(host, api_key, port, notification)

    elif indexer == Indexer.JACKGRAM:
        from lib.clients.jackgram.client import Jackgram

        host = str(get_setting("jackgram_host"))
        token = str(get_setting("jackgram_token", ""))
        if not validate_credentials(indexer, host):
            return
        return Jackgram(host, notification, token)

    elif indexer == Indexer.ZILEAN:
        from lib.clients.zilean import Zilean

        timeout = get_int_setting("zilean_timeout")
        host = str(get_setting("zilean_host"))
        if not validate_credentials(indexer, host):
            return
        return Zilean(host, timeout, notification)

    elif indexer == Indexer.BURST:
        from lib.jacktook.client import Burst

        return Burst(notification)

    elif indexer == Indexer.EASYNEWS:
        from lib.clients.easynews import Easynews

        user = str(get_setting("easynews_user"))
        password = str(get_setting("easynews_password"))
        timeout = get_int_setting("easynews_timeout")

        if not validate_credentials(indexer, user, password):
            return
        return Easynews(user, password, timeout, notification)
