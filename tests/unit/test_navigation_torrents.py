from unittest.mock import MagicMock, patch

from lib import navigation


def test_torrent_categories_normalize_uncategorized_and_sort_custom_categories():
    categories = navigation._torrent_categories(
        [
            {"category": " TV "},
            {"category": "alpha"},
            {"category": None},
            {"category": ""},
            {"category": 1},
            {"category": "Alpha"},
        ]
    )

    assert categories == ["Alpha", "alpha", "TV", None]


def test_torrents_root_lists_category_folders():
    api = MagicMock()
    api.torrents.return_value = [
        {"hash": "movie", "category": "movie"},
        {"hash": "custom", "category": "Custom"},
        {"hash": "uncategorized"},
    ]

    with patch.object(navigation, "JACKTORR_ADDON", True), patch.object(
        navigation, "get_torrserver_api", return_value=api
    ), patch.object(navigation, "translation", side_effect=lambda value: f"label-{value}"), patch.object(
        navigation, "build_list_item", side_effect=lambda label, *_args, **_kwargs: MagicMock(label=label)
    ), patch.object(
        navigation, "build_url", side_effect=lambda action, **params: (action, params)
    ), patch.object(navigation, "addDirectoryItem") as add_directory_item, patch.object(
        navigation, "end_of_directory"
    ), patch.object(navigation, "apply_section_view"):
        navigation.torrents({})

    assert [call.args[1] for call in add_directory_item.call_args_list] == [
        ("torrents", {"category": "Custom"}),
        ("torrents", {"category": "movie"}),
        ("torrents", {"uncategorized": True}),
    ]


def test_torrents_category_route_filters_entries_and_preserves_actions():
    api = MagicMock()
    api.torrents.return_value = [
        {"hash": "selected", "title": "Selected", "category": "TV", "stat": 1},
        {"hash": "other", "title": "Other", "category": "movie", "stat": 1},
    ]
    torrent_item = MagicMock()

    with patch.object(navigation, "JACKTORR_ADDON", True), patch.object(
        navigation, "get_torrserver_api", return_value=api
    ), patch.object(navigation, "translation", side_effect=lambda value: f"label-{value}"), patch.object(
        navigation, "build_list_item", return_value=torrent_item
    ), patch.object(
        navigation, "build_url", side_effect=lambda action, **params: (action, params)
    ), patch.object(navigation, "action_url_run", return_value="action"), patch.object(
        navigation, "play_info_hash", return_value="play"
    ), patch("lib.utils.torrent.torrserver_utils.get_torrent_meta", return_value={}), patch.object(
        navigation, "addDirectoryItem"
    ) as add_directory_item, patch.object(navigation, "end_of_directory"), patch.object(
        navigation, "apply_section_view"
    ):
        navigation.torrents({"category": "TV"})

    add_directory_item.assert_called_once()
    assert add_directory_item.call_args.args[1] == ("torrent_files", {"info_hash": "selected"})
    torrent_item.addContextMenuItems.assert_called_once()


def test_torrent_item_uses_shared_display_metadata_for_video_info_tag():
    api = MagicMock(_base_url="http://server:8090")
    torrent_item = MagicMock()
    video_tag = MagicMock()
    torrent_item.getVideoInfoTag.return_value = video_tag

    with patch.object(navigation, "get_torrserver_api", return_value=api), patch.object(
        navigation, "get_display_metadata", return_value={"title": "Shared", "plot": "Plot", "poster": "Poster"}
    ), patch.object(
        navigation, "build_list_item", return_value=torrent_item
    ) as build_item, patch.object(
        navigation, "translation", side_effect=lambda value: str(value)
    ), patch.object(
        navigation, "action_url_run", return_value="action"
    ), patch.object(
        navigation, "play_info_hash", return_value="play"
    ), patch("lib.utils.torrent.torrserver_utils.get_torrent_meta", return_value={}), patch.object(
        navigation, "addDirectoryItem"
    ):
        navigation._add_torrent_items([{"hash": "a" * 40, "title": "Server title", "stat": 0}])

    build_item.assert_called_once_with("Shared", "magnet.png", poster_path="Poster")
    video_tag.setTitle.assert_called_once_with("Shared")
    video_tag.setPlot.assert_called_once_with("Plot")


def test_torrent_item_falls_back_to_legacy_video_info_labels():
    api = MagicMock(_base_url="http://server:8090")
    torrent_item = MagicMock(spec=["setInfo", "addContextMenuItems"])

    with patch.object(navigation, "get_torrserver_api", return_value=api), patch.object(
        navigation, "get_display_metadata", return_value={"title": "Shared", "plot": "Plot", "poster": "Poster"}
    ), patch.object(
        navigation, "build_list_item", return_value=torrent_item
    ), patch.object(
        navigation, "translation", side_effect=lambda value: str(value)
    ), patch.object(
        navigation, "action_url_run", return_value="action"
    ), patch.object(
        navigation, "play_info_hash", return_value="play"
    ), patch("lib.utils.torrent.torrserver_utils.get_torrent_meta", return_value={}), patch.object(
        navigation, "addDirectoryItem"
    ):
        navigation._add_torrent_items([{"hash": "a" * 40, "title": "Server title", "stat": 0}])

    torrent_item.setInfo.assert_called_once_with("video", {"title": "Shared", "plot": "Plot"})
