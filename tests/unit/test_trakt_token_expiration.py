from unittest.mock import patch

import pytest

from lib.api.trakt.trakt import TraktAuthentication, TraktBase


def token_response(**overrides):
    result = {
        "access_token": "access",
        "refresh_token": "refresh",
        "created_at": 1_000,
        "expires_in": 604_800,
    }
    result.update(overrides)
    return result


def test_valid_seven_day_response_uses_server_expiration():
    api = TraktBase()

    expiration = api._oauth_token_expiration(token_response(), receipt_time=5_000)

    assert expiration == 605_800


def test_initial_device_token_install_persists_response_expiration():
    api = TraktAuthentication()
    token = token_response(created_at=10_000, expires_in=600)
    with patch.object(api, "trakt_get_device_code", return_value={"valid": True}), patch.object(
        api, "trakt_get_device_token", return_value=token
    ), patch.object(api, "call_trakt", return_value={"username": "tester"}), patch(
        "lib.api.trakt.trakt.set_property"
    ) as set_property, patch("lib.api.trakt.trakt.set_setting"), patch(
        "lib.api.trakt.trakt.notification"
    ):
        result = api.trakt_authenticate()

    assert result is True
    assert set_property.call_args_list[-1].args == ("trakt_expires", "10600.0")


def test_refresh_persists_response_expiration():
    api = TraktBase()
    api.trakt_refresh = "old-refresh"
    token = token_response(created_at=20_000, expires_in=1_200)
    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch(
        "lib.api.trakt.trakt.trakt_secret", return_value="client-secret"
    ), patch.object(api, "call_trakt", return_value=token), patch(
        "lib.api.trakt.trakt.set_property"
    ) as set_property:
        result = api.trakt_refresh_token()

    assert result is True
    assert set_property.call_args_list[-1].args == ("trakt_expires", "21200.0")


@pytest.mark.parametrize("created_at", [None, "bad", False, float("nan"), float("inf")])
def test_invalid_created_at_uses_receipt_time(created_at):
    api = TraktBase()

    expiration = api._oauth_token_expiration(
        token_response(created_at=created_at, expires_in=600), receipt_time=10_000
    )

    assert expiration == 10_600


@pytest.mark.parametrize(
    ("future_offset", "expected_expiration"),
    [(300, 10_900), (300.001, 10_600), (1e308, 10_600)],
)
def test_future_created_at_respects_clock_skew_tolerance(
    future_offset, expected_expiration
):
    api = TraktBase()

    expiration = api._oauth_token_expiration(
        token_response(created_at=10_000 + future_offset, expires_in=600),
        receipt_time=10_000,
    )

    assert expiration == expected_expiration


@pytest.mark.parametrize(
    "expires_in",
    [None, "bad", False, 0, -1, float("nan"), float("inf"), 10**1000],
)
def test_invalid_expires_in_uses_compatibility_fallback(expires_in):
    api = TraktBase()

    expiration = api._oauth_token_expiration(
        token_response(expires_in=expires_in), receipt_time=10_000
    )

    assert expiration == 92_800


def test_overflowing_combined_expiration_uses_compatibility_fallback():
    api = TraktBase()

    expiration = api._oauth_token_expiration(
        token_response(created_at=1e308, expires_in=1e308), receipt_time=10_000
    )

    assert expiration == 92_800


@pytest.mark.parametrize(
    ("seconds_until_expiry", "refresh_expected"),
    [(3_600, False), (3_599.999, True), (0, True), (-1, True)],
)
def test_refresh_threshold_clock_boundary(seconds_until_expiry, refresh_expected):
    api = TraktBase()
    now = 50_000
    properties = {
        "trakt_expires": str(now + seconds_until_expiry),
        "trakt_refresh": "refresh",
    }
    with patch("lib.api.trakt.trakt.get_property", side_effect=properties.get), patch(
        "lib.api.trakt.trakt.time.time", return_value=now
    ), patch.object(api, "trakt_refresh_token", return_value=True) as refresh:
        result = api.ensure_token_valid()

    assert result is (True if refresh_expected else None)
    assert refresh.called is refresh_expected


def test_stale_created_at_persists_expired_value_and_triggers_refresh():
    api = TraktBase()
    expiration = api._oauth_token_expiration(
        token_response(created_at=1_000, expires_in=600), receipt_time=50_000
    )
    properties = {
        "trakt_expires": str(expiration),
        "trakt_refresh": "refresh",
    }
    with patch("lib.api.trakt.trakt.get_property", side_effect=properties.get), patch(
        "lib.api.trakt.trakt.time.time", return_value=50_000
    ), patch.object(api, "trakt_refresh_token", return_value=True) as refresh:
        result = api.ensure_token_valid()

    assert expiration == 1_600
    assert result is True
    refresh.assert_called_once_with()
