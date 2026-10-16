from datetime import timedelta
from unittest.mock import MagicMock, call, patch

import pytest
import requests

from lib.api.debrid.torbox import Torbox
from lib.clients.debrid import debrider as debrider_helper
from lib.clients.debrid import easydebrid as easydebrid_helper
from lib.clients.debrid import torbox as torbox_helper
from lib.nav import debrid as debrid_navigation
from lib.utils.general import utils


@pytest.fixture(autouse=True)
def no_live_ip_lookup():
    with patch.object(utils.requests, "get", side_effect=AssertionError("Unexpected HTTP request")):
        yield


def test_public_ip_default_cache_behavior_is_unchanged():
    reply = MagicMock(text="203.0.113.1\n")
    with patch.object(utils.cache, "get", return_value=None) as get_cache, patch.object(
        utils.cache, "set"
    ) as set_cache, patch.object(
        utils.requests, "get", return_value=reply
    ) as http_get, patch.object(utils, "get_cache_expiration", return_value=4):
        assert utils.get_public_ip() == "203.0.113.1"
    get_cache.assert_called_once_with("public_ip")
    set_cache.assert_called_once_with("public_ip", "203.0.113.1", timedelta(hours=4))
    http_get.assert_called_once_with("https://ipconfig.io/ip", timeout=5)


def test_non_torbox_helpers_keep_generic_public_ip_lookup_defaults():
    with patch.object(
        easydebrid_helper, "get_public_ip", return_value="203.0.113.10"
    ) as easy_ip, patch.object(
        debrider_helper, "get_public_ip", return_value="203.0.113.11"
    ) as debrider_ip:
        easydebrid_helper.EasyDebridHelper()
        debrider_helper.DebriderHelper()

    easy_ip.assert_called_once_with()
    debrider_ip.assert_called_once_with()


def test_torbox_ip_cache_is_separate_and_refreshes_after_one_minute():
    now = [0]
    stored = {"public_ip": ("203.0.113.99", 3600)}

    def get_cache(key):
        value, expires = stored.get(key, (None, 0))
        return value if now[0] < expires else None

    def set_cache(key, value, expires):
        stored[key] = (value, now[0] + expires.total_seconds())

    with patch.object(utils.cache, "get", side_effect=get_cache), patch.object(
        utils.cache, "set", side_effect=set_cache
    ) as cache_set, patch.object(
        utils.requests,
        "get",
        side_effect=[MagicMock(text="203.0.113.1"), MagicMock(text="203.0.113.2")],
    ) as http_get:
        assert torbox_helper.get_torbox_public_ip() == "203.0.113.1"
        now[0] = 59
        assert torbox_helper.get_torbox_public_ip() == "203.0.113.1"
        now[0] = 60
        assert torbox_helper.get_torbox_public_ip() == "203.0.113.2"

    assert http_get.call_count == 2
    assert all(item.args[0] == "torbox_public_ip" for item in cache_set.call_args_list)
    assert all(item.args[2] == timedelta(minutes=1) for item in cache_set.call_args_list)
    assert stored["public_ip"] == ("203.0.113.99", 3600)


def test_failed_torbox_ip_lookup_falls_back_without_caching_failure():
    with patch.object(utils.cache, "get", return_value=None), patch.object(
        utils.cache, "set"
    ) as cache_set, patch.object(
        utils.requests, "get", side_effect=requests.ConnectionError("offline")
    ) as http_get:
        assert torbox_helper.get_torbox_public_ip() is None
    assert http_get.call_count == 2
    cache_set.assert_not_called()


def test_cloud_link_cache_is_bound_to_ip_and_reuses_only_matching_link():
    helper = MagicMock()
    helper.client.create_download_link.side_effect = [
        {"data": "https://cdn-a/video"},
        {"data": "https://cdn-b/video"},
    ]
    stored = {"tb_download_link|7|2": "https://old-cdn/video"}
    data = {"debrid_type": "TB", "torrent_id": 7, "file_id": 2}
    with patch.object(debrid_navigation, "TorboxHelper", return_value=helper), patch.object(
        debrid_navigation,
        "get_torbox_public_ip",
        side_effect=["203.0.113.1", "203.0.113.1", "203.0.113.2"],
        create=True,
    ) as get_ip, patch.object(debrid_navigation.cache, "get", side_effect=stored.get), patch.object(
        debrid_navigation.cache,
        "set",
        side_effect=lambda key, value, _expires: stored.update({key: value}),
    ):
        assert debrid_navigation.resolve_cloud_download_url(data) == "https://cdn-a/video"
        assert debrid_navigation.resolve_cloud_download_url(data) == "https://cdn-a/video"
        assert debrid_navigation.resolve_cloud_download_url(data) == "https://cdn-b/video"

    assert get_ip.call_count == 3
    assert helper.client.create_download_link.call_args_list == [
        call(7, 2, "203.0.113.1"),
        call(7, 2, "203.0.113.2"),
    ]
    assert stored["tb_download_link|7|2|203.0.113.1"] == "https://cdn-a/video"
    assert stored["tb_download_link|7|2|203.0.113.2"] == "https://cdn-b/video"


def test_unknown_ip_does_not_reuse_or_store_cdn_link():
    helper = MagicMock()
    helper.client.create_download_link.return_value = {"data": "https://automatic-cdn/video"}
    with patch.object(debrid_navigation, "TorboxHelper", return_value=helper), patch.object(
        debrid_navigation, "get_torbox_public_ip", return_value=None, create=True
    ), patch.object(
        debrid_navigation.cache, "get", return_value="https://old-cdn/video"
    ) as get_cache, patch.object(debrid_navigation.cache, "set") as set_cache:
        result = debrid_navigation.resolve_cloud_download_url(
            {"debrid_type": "TB", "torrent_id": 7, "file_id": 2}
        )
    assert result == "https://automatic-cdn/video"
    helper.client.create_download_link.assert_called_once_with(7, 2, None)
    get_cache.assert_not_called()
    set_cache.assert_not_called()


@pytest.mark.parametrize("ip", ["203.0.113.1", None])
def test_download_request_leaves_region_selection_to_torbox(ip):
    client = Torbox("test-token")
    with patch.object(
        client, "_make_request", return_value={"success": True, "data": "url"}
    ) as request:
        assert client.create_download_link(7, 2, ip) == {"success": True, "data": "url"}
    params = request.call_args.kwargs["params"]
    assert params == {
        "token": "test-token",
        "torrent_id": 7,
        "file_id": 2,
        **({"user_ip": ip} if ip else {}),
    }
