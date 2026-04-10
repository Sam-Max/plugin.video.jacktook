from unittest.mock import MagicMock, patch

from lib.api.trakt.trakt import TraktLists
from lib.clients.trakt.trakt import TraktPresentation


def test_create_list_calls_trakt_and_clears_my_lists_cache():
    trakt_lists = TraktLists()

    with patch.object(trakt_lists, "call_trakt", return_value={"ids": {"trakt": 1}}) as call_trakt, patch(
        "lib.api.trakt.trakt.clear_trakt_list_data"
    ) as clear_list_data, patch(
        "lib.api.trakt.trakt.clear_trakt_list_contents_data"
    ) as clear_list_contents:
        trakt_lists.create_list("My List", "Description")

    call_trakt.assert_called_once_with(
        "users/me/lists",
        data={
            "name": "My List",
            "description": "Description",
            "privacy": "private",
            "display_numbers": True,
            "allow_comments": True,
        },
        with_auth=True,
        pagination=False,
    )
    clear_list_data.assert_called_once_with("my_lists")
    clear_list_contents.assert_called_once_with("my_lists")


def test_like_list_calls_expected_endpoint():
    trakt_lists = TraktLists()

    with patch.object(trakt_lists, "call_trakt", return_value={}) as call_trakt, patch(
        "lib.api.trakt.trakt.clear_trakt_list_data"
    ):
        trakt_lists.like_list("tester", 77)

    call_trakt.assert_called_once_with(
        "users/tester/lists/77/like",
        data={},
        with_auth=True,
        pagination=False,
    )


def test_show_user_lists_adds_delete_context_for_my_lists():
    fake_item = MagicMock()
    fake_info_tag = MagicMock()
    fake_item.getVideoInfoTag.return_value = fake_info_tag

    with patch("lib.clients.trakt.trakt.make_list_item", return_value=fake_item), patch(
        "lib.clients.trakt.trakt.add_kodi_dir_item"
    ):
        TraktPresentation.show_user_lists(
            {
                "name": "Owned List",
                "description": "Demo",
                "slug": "owned-list",
                "trakt_id": 55,
                "user_slug": "me",
                "can_delete": True,
                "list_type": "my_lists",
            },
            "tv",
        )

    fake_item.addContextMenuItems.assert_called_once()
    labels = [entry[0] for entry in fake_item.addContextMenuItems.call_args[0][0]]
    assert "Delete Trakt List" in labels


def test_show_create_list_entry_builds_plugin_action():
    fake_item = MagicMock()

    with patch("lib.clients.trakt.trakt.make_list_item", return_value=fake_item), patch(
        "lib.clients.trakt.trakt.add_kodi_dir_item"
    ) as add_dir_item:
        TraktPresentation.show_create_list_entry("movies")

    assert add_dir_item.call_args.kwargs["is_folder"] is False
    assert "trakt_create_list" in add_dir_item.call_args.kwargs["url"]


def test_add_item_to_list_posts_expected_payload():
    trakt_lists = TraktLists()

    with patch.object(trakt_lists, "call_trakt", return_value={}) as call_trakt, patch(
        "lib.api.trakt.trakt.clear_trakt_list_contents_data"
    ) as clear_contents:
        trakt_lists.add_item_to_list(10, "movies", {"tmdb": 44, "imdb": "tt44"})

    call_trakt.assert_called_once_with(
        "users/me/lists/10/items",
        data={"movies": [{"ids": {"tmdb": 44, "imdb": "tt44"}}]},
        with_auth=True,
        pagination=False,
    )
    clear_contents.assert_called_once_with("my_lists")


def test_remove_item_from_list_posts_expected_payload():
    trakt_lists = TraktLists()

    with patch.object(trakt_lists, "call_trakt", return_value={}) as call_trakt, patch(
        "lib.api.trakt.trakt.clear_trakt_list_contents_data"
    ):
        trakt_lists.remove_item_from_list(12, "shows", {"tmdb": 55, "tvdb": 66})

    call_trakt.assert_called_once_with(
        "users/me/lists/12/items/remove",
        data={"shows": [{"ids": {"tmdb": 55, "tvdb": 66}}]},
        with_auth=True,
        pagination=False,
    )
