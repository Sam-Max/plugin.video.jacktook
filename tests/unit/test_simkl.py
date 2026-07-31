from unittest.mock import MagicMock

import requests

from lib.api.simkl import SimklClient, is_simkl_scrobbling_enabled
from lib.clients.simkl import SIMKL, SIMKL_CLIENT_ID


def test_auth_client_and_legacy_metadata_share_default_client_id(monkeypatch):
    monkeypatch.setattr("lib.api.simkl.get_setting", lambda _key: "")

    assert SimklClient().client_id == SIMKL_CLIENT_ID
    assert SIMKL().ClientID == SIMKL_CLIENT_ID


def test_scrobbling_does_not_require_client_id_override(monkeypatch):
    values = {
        "simkl_enabled": True,
        "simkl_scrobbling_enabled": True,
        "simkl_authenticated": True,
        "simkl_access_token": "token",
        "simkl_client_id": "",
    }
    monkeypatch.setattr("lib.api.simkl.get_setting", values.get)

    assert is_simkl_scrobbling_enabled() is True


def test_movie_scrobble_uses_authenticated_simkl_contract(monkeypatch):
    response = MagicMock(status_code=200)
    post = MagicMock(return_value=response)
    monkeypatch.setattr("lib.api.simkl.requests.post", post)
    monkeypatch.setattr("lib.api.simkl.ADDON_NAME", "Jacktook")
    monkeypatch.setattr("lib.api.simkl.ADDON_VERSION", "1.16.0")
    client = SimklClient(client_id="client-id", access_token="token")

    assert client.scrobble(
        "start", {"mode": "movies", "ids": {"tmdb_id": "123"}, "progress": 12.345}
    )

    post.assert_called_once_with(
        "https://api.simkl.com/scrobble/start",
        params={
            "client_id": "client-id",
            "app-name": "Jacktook",
            "app-version": "1.16.0",
        },
        headers={"User-Agent": "Jacktook/1.16.0", "Authorization": "Bearer token"},
        json={"movie": {"ids": {"tmdb": 123}}, "progress": 12.35},
        timeout=5,
    )


def test_tv_payload_requires_canonical_identity_and_episode_coordinates():
    assert SimklClient.scrobble_payload(
        {
            "mode": "tv",
            "ids": {"tmdb_id": 456},
            "tv_data": {"season": "2", "episode": "3"},
            "progress": 101,
        }
    ) == {
        "show": {"ids": {"tmdb": 456}},
        "episode": {"season": 2, "number": 3},
        "progress": 100,
    }
    assert (
        SimklClient.scrobble_payload(
            {
                "mode": "tv",
                "ids": {"tmdb_id": "opaque-id"},
                "tv_data": {"season": 2, "episode": 3},
            }
        )
        is None
    )
    assert (
        SimklClient.scrobble_payload(
            {"mode": "tv", "ids": {"tmdb_id": 456}, "tv_data": {"season": 2}}
        )
        is None
    )


def test_tv_payload_allows_season_zero_specials_but_rejects_bool_season():
    data = {
        "mode": "tv",
        "ids": {"tmdb_id": 456},
        "tv_data": {"season": 0, "episode": 1},
        "progress": 50,
    }

    assert SimklClient.scrobble_payload(data)["episode"] == {"season": 0, "number": 1}
    data["tv_data"]["season"] = False
    assert SimklClient.scrobble_payload(data) is None


def test_scrobble_transport_failure_is_contained(monkeypatch):
    monkeypatch.setattr(
        "lib.api.simkl.requests.post", MagicMock(side_effect=requests.Timeout("offline"))
    )
    log = MagicMock()
    monkeypatch.setattr("lib.api.simkl.kodilog", log)

    result = SimklClient("client-id", "token").scrobble(
        "stop", {"mode": "movies", "ids": {"tmdb_id": 123}, "progress": 90}
    )

    assert result is False
    assert "offline" not in " ".join(str(item) for item in log.call_args_list)


def test_rate_limit_starts_cooldown_without_retry(monkeypatch):
    SimklClient._scrobble_backoff_until = 0
    response = MagicMock(status_code=429, headers={"Retry-After": "30"}, text="RATE_LIMIT")
    post = MagicMock(return_value=response)
    monkeypatch.setattr("lib.api.simkl.requests.post", post)
    monkeypatch.setattr("lib.api.simkl.time.monotonic", lambda: 100)
    client = SimklClient("client-id", "token")
    data = {"mode": "movies", "ids": {"tmdb_id": 123}, "progress": 50}

    assert client.scrobble("pause", data) is False
    assert client.scrobble("start", data) is False

    assert post.call_count == 1
    assert SimklClient._scrobble_backoff_until == 130
    SimklClient._scrobble_backoff_until = 0


def test_pin_auth_persists_access_token(monkeypatch):
    client = SimklClient("client-id", "")
    monkeypatch.setattr(
        client,
        "request_pin",
        lambda: {
            "user_code": "ABCD",
            "verification_url": "https://simkl.com/pin",
            "expires_in": 60,
            "interval": 1,
        },
    )
    poll = MagicMock(status_code=200)
    poll.json.return_value = {"result": "OK", "access_token": "new-token"}
    monkeypatch.setattr("lib.api.simkl.requests.get", MagicMock(return_value=poll))
    dialog = MagicMock()
    dialog.iscanceled = False
    monkeypatch.setattr("lib.api.simkl.QRProgressDialog", MagicMock(return_value=dialog))
    monkeypatch.setattr("lib.api.simkl.make_qrcode", MagicMock(return_value="qr.png"))
    monkeypatch.setattr("lib.api.simkl.copy2clip", MagicMock())
    monkeypatch.setattr("lib.api.simkl.sleep", MagicMock())
    monkeypatch.setattr("lib.api.simkl.time.monotonic", MagicMock(side_effect=[0, 0, 0]))
    monitor = MagicMock()
    monitor.abortRequested.return_value = False
    monkeypatch.setattr("lib.api.simkl.xbmc.Monitor", MagicMock(return_value=monitor))
    settings = MagicMock()
    monkeypatch.setattr("lib.api.simkl.set_setting", settings)

    assert client.authenticate() is True
    assert settings.call_args_list[-2].args == ("simkl_access_token", "new-token")
    assert settings.call_args_list[-1].args == ("simkl_authenticated", "true")


def test_logout_clears_persisted_auth(monkeypatch):
    settings = MagicMock()
    monkeypatch.setattr("lib.api.simkl.set_setting", settings)
    client = SimklClient("client-id", "token")

    client.logout()

    assert client.access_token == ""
    assert settings.call_args_list[0].args == ("simkl_access_token", "")
    assert settings.call_args_list[1].args == ("simkl_authenticated", "false")
