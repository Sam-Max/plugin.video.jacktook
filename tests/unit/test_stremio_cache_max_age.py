from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from lib.api.stremio.addon_manager import AddonManager
from lib.clients.stremio import addon_client
from lib.clients.stremio.protocol import MAX_CACHE_TTL_SECONDS, MIN_CACHE_TTL_SECONDS, cache_ttl_seconds
from lib.utils.stremio import catalogs_utils


@pytest.mark.parametrize("value, expected", [(None, 300), (0, 0), (-1, 0), (1, MIN_CACHE_TTL_SECONDS), (999999, MAX_CACHE_TTL_SECONDS), ("invalid", 300)])
def test_cache_max_age_clamping(value, expected):
    assert cache_ttl_seconds(value, 300) == expected


def test_catalog_cache_uses_redacted_key_and_response_ttl(monkeypatch):
    stored = {}
    fake_cache = MagicMock()
    fake_cache.get.return_value = None
    fake_cache.set.side_effect = lambda key, value, expires: stored.update(key=key, value=value, expires=expires)
    monkeypatch.setattr(catalogs_utils, "cache", fake_cache)
    monkeypatch.setattr(catalogs_utils, "is_cache_enabled", lambda: True)
    monkeypatch.setattr(catalogs_utils, "get_cache_expiration", lambda: 12)
    monkeypatch.setattr(catalogs_utils.StremioAddonCatalogsClient, "get_catalog_info", lambda self, **kwargs: {"metas": [], "cacheMaxAge": 90})

    result = catalogs_utils.catalogs_get_cache("list_catalog", {"addon_url": "https://example.com/private-value", "catalog_type": "movie", "catalog_id": "popular"})

    assert result["cacheMaxAge"] == 90
    assert "private-value" not in stored["key"]
    assert stored["expires"] == timedelta(seconds=90)


def test_cache_max_age_zero_does_not_store(monkeypatch):
    fake_cache = MagicMock()
    fake_cache.get.return_value = None
    monkeypatch.setattr(catalogs_utils, "cache", fake_cache)
    monkeypatch.setattr(catalogs_utils.StremioAddonCatalogsClient, "get_stream_info", lambda self: {"streams": [], "cacheMaxAge": 0})

    catalogs_utils.catalogs_get_cache("list_stremio_movie", {"addon_url": "https://example.com", "catalog_type": "movie", "meta_id": "item"})

    fake_cache.set.assert_not_called()


def test_stream_search_honors_cache_max_age_with_redacted_identity(monkeypatch):
    manager = AddonManager([{"manifest": {"id": "stream.addon", "name": "Stream", "types": ["movie"], "resources": [{"name": "stream", "types": ["movie"], "idPrefixes": ["tt"]}]}, "transportUrl": "https://example.com/private-value/manifest.json", "transportName": "custom"}])
    fake_cache = MagicMock()
    fake_cache.get.return_value = None

    class Response:
        status_code = 200
        def json(self): return {"streams": [], "cacheMaxAge": 120}

    monkeypatch.setattr(addon_client, "get_addon_display_name", lambda addon: addon.manifest.name)
    client = addon_client.StremioAddonClient(manager.addons[0])
    monkeypatch.setattr(addon_client, "cache", fake_cache)
    monkeypatch.setattr(addon_client, "is_cache_enabled", lambda: True)
    monkeypatch.setattr(addon_client, "get_cache_expiration", lambda: 12)
    monkeypatch.setattr(client.session, "get", lambda *_args, **_kwargs: Response())

    assert client.search("tt123", "movies", "movies", None, None) == []

    cache_key, _value, expires = fake_cache.set.call_args[0]
    assert "private-value" not in cache_key
    assert expires == timedelta(seconds=120)
