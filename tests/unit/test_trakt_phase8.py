from unittest.mock import MagicMock, patch

from lib.api.trakt.trakt import TraktLists
from lib.api.trakt.trakt_utils import (
    add_trakt_favorites_context_menu,
    add_trakt_watchlist_context_menu,
)
from lib.clients.trakt.trakt import TraktPresentation


def test_add_to_favorites_posts_expected_payload():
    trakt_lists = TraktLists()

    with patch.object(trakt_lists, "call_trakt", return_value={}) as call_trakt, patch(
        "lib.api.trakt.trakt.clear_trakt_favorites"
    ) as clear_favorites:
        trakt_lists.add_to_favorites("movies", {"tmdb": 11, "imdb": "tt11"})

    call_trakt.assert_called_once_with(
        "sync/favorites",
        data={"movies": [{"ids": {"tmdb": 11, "imdb": "tt11"}}]},
        with_auth=True,
        pagination=False,
    )
    clear_favorites.assert_called_once_with()


def test_remove_from_favorites_posts_expected_payload():
    trakt_lists = TraktLists()

    with patch.object(trakt_lists, "call_trakt", return_value={}) as call_trakt, patch(
        "lib.api.trakt.trakt.clear_trakt_favorites"
    ):
        trakt_lists.remove_from_favorites("shows", {"tmdb": 22, "tvdb": 33})

    call_trakt.assert_called_once_with(
        "sync/favorites/remove",
        data={"shows": [{"ids": {"tmdb": 22, "tvdb": 33}}]},
        with_auth=True,
        pagination=False,
    )


def test_watchlist_context_menu_can_hide_add_action():
    menu = add_trakt_watchlist_context_menu(
        "movies", {"tmdb_id": 1}, include_add=False, include_remove=True
    )

    labels = [label for label, _cmd in menu]
    assert labels == ["Remove from Trakt Watchlist"]


def test_favorites_context_menu_can_hide_remove_action():
    menu = add_trakt_favorites_context_menu(
        "shows", {"tmdb_id": 1}, include_add=True, include_remove=False
    )

    labels = [label for label, _cmd in menu]
    assert labels == ["Add to Trakt Favorites"]


def test_show_favorites_uses_state_aware_context_flags():
    fake_item = MagicMock()

    with patch("lib.clients.trakt.trakt.ListItem", return_value=fake_item), patch(
        "lib.clients.trakt.trakt.tmdb_get", return_value={}
    ), patch("lib.clients.trakt.trakt.set_media_infoTag"), patch(
        "lib.clients.trakt.trakt.BaseTraktClient._add_media_directory_item"
    ) as add_item:
        TraktPresentation.show_favorites(
            {"title": "Demo", "media_ids": {"tmdb": 1, "imdb": "tt1"}},
            "movies",
        )

    from lib.clients.trakt.trakt import BaseTraktClient

    assert add_item.call_args.kwargs["context_flags"] == BaseTraktClient._exclusive_context_flags(
        "favorites"
    )


def test_exclusive_context_flags_only_enable_requested_remove_action():
    from lib.clients.trakt.trakt import BaseTraktClient

    flags = BaseTraktClient._exclusive_context_flags("watchlist")

    assert flags["watchlist_remove"] is True
    assert flags["watchlist_add"] is False
    assert flags["favorites_remove"] is False
    assert flags["collection_remove"] is False
    assert flags["custom_list_remove"] is False


def test_add_to_collection_clears_collection_caches_for_movies():
    trakt_lists = TraktLists()

    with patch.object(trakt_lists, "call_trakt", return_value={}) as call_trakt, patch(
        "lib.api.trakt.trakt.lists_cache.delete_prefix"
    ) as delete_prefix, patch(
        "lib.api.trakt.trakt.clear_trakt_collection_watchlist_data"
    ) as clear_collection:
        trakt_lists.add_to_collection("movies", {"tmdb": 44})

    call_trakt.assert_called_once()
    delete_prefix.assert_called_once_with("trakt_movies_collection_")
    clear_collection.assert_called_once_with("collection", "movies")


def test_remove_from_collection_uses_all_known_ids_for_shows():
    trakt_lists = TraktLists()

    with patch.object(trakt_lists, "call_trakt", return_value={}) as call_trakt, patch(
        "lib.api.trakt.trakt.lists_cache.delete_prefix"
    ), patch("lib.api.trakt.trakt.clear_trakt_collection_watchlist_data"):
        trakt_lists.remove_from_collection(
            "shows", {"tmdb": "44", "tvdb": "55", "imdb": "tt66"}
        )

    call_trakt.assert_called_once_with(
        "sync/collection/remove",
        data={"shows": [{"ids": {"tmdb": 44, "tvdb": 55, "imdb": "tt66"}}]},
        with_auth=True,
        pagination=False,
    )


def test_build_show_collection_payload_uses_show_level_ids():
    with patch(
        "lib.clients.trakt.trakt.TraktPresentation._resolve_media_ids",
        return_value={"tmdb_id": "99", "tvdb_id": "77", "imdb_id": "tt99"},
    ), patch("lib.clients.trakt.trakt.TraktAPI") as trakt_api, patch(
        "lib.clients.trakt.trakt.tmdb_get",
        return_value={"name": "Demo Show", "first_air_date": "2024-01-01"},
    ):
        trakt_api.return_value.lists.get_trakt_object_by_tmdb.return_value = {
            "title": "Demo Show",
            "year": 2024,
            "ids": {"trakt": 123, "slug": "demo-show"},
        }
        from lib.clients.trakt.trakt import TraktClient

        payload = TraktClient._build_show_collection_payload({"tmdb_id": "99"})

    assert payload == {
        "shows": [
            {
                "title": "Demo Show",
                "year": 2024,
                "ids": {
                    "tmdb": 99,
                    "tvdb": 77,
                    "imdb": "tt99",
                    "trakt": 123,
                    "slug": "demo-show",
                },
            }
        ]
    }


def test_build_show_collection_episode_payload_includes_aired_episodes_only():
    tv_details = {"number_of_seasons": 1}
    season_details = {
        "episodes": [
            {"episode_number": 1, "air_date": "2024-01-01"},
            {"episode_number": 2, "air_date": "2999-01-01"},
        ]
    }

    with patch("lib.clients.trakt.trakt.tmdb_get", side_effect=[tv_details, season_details]), patch(
        "lib.clients.trakt.trakt.TraktPresentation._resolve_media_ids",
        return_value={"tmdb_id": "99", "tvdb_id": "77", "imdb_id": "tt99"},
    ), patch("lib.clients.trakt.trakt.TraktAPI") as trakt_api:
        trakt_api.return_value.lists.get_trakt_object_by_tmdb.return_value = {
            "title": "Demo Show",
            "year": 2024,
            "ids": {"trakt": 123, "slug": "demo-show"},
        }
        from lib.clients.trakt.trakt import TraktClient

        payload = TraktClient._build_show_collection_episode_payload({"tmdb_id": "99"})

    assert payload == {
        "shows": [
            {
                "title": "Demo Show",
                "year": 2024,
                "ids": {
                    "tmdb": 99,
                    "tvdb": 77,
                    "imdb": "tt99",
                    "trakt": 123,
                    "slug": "demo-show",
                },
                "seasons": [{"number": 1, "episodes": [{"number": 1}]}],
            }
        ]
    }


def test_build_show_collection_season_payload_uses_season_numbers_only():
    episode_payload = {
        "shows": [
            {
                "ids": {"tmdb": 99, "tvdb": 77},
                "title": "Demo Show",
                "year": 2024,
                "seasons": [
                    {"number": 1, "episodes": [{"number": 1}]},
                    {"number": 2, "episodes": [{"number": 1}]},
                ],
            }
        ]
    }

    with patch(
        "lib.clients.trakt.trakt.TraktClient._build_show_collection_episode_payload",
        return_value=episode_payload,
    ):
        from lib.clients.trakt.trakt import TraktClient

        payload = TraktClient._build_show_collection_season_payload({"tmdb_id": "99"})

    assert payload == {
        "shows": [
            {
                "ids": {"tmdb": 99, "tvdb": 77},
                "title": "Demo Show",
                "year": 2024,
                "seasons": [{"number": 1}, {"number": 2}],
            }
        ]
    }


def test_normalize_trakt_media_type_prefers_show_when_tvdb_present():
    from lib.clients.trakt.trakt import TraktClient

    result = TraktClient._normalize_trakt_media_type(
        "movies", {"tmdb": 44, "tvdb": 55}
    )

    assert result == "shows"


def test_normalize_trakt_media_type_uses_tmdb_details_for_tv_ids():
    with patch("lib.clients.trakt.trakt.tmdb_get", side_effect=[{"name": "TV Show"}, None]):
        from lib.clients.trakt.trakt import TraktClient

        result = TraktClient._normalize_trakt_media_type("movies", {"tmdb": 999})

    assert result == "shows"


def test_build_collection_remove_payload_uses_existing_collection_entry():
    trakt_lists = TraktLists()

    with patch.object(
        trakt_lists,
        "get_collection_items",
        return_value=[
            {
                "show": {
                    "title": "Demo Show",
                    "year": 2024,
                    "ids": {"tmdb": 99, "tvdb": 77, "imdb": "tt99", "trakt": 123},
                },
                "seasons": [{"number": 1, "episodes": [{"number": 1}, {"number": 2}]}],
            }
        ],
    ):
        payload = trakt_lists.build_collection_remove_payload(
            "shows", {"tmdb": 99, "tvdb": 77}
        )

    assert payload == {
        "shows": [
            {
                "title": "Demo Show",
                "year": 2024,
                "ids": {"tmdb": 99, "tvdb": 77, "imdb": "tt99", "trakt": 123},
                "seasons": [{"number": 1, "episodes": [{"number": 1}, {"number": 2}]}],
            }
        ]
    }


def test_result_has_collection_change_for_show_add_when_episodes_added():
    from lib.clients.trakt.trakt import TraktClient

    result = TraktClient._result_has_collection_change(
        {"added": {"movies": 0, "episodes": 3}}, "add"
    )

    assert result is True
