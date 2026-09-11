"""show_season_info must resolve missing external ids from TMDB details.

Callers such as the Nuvio library only know the tmdb_id. Without imdb/tvdb the
episode search carries a bare tmdb_id and sources that match by IMDB (for
example Torrentio) return nothing, which surfaces as "0 results".
"""

from unittest.mock import MagicMock

from lib.utils.views import shows


class _Details:
    """Minimal AsObj-like stand-in for a TMDB tv_details payload."""

    def __init__(self, external_ids):
        self.name = "Reacher"
        self.seasons = []
        self.overview = "overview"
        self.external_ids = external_ids


def _run(monkeypatch, ids, details):
    recorded = {}

    def fake_pool(collection, func, *args, **kwargs):
        recorded["ids"] = args[2]
        return []

    def fake_tmdb_get(action, *args, **kwargs):
        # Only tv_details carries the payload under test; the imdb lookup is
        # irrelevant here.
        return None if action == "find_by_imdb_id" else details

    monkeypatch.setattr(shows, "tmdb_get", fake_tmdb_get)
    monkeypatch.setattr(shows, "execute_thread_pool_collection", fake_pool)
    monkeypatch.setattr(shows, "get_fanart_details", MagicMock(return_value=None))
    monkeypatch.setattr(shows, "add_directory_items_batch", MagicMock())

    shows.show_season_info(ids, "tv", "")
    return recorded["ids"]


def test_show_season_info_resolves_ids_from_tmdb_details(monkeypatch):
    details = _Details({"imdb_id": "tt9288030", "tvdb_id": 366924})

    resolved = _run(monkeypatch, {"tmdb_id": 108978}, details)

    assert resolved == {
        "tmdb_id": 108978,
        "tvdb_id": 366924,
        "imdb_id": "tt9288030",
    }


def test_show_season_info_keeps_provided_ids(monkeypatch):
    details = _Details({"imdb_id": "tt0000000", "tvdb_id": 111111})

    resolved = _run(
        monkeypatch,
        {"tmdb_id": 108978, "tvdb_id": 366924, "imdb_id": "tt9288030"},
        details,
    )

    assert resolved == {
        "tmdb_id": 108978,
        "tvdb_id": 366924,
        "imdb_id": "tt9288030",
    }


def test_show_season_info_tolerates_missing_external_ids(monkeypatch):
    details = _Details(None)

    resolved = _run(monkeypatch, {"tmdb_id": 108978}, details)

    assert resolved == {"tmdb_id": 108978, "tvdb_id": None, "imdb_id": None}
