from unittest.mock import MagicMock, patch

from lib.utils.views import library
from lib.utils.general.utils import add_to_library, remove_from_library


def test_get_library_entries_uses_cached_materialized_list():
    items = [("Movie", {"ids": {"tmdb_id": 1}})]
    cached_entries = [("Movie", {"ids": {"tmdb_id": 1}}, {"id": 1, "title": "Movie"})]

    with patch("lib.utils.views.library.cache.get", return_value=cached_entries) as mock_get, patch(
        "lib.utils.views.library.tmdb_get"
    ) as mock_tmdb_get:
        entries = library._get_library_entries(items, "movies")

    mock_get.assert_called_once_with("library_view|movies")
    mock_tmdb_get.assert_not_called()
    assert entries == cached_entries


def test_get_library_entries_materializes_and_caches_missing_entries():
    items = [
        ("Movie", {"ids": {"tmdb_id": 1}}),
        ("Missing", {"ids": {"tmdb_id": 2}}),
    ]

    with patch("lib.utils.views.library.cache.get", return_value=None), patch(
        "lib.utils.views.library.cache.set"
    ) as mock_set, patch(
        "lib.utils.views.library.tmdb_get",
        side_effect=[{"id": 1, "title": "Movie"}, None],
    ) as mock_tmdb_get:
        entries = library._get_library_entries(items, "movies")

    assert entries == [
        {
            "title": "Movie",
            "data": {"ids": {"tmdb_id": 1}},
            "details": {"id": 1, "title": "Movie"},
            "is_stremio": False,
        }
    ]
    assert mock_tmdb_get.call_count == 2
    mock_set.assert_called_once_with("library_view|movies", entries)


def test_library_mutations_invalidate_materialized_cache():
    with patch("lib.utils.general.utils.pickle_db.set_item"), patch(
        "lib.utils.general.utils.cache.delete"
    ) as mock_delete:
        add_to_library({"title": "Movie", "ids": {"tmdb_id": 1}, "mode": "movies"})

    assert mock_delete.call_args_list[0].args[0] == "library_view|tv"
    assert mock_delete.call_args_list[1].args[0] == "library_view|movies"

    with patch("lib.utils.general.utils.pickle_db.delete_item"), patch(
        "lib.utils.general.utils.cache.delete"
    ) as mock_delete:
        remove_from_library("Movie")

    assert mock_delete.call_args_list[0].args[0] == "library_view|tv"
    assert mock_delete.call_args_list[1].args[0] == "library_view|movies"
