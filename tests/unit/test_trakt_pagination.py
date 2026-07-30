from unittest.mock import MagicMock, patch

from lib.api.trakt.trakt import TraktBase, TraktLists
from lib.clients.trakt.trakt import Trakt, TraktClient, TraktPresentation


def pagination(page, page_count, limit=20, item_count=50):
    return {
        "X-Pagination-Page": page,
        "X-Pagination-Limit": limit,
        "X-Pagination-Page-Count": page_count,
        "X-Pagination-Item-Count": item_count,
    }


def test_process_response_exposes_parsed_pagination_metadata():
    response = MagicMock()
    response.json.return_value = [{"title": "Item"}]
    response.headers = {
        "X-Pagination-Page": "2",
        "X-Pagination-Limit": "20",
        "X-Pagination-Page-Count": "3",
        "X-Pagination-Item-Count": "41",
    }

    result, metadata = TraktBase()._process_response(response, None, pagination=True)

    assert result == [{"title": "Item"}]
    assert metadata == pagination(2, 3, item_count=41)


def test_get_trakt_preserves_non_paginated_caller_result_shape():
    api = TraktBase()
    api.call_trakt = MagicMock(return_value=([{"title": "Item"}], pagination(1, 2)))

    assert api.get_trakt({"path": "movies/trending"}) == [{"title": "Item"}]
    assert api.get_trakt({"path": "movies/trending", "return_pagination": True}) == (
        [{"title": "Item"}],
        pagination(1, 2),
    )


def test_process_trakt_result_adds_next_only_before_final_page():
    with patch.object(TraktClient, "_should_cache_directory", return_value=True), patch(
        "lib.clients.trakt.trakt.execute_thread_pool"
    ), patch("lib.clients.trakt.trakt.add_next_button") as add_next, patch(
        "lib.clients.trakt.trakt.end_of_directory"
    ):
        TraktClient.process_trakt_result(
            ([{"movie": {}}], pagination(1, 2)),
            Trakt.TRENDING,
            None,
            "movies",
            "",
            "trakt",
            1,
        )
        TraktClient.process_trakt_result(
            ([{"movie": {}}], pagination(2, 2)),
            Trakt.TRENDING,
            None,
            "movies",
            "",
            "trakt",
            2,
        )

    add_next.assert_called_once()
    assert add_next.call_args.kwargs["page"] == 1


def test_process_trakt_result_empty_page_does_not_add_next():
    with patch("lib.clients.trakt.trakt.execute_thread_pool"), patch(
        "lib.clients.trakt.trakt.add_next_button"
    ) as add_next, patch("lib.clients.trakt.trakt.end_of_directory"):
        TraktClient.process_trakt_result(
            ([], pagination(3, 3, item_count=40)),
            Trakt.TRENDING,
            None,
            "movies",
            "",
            "trakt",
            3,
        )

    add_next.assert_not_called()


def test_process_trakt_result_empty_non_final_page_does_not_add_next():
    with patch("lib.clients.trakt.trakt.execute_thread_pool"), patch(
        "lib.clients.trakt.trakt.add_next_button"
    ) as add_next, patch("lib.clients.trakt.trakt.end_of_directory"):
        TraktClient.process_trakt_result(
            ([], pagination(1, 3, item_count=40)),
            Trakt.TRENDING,
            None,
            "movies",
            "",
            "trakt",
            1,
        )

    add_next.assert_not_called()


def test_custom_list_uses_api_page_and_preserves_next_route_parameters():
    items = [{"title": "Page two", "type": "movie", "media_ids": {"tmdb": 1}}]
    with patch("lib.clients.trakt.trakt.TraktAPI") as trakt_api, patch(
        "lib.clients.trakt.trakt.execute_thread_pool"
    ) as execute, patch("lib.clients.trakt.trakt.add_next_button") as add_next, patch(
        "lib.clients.trakt.trakt.end_of_directory"
    ):
        get_contents = trakt_api.return_value.lists.get_trakt_list_contents
        get_contents.return_value = (items, pagination(2, 3))

        TraktClient.show_trakt_list_content(
            "liked_lists", "movies", "alice", "favorites", False, 2, 99
        )

    get_contents.assert_called_once_with("liked_lists", "alice", "favorites", False, 99, 2)
    execute.assert_called_once_with(items, TraktPresentation.show_lists_content_items)
    assert add_next.call_args.args == ("list_trakt_page", 2)
    assert add_next.call_args.kwargs == {
        "mode": "movies",
        "list_type": "liked_lists",
        "user": "alice",
        "slug": "favorites",
        "with_auth": False,
        "trakt_id": 99,
    }


def test_custom_list_api_requests_and_returns_the_selected_page():
    api = TraktLists()
    raw_items = [
        {"type": "movie", "movie": {"title": "Page two", "ids": {"tmdb": 1}}}
    ]
    with patch.object(
        api, "get_trakt", return_value=(raw_items, pagination(2, 3))
    ) as get_trakt, patch(
        "lib.api.trakt.trakt.cache_trakt_object",
        side_effect=lambda function, _key, params, _expected_type: function(params),
    ):
        items, metadata = api.get_trakt_list_contents(
            "liked_lists", "alice", "favorites", False, 99, 2
        )

    assert items == [
        {
            "media_ids": {"tmdb": 1},
            "title": "Page two",
            "type": "movie",
            "order": 0,
        }
    ]
    assert metadata == pagination(2, 3)
    assert get_trakt.call_args.args[0]["page_no"] == 2
    assert get_trakt.call_args.args[0]["method"] == "sort_by_headers"
    assert get_trakt.call_args.args[0]["return_pagination"] is True


def test_custom_list_final_and_empty_pages_do_not_add_next_or_raise():
    with patch("lib.clients.trakt.trakt.TraktAPI") as trakt_api, patch(
        "lib.clients.trakt.trakt.execute_thread_pool"
    ), patch("lib.clients.trakt.trakt.add_next_button") as add_next, patch(
        "lib.clients.trakt.trakt.notification"
    ), patch("lib.clients.trakt.trakt.end_of_directory"):
        get_contents = trakt_api.return_value.lists.get_trakt_list_contents
        get_contents.side_effect = [
            ([{"title": "Last", "type": "movie", "media_ids": {}}], pagination(2, 2)),
            ([], pagination(3, 2)),
        ]

        TraktClient.show_trakt_list_content("my_lists", "movies", "me", "favorites", True, 2, 99)
        TraktClient.show_trakt_list_content("my_lists", "movies", "me", "favorites", True, 3, 99)

    add_next.assert_not_called()


def test_legacy_custom_list_next_route_ends_without_index_error():
    with patch("lib.clients.trakt.trakt.notification") as notification, patch(
        "lib.clients.trakt.trakt.end_of_directory"
    ) as end_directory:
        TraktClient.show_list_trakt_page(2, "movies")

    notification.assert_called_once()
    end_directory.assert_called_once_with(cache=False)
