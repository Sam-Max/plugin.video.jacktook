from lib.api.jacktorr.jacktorr import TorrServer
from lib.utils.general.utils import (
    get_service_host,
    get_port,
    get_username,
    get_password,
    ssl_enabled,
)
from lib.utils.kodi.utils import JACKTORR_ADDON

_torrserver_api = None


def get_torrserver_api():
    global _torrserver_api

    if _torrserver_api is None and JACKTORR_ADDON:
        _torrserver_api = TorrServer(
            get_service_host(),
            get_port(),
            get_username(),
            get_password(),
            ssl_enabled(),
        )
    return _torrserver_api
