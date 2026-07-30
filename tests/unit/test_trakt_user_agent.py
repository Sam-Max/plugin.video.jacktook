from unittest.mock import Mock, patch

import pytest

from lib.api.trakt.trakt import TraktAuthentication, TraktBase, TraktCache


def response(payload=None):
    result = Mock(status_code=200, headers={}, text="response body")
    result.json.return_value = {} if payload is None else payload
    return result


def assert_contract_headers(headers, client_id="client-id"):
    assert headers == {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": client_id,
        "User-Agent": "Jacktook/1.15.0",
    }


def test_header_builder_uses_kodi_addon_name_and_version():
    api = TraktBase()
    with patch("lib.api.trakt.trakt.ADDON_NAME", "Jacktook"), patch(
        "lib.api.trakt.trakt.ADDON_VERSION", "1.15.0"
    ), patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"):
        assert_contract_headers(api._trakt_headers())


@pytest.mark.parametrize(
    "name, version", [(None, None), ("", ""), ("bad\rname", "bad\nversion")]
)
def test_header_builder_has_safe_deterministic_metadata_fallback(name, version):
    api = TraktBase()
    with patch("lib.api.trakt.trakt.ADDON_NAME", name), patch(
        "lib.api.trakt.trakt.ADDON_VERSION", version
    ):
        assert api._trakt_user_agent() == "Jacktook/0.0.0"


def test_shared_rest_request_includes_contract_headers():
    api = TraktBase()
    api._send_request = Mock(return_value=response())

    with patch("lib.api.trakt.trakt.ADDON_NAME", "Jacktook"), patch(
        "lib.api.trakt.trakt.ADDON_VERSION", "1.15.0"
    ), patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"):
        api.call_trakt("movies/trending", with_auth=False)

    assert_contract_headers(api._send_request.call_args.args[3])


def test_device_code_request_includes_contract_headers():
    api = TraktAuthentication()
    api._send_request = Mock(
        return_value=response(
            {
                "device_code": "device-code",
                "user_code": "USER-CODE",
                "verification_url": "https://trakt.tv/activate",
                "expires_in": 600,
                "interval": 5,
            }
        )
    )

    with patch("lib.api.trakt.trakt.ADDON_NAME", "Jacktook"), patch(
        "lib.api.trakt.trakt.ADDON_VERSION", "1.15.0"
    ), patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"):
        api.trakt_get_device_code()

    assert_contract_headers(api._send_request.call_args.args[3])


def test_refresh_and_revoke_requests_include_contract_headers():
    api = TraktAuthentication()
    api.trakt_refresh = "refresh-token"
    api._send_request = Mock(
        side_effect=[
            response({"access_token": "access", "refresh_token": "refresh"}),
            response(),
        ]
    )

    with patch("lib.api.trakt.trakt.ADDON_NAME", "Jacktook"), patch(
        "lib.api.trakt.trakt.ADDON_VERSION", "1.15.0"
    ), patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch(
        "lib.api.trakt.trakt.trakt_secret", return_value="client-secret"
    ), patch("lib.api.trakt.trakt.set_property"), patch(
        "lib.api.trakt.trakt.set_setting"
    ), patch(
        "lib.api.trakt.trakt.get_property", return_value="access-token"
    ), patch("lib.api.trakt.trakt.notification"), patch.object(
        TraktCache, "clear_all_trakt_cache_data"
    ):
        assert api.trakt_refresh_token() is True
        api.trakt_revoke_authentication()

    refresh_headers = api._send_request.call_args_list[0].args[3]
    revoke_headers = api._send_request.call_args_list[1].args[3]
    assert_contract_headers(refresh_headers)
    assert_contract_headers(revoke_headers)


@pytest.mark.parametrize(
    ("method", "data", "is_delete", "request_name"),
    [
        ("post", {}, False, "post"),
        ("delete", {}, False, "delete"),
        ("sort_by_headers", None, False, "get"),
        (None, {}, False, "post"),
        (None, None, True, "delete"),
        (None, None, False, "get"),
    ],
)
def test_every_shared_transport_dispatch_forwards_user_agent(
    method, data, is_delete, request_name
):
    api = TraktBase()
    headers = {"User-Agent": "Jacktook/1.15.0"}

    with patch(
        f"lib.api.trakt.trakt.requests.{request_name}", return_value=response()
    ) as request:
        api._send_request("movies/trending", {}, data, headers, is_delete, method)

    assert request.call_args.kwargs["headers"] is headers
