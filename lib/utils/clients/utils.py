from typing import Any, Callable, Dict, Optional
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


def update_dialog(title: str, message: str, dialog: Any, percent: int = 0) -> None:
    if dialog:
        dialog.update(percent, translation(90661) % title, message)


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


def build_jackett_client() -> Optional[object]:
    from lib.clients.jackett import Jackett

    host = str(get_setting("jackett_host", ""))
    api_key = str(get_setting("jackett_apikey", ""))
    port = str(get_setting("jackett_port", "9117"))

    if not validate_credentials(Indexer.JACKETT, host, api_key):
        return None
    return Jackett(host, api_key, port, notification)


def build_prowlarr_client() -> Optional[object]:
    from lib.clients.prowlarr import Prowlarr

    host = str(get_setting("prowlarr_host"))
    api_key = str(get_setting("prowlarr_apikey"))
    port = str(get_setting("prowlarr_port", "9696"))

    if not validate_credentials(Indexer.PROWLARR, host, api_key):
        return None
    return Prowlarr(host, api_key, port, notification)


def build_jackgram_client() -> Optional[object]:
    from lib.clients.jackgram.client import Jackgram

    host = str(get_setting("jackgram_host"))
    token = str(get_setting("jackgram_token", ""))

    if not validate_credentials(Indexer.JACKGRAM, host):
        return None
    return Jackgram(host, notification, token)


def build_zilean_client() -> Optional[object]:
    from lib.clients.zilean import Zilean

    timeout = get_int_setting("zilean_timeout")
    host = str(get_setting("zilean_host"))

    if not validate_credentials(Indexer.ZILEAN, host):
        return None
    return Zilean(host, timeout, notification)


def build_burst_client() -> object:
    from lib.jacktook.client import Burst

    return Burst(notification)


def build_easynews_client() -> Optional[object]:
    from lib.clients.easynews import Easynews

    user = str(get_setting("easynews_user"))
    password = str(get_setting("easynews_password"))
    timeout = get_int_setting("easynews_timeout")

    if not validate_credentials(Indexer.EASYNEWS, user, password):
        return None
    return Easynews(user, password, timeout, notification)


CLIENT_BUILDERS: Dict[str, Callable[[], Optional[object]]] = {
    Indexer.JACKETT: build_jackett_client,
    Indexer.PROWLARR: build_prowlarr_client,
    Indexer.JACKGRAM: build_jackgram_client,
    Indexer.ZILEAN: build_zilean_client,
    Indexer.BURST: build_burst_client,
    Indexer.EASYNEWS: build_easynews_client,
}


def get_client(indexer: str) -> Optional[object]:
    builder = CLIENT_BUILDERS.get(indexer)
    if not builder:
        return None
    return builder()
