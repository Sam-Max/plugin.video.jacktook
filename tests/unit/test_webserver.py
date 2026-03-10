import sqlite3
import sys
from unittest.mock import MagicMock


sqlite3.connect = MagicMock(return_value=MagicMock())
sys.modules["xbmc"] = MagicMock()
sys.modules["xbmcgui"] = MagicMock()
sys.modules["xbmcaddon"] = MagicMock()
sys.modules["xbmcplugin"] = MagicMock()
sys.modules["xbmcvfs"] = MagicMock()


from lib.services.webserver import _addon_capabilities


def test_addon_capabilities_requires_supported_movie_prefixes():
    manifest = {
        "types": ["movie", "series"],
        "idPrefixes": ["kitsu:"],
        "resources": [{"name": "stream", "types": ["movie", "series"]}],
    }

    capabilities = _addon_capabilities(manifest)

    assert capabilities == {"stream": False, "catalog": False, "tv": False}


def test_addon_capabilities_accepts_tmdb_stream_prefixes():
    manifest = {
        "types": ["movie", "series"],
        "idPrefixes": ["tmdb:"],
        "resources": ["stream"],
    }

    capabilities = _addon_capabilities(manifest)

    assert capabilities == {"stream": True, "catalog": False, "tv": False}


def test_addon_capabilities_keeps_tv_streams_without_movie_prefixes():
    manifest = {
        "types": ["tv"],
        "resources": [{"name": "stream", "types": ["tv"]}],
    }

    capabilities = _addon_capabilities(manifest)

    assert capabilities == {"stream": False, "catalog": False, "tv": True}
