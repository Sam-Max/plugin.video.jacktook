import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from lib.api.debrid import torbox as torbox_api
from lib.api.debrid.base import ProviderException
from lib.clients.debrid.torbox import TorboxHelper
from lib.nav import debrid as debrid_navigation
from lib.utils.general.utils import DebridType


@pytest.mark.parametrize(
    "response, expected_message",
    [
        ({"success": True, "data": {"torrent_id": 7}}, "Added to Torbox cloud"),
        ({"success": True, "queued": True}, "Added to Torbox cloud"),
        ({"success": False, "detail": "Monthly limit exceeded"}, "Monthly limit exceeded"),
        ({"success": False}, "Failed to add torrent to Torbox"),
    ],
)
def test_download_submits_magnet_and_reports_outcome(response, expected_message):
    client = torbox_api.Torbox("test-token")
    magnet = "magnet:?xt=urn:btih:testhash"
    with patch.object(client, "add_magnet_link", return_value=response) as add_magnet, patch.object(
        torbox_api, "notification"
    ) as notify, patch.object(torbox_api, "translation", return_value="Added to %s cloud"):
        result = client.download(magnet)

    add_magnet.assert_called_once_with(magnet)
    assert result == response["success"]
    notify.assert_called_once_with(expected_message)


def test_download_handles_provider_failure_without_duplicate_notification():
    client = torbox_api.Torbox("test-token")

    def fail(_magnet):
        raise ProviderException("Request timed out.")

    with patch.object(client, "add_magnet_link", side_effect=fail) as add_magnet, patch(
        "lib.api.debrid.base.notification"
    ) as provider_notify, patch.object(torbox_api, "notification") as notify:
        result = client.download("magnet:test")

    assert result is False
    add_magnet.assert_called_once_with("magnet:test")
    provider_notify.assert_called_once_with("Request timed out.")
    notify.assert_not_called()


def test_cloud_lists_every_video_and_preserves_ids_in_playback_and_download_actions():
    helper = TorboxHelper()
    helper.client = MagicMock()
    helper.client.get_user_torrent_list.return_value = {
        "success": True,
        "data": [
            {
                "id": "season-pack",
                "hash": "packhash",
                "download_present": True,
                "files": [
                    {"id": "episode-1", "name": "Show.S01E01.mkv", "size": 100},
                    {"id": "episode-2", "name": "Show.S01E02.mkv", "size": 200},
                    {"id": "text", "name": "readme.txt", "size": 1},
                ],
            },
            {"id": "pending", "download_present": False, "files": []},
        ],
    }
    items = []

    def make_item(*_args):
        item = MagicMock()
        items.append(item)
        return item

    with patch.object(debrid_navigation, "TorboxHelper", return_value=helper), patch.object(
        debrid_navigation.cache, "get", return_value=None
    ) as cache_get, patch.object(debrid_navigation.cache, "set") as cache_set, patch.object(
        debrid_navigation, "build_list_item", side_effect=make_item
    ), patch.object(debrid_navigation, "addDirectoryItem") as add_item, patch.object(
        debrid_navigation, "end_of_directory"
    ), patch.object(debrid_navigation, "apply_section_view"):
        debrid_navigation.get_tb_downloads({})

    assert add_item.call_count == 2
    cache_key = f"cloud_downloads|{DebridType.TB}|1|files-v2"
    cache_get.assert_called_once_with(cache_key)
    assert cache_set.call_args.args[0] == cache_key
    assert len(cache_set.call_args.args[1]) == 2
    selected_ids = set()
    for call, item in zip(add_item.call_args_list, items):
        query = parse_qs(urlparse(call.args[1]).query)
        assert query["action"] == ["play_media"]
        data = json.loads(query["data"][0])
        assert data["torrent_id"] == "season-pack"
        assert data["info_hash"] == "packhash"
        selected_ids.add(data["file_id"])
        action = item.addContextMenuItems.call_args.args[0][0][1]
        download_query = parse_qs(urlparse(action[len("RunPlugin(") : -1]).query)
        assert download_query["action"] == ["download_cloud_file"]
        assert download_query["torrent_id"] == ["season-pack"]
        assert download_query["file_id"] == [data["file_id"]]
        assert download_query["filename"] == [data["title"]]
        item.setProperty.assert_called_once_with("IsPlayable", "true")
        assert call.kwargs["isFolder"] is False
    assert selected_ids == {"episode-1", "episode-2"}


@pytest.mark.parametrize(
    "total, page, expected_ids, next_page",
    [
        (0, None, [], None),
        (20, None, list(range(20)), None),
        (21, None, list(range(20)), 2),
        (40, "2", list(range(20, 40)), None),
        (41, "2", list(range(20, 40)), 3),
        (41, "3", [40], None),
        (41, "4", [], None),
        (21, "invalid", list(range(20)), 2),
        (21, "0", list(range(20)), 2),
        (21, "-1", list(range(20)), 2),
    ],
)
def test_cloud_pagination_limits_videos_and_preserves_order_and_ids(
    total, page, expected_ids, next_page
):
    # Descending names give a known order using the existing cloud sort.
    downloads = [
        {"name": f"video-{total - i:03d}.mkv", "torrent_id": "pack", "file_id": str(i)}
        for i in range(total)
    ]
    params = {} if page is None else {"page": page}
    with patch.object(debrid_navigation.cache, "get", return_value=downloads), patch.object(
        debrid_navigation.cache, "set"
    ) as cache_set, patch.object(debrid_navigation, "TorboxHelper") as helper, patch.object(
        debrid_navigation, "addDirectoryItem"
    ) as add_item, patch.object(
        debrid_navigation, "build_list_item", side_effect=lambda *_args: MagicMock()
    ), patch.object(debrid_navigation, "end_of_directory") as end_directory, patch.object(
        debrid_navigation, "apply_section_view"
    ):
        debrid_navigation.get_tb_downloads(params)

    video_calls = [call for call in add_item.call_args_list if not call.kwargs["isFolder"]]
    folder_calls = [call for call in add_item.call_args_list if call.kwargs["isFolder"]]
    actual_ids = []
    for call in video_calls:
        query = parse_qs(urlparse(call.args[1]).query)
        assert query["action"] == ["play_media"]
        data = json.loads(query["data"][0])
        assert data["torrent_id"] == "pack"
        actual_ids.append(int(data["file_id"]))
        menu_action = call.args[2].addContextMenuItems.call_args.args[0][0][1]
        menu_query = parse_qs(urlparse(menu_action[len("RunPlugin(") : -1]).query)
        assert menu_query["file_id"] == [data["file_id"]]
        assert menu_query["torrent_id"] == ["pack"]
    assert actual_ids == expected_ids
    assert len(video_calls) <= 20
    if next_page is None:
        assert folder_calls == []
    else:
        assert len(folder_calls) == 1
        query = parse_qs(urlparse(folder_calls[0].args[1]).query)
        assert query == {"action": ["get_tb_downloads"], "page": [str(next_page)]}
    helper.assert_not_called()
    cache_set.assert_not_called()
    assert len(downloads) == total
    end_directory.assert_called_once()


@pytest.mark.parametrize(
    "total, page, label", [(21, 1, "Next Page (2/2)"), (101, 3, "Next Page (4/6)")]
)
def test_cloud_next_page_label_includes_destination_and_total(total, page, label):
    downloads = [{"name": f"video-{i}.mkv"} for i in range(total)]
    with patch.object(debrid_navigation.cache, "get", return_value=downloads), patch.object(
        debrid_navigation, "build_list_item", return_value=MagicMock()
    ) as build_item, patch.object(debrid_navigation, "addDirectoryItem"), patch.object(
        debrid_navigation, "end_of_directory"
    ), patch.object(debrid_navigation, "apply_section_view"):
        debrid_navigation.get_tb_downloads({"page": str(page)})

    assert build_item.call_args.args[0] == label


def test_cloud_next_page_uses_existing_pagination_icon():
    downloads = [{"name": f"video-{i}.mkv"} for i in range(21)]
    with patch.object(debrid_navigation.cache, "get", return_value=downloads), patch.object(
        debrid_navigation, "build_list_item", return_value=MagicMock()
    ) as build_item, patch.object(debrid_navigation, "addDirectoryItem"), patch.object(
        debrid_navigation, "end_of_directory"
    ), patch.object(debrid_navigation, "apply_section_view"):
        debrid_navigation.get_tb_downloads({})

    icon = build_item.call_args.args[1]
    assert (Path(__file__).resolve().parents[2] / "resources" / "img" / icon).is_file()
    assert icon == "nextpage.png"
