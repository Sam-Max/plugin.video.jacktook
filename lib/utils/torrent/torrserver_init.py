from lib.api.jacktorr.jacktorr import TorrServer
from lib.utils.general.utils import (
    get_service_host,
    get_port,
    get_username,
    get_password,
    ssl_enabled,
)
from lib.utils.kodi.utils import get_setting, JACKTORR_ADDON

_torrserver_api = None


def get_torrserver_api():
    global _torrserver_api

    jacktorr_selected = get_setting("torrent_client", "Jacktorr") == "Jacktorr"

    if _torrserver_api is None and jacktorr_selected and JACKTORR_ADDON:
        _torrserver_api = TorrServer(
            get_service_host(),
            get_port(),
            get_username(),
            get_password(),
            ssl_enabled(),
        )
    return _torrserver_api
