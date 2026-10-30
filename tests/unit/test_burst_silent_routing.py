from unittest.mock import MagicMock, patch

import pytest

import lib.jacktook.providers as providers


def _run_search(provider_ids, silent, supports_silent=True):
    listener = MagicMock()
    listener.__enter__.return_value.data = {}
    with patch.object(providers, "get_providers", return_value=provider_ids), patch.object(
        providers, "send_to_providers"
    ) as send, patch.object(
        providers, "ProviderListenerDialog", return_value=listener
    ), patch.object(
        providers, "_burst_supports_silent", return_value=supports_silent
    ):
        with pytest.raises(Exception, match="No results found"):
            providers.search("search_movie", "tt1", "Title", silent=silent)
    return send


def test_silent_is_sent_only_to_burst():
    send = _run_search(["script.jacktook.burst", "script.jacktook.other"], silent=True)
    calls = {call.args[0][0]: call.kwargs for call in send.call_args_list}

    assert calls["script.jacktook.burst"]["silent"] is True
    assert "silent" not in calls["script.jacktook.other"]


def test_non_silent_search_still_reaches_burst():
    send = _run_search(["script.jacktook.burst"], silent=False)
    calls = {call.args[0][0]: call.kwargs for call in send.call_args_list}

    assert calls["script.jacktook.burst"]["silent"] is False


def test_silent_skipped_for_old_burst_builds():
    send = _run_search(["script.jacktook.burst"], silent=True, supports_silent=False)
    (call,) = send.call_args_list

    assert "silent" not in call.kwargs


def test_no_silent_kwarg_without_burst():
    send = _run_search(["script.jacktook.other"], silent=True)
    (call,) = send.call_args_list

    assert "silent" not in call.kwargs
