from unittest.mock import MagicMock

import xbmc

from lib.api.stremio.addon_manager import AddonManager
from lib.clients.stremio import addon_client


def _addon():
    manager = AddonManager(
        [
            {
                "manifest": {
                    "id": "stream.addon",
                    "name": "Stream",
                    "types": ["movie"],
                    "resources": [{"name": "stream", "types": ["movie"], "idPrefixes": ["tt"]}],
                },
                "transportUrl": "https://example.com/private-value/manifest.json",
                "transportName": "custom",
            }
        ]
    )
    return manager.addons[0]


def _client_failing_with(monkeypatch, error):
    monkeypatch.setattr(addon_client, "get_addon_display_name", lambda addon: "Stream")
    client = addon_client.StremioAddonClient(_addon())
    monkeypatch.setattr(addon_client, "cache", MagicMock(get=MagicMock(return_value=None)))
    monkeypatch.setattr(client.session, "get", MagicMock(side_effect=error))
    notifications = []
    monkeypatch.setattr(client, "handle_exception", lambda message: notifications.append(message))
    logged = []
    monkeypatch.setattr(
        addon_client,
        "kodilog",
        lambda message, level=None: logged.append((message, level)),
    )
    return client, logged, notifications


def test_search_failure_is_logged_with_exception_type_and_error_level(monkeypatch):
    client, logged, notifications = _client_failing_with(
        monkeypatch, ConnectionError("connection reset")
    )

    assert client.search("tt123", "movies", "movies", None, None) == []

    assert notifications == ["Error in Stream"]
    messages = [message for message, level in logged if level == xbmc.LOGERROR]
    assert len(messages) == 1
    assert "ConnectionError" in messages[0]
    assert "connection reset" in messages[0]


def test_search_failure_log_redacts_the_private_addon_url(monkeypatch):
    error = RuntimeError(
        "bad response from https://example.com/private-value/stream/movie/tt123.json"
    )
    client, logged, _ = _client_failing_with(monkeypatch, error)

    client.search("tt123", "movies", "movies", None, None)

    messages = [message for message, level in logged if level == xbmc.LOGERROR]
    assert messages
    assert "private-value" not in messages[0]
    assert "<addon-url>" in messages[0]
