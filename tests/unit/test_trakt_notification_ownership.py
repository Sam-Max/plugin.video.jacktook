from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests

from lib import navigation
from lib.api.trakt.trakt import ProviderException, TraktAuthentication, TraktBase
from lib.clients.trakt.trakt import TraktClient
from lib.services.trakt_sync import TraktSyncService


def test_provider_exception_is_side_effect_free_and_has_safe_context():
    with patch("lib.api.trakt.trakt.notification") as notification:
        error = ProviderException("diagnostic", status_code=503, operation="read")

    assert error.status_code == 503
    assert error.operation == "read"
    assert error.user_message == "Trakt is temporarily unavailable"
    notification.assert_not_called()


def test_mutation_action_owns_one_translated_failure_notification():
    api = Mock()
    api.return_value.lists.add_to_watchlist.side_effect = ProviderException(
        "diagnostic", status_code=503, operation="write"
    )

    with patch("lib.clients.trakt.trakt.TraktAPI", api), patch(
        "lib.clients.trakt.trakt.notification"
    ) as notification, patch("lib.clients.trakt.trakt.translation", return_value="watchlist failed"), patch(
        "lib.clients.trakt.trakt.kodilog"
    ):
        TraktClient.trakt_add_to_watchlist({"ids": '{"tvdb": 1}', "media_type": "tv"})

    notification.assert_called_once_with("watchlist failed", time=3000)


@pytest.mark.parametrize(
    ("action", "failure_translation"),
    [
        ("trakt_add_item_to_list", 90459),
        ("trakt_remove_item_from_list", 90537),
    ],
)
def test_list_selection_failure_uses_action_notification(action, failure_translation):
    api = Mock()
    api.return_value.lists.trakt_get_lists.side_effect = ProviderException(
        "diagnostic", status_code=503
    )

    with patch("lib.clients.trakt.trakt.TraktAPI", api), patch(
        "lib.clients.trakt.trakt.notification"
    ) as notification, patch(
        "lib.clients.trakt.trakt.translation", side_effect=lambda string_id: f"text-{string_id}"
    ), patch("lib.clients.trakt.trakt.kodilog"):
        getattr(TraktClient, action)({"media_type": "movies", "ids": "{}"})

    notification.assert_called_once_with(f"text-{failure_translation}", time=3000)
    api.return_value.lists.add_item_to_list.assert_not_called()
    api.return_value.lists.remove_item_from_list.assert_not_called()


def test_navigation_query_owns_one_safe_failure_notification():
    error = ProviderException("secret token", status_code=503)

    with patch.object(navigation.TraktClient, "handle_trakt_query", side_effect=error), patch(
        "lib.navigation.notification"
    ) as notification, patch("lib.navigation.end_of_directory") as end_directory:
        navigation.search_item(
            {"api": "trakt", "query": "trending", "mode": "movies", "category": ""}
        )

    notification.assert_called_once_with("Trakt is temporarily unavailable", time=3500)
    end_directory.assert_called_once_with(cache=False)


def test_device_auth_owns_one_safe_failure_notification():
    auth = TraktAuthentication()
    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch.object(
        auth, "call_trakt", side_effect=ProviderException("secret token", status_code=503)
    ), patch("lib.api.trakt.trakt.notification") as notification, patch(
        "lib.api.trakt.trakt.translation", return_value="Trakt Error"
    ), patch("lib.api.trakt.trakt.kodilog"):
        assert auth.trakt_get_device_code() is None

    notification.assert_called_once_with(
        "Trakt Error: Trakt is temporarily unavailable", time=5000
    )


def test_scrobble_failure_logs_without_notification():
    scrobble = TraktBase()
    response = Mock(status_code=503, headers={}, text="response body")
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    scrobble._send_request = Mock(return_value=response)

    with patch("lib.api.trakt.trakt.trakt_client", return_value="client-id"), patch(
        "lib.api.trakt.trakt.notification"
    ) as notification, patch("lib.api.trakt.trakt.kodilog"):
        try:
            scrobble.call_trakt("scrobble/start", data={}, with_auth=False)
        except ProviderException:
            pass

    notification.assert_not_called()


def test_background_sync_failure_logs_without_notification():
    api = SimpleNamespace(sync=SimpleNamespace(get_last_activities=Mock()))
    api.sync.get_last_activities.side_effect = ProviderException("diagnostic", status_code=503)
    service = TraktSyncService(api=api, monitor=Mock())

    with patch("lib.services.trakt_sync.kodilog") as kodilog, patch(
        "lib.api.trakt.trakt.notification"
    ) as notification:
        try:
            service.sync_activities()
        except ProviderException:
            pass

    assert any("failed" in call.args[0] for call in kodilog.call_args_list)
    notification.assert_not_called()
