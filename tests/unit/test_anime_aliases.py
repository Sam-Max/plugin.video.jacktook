"""Offline tests for anime title aliases and their use as search fallbacks."""

from types import SimpleNamespace

import pytest

from lib.anime.stream_target import resolve_title_aliases
from lib.search import SearchVariant, _build_title_fallback_queries


def _record(**titles):
    fields = {"title_en": None, "title_romaji": None, "title_native": None}
    fields.update(titles)
    return SimpleNamespace(**fields)


# --- resolve_title_aliases ----------------------------------------------------


def test_collects_distinct_identity_titles(monkeypatch):
    monkeypatch.setattr(
        "lib.anime.stream_target.resolve_identity",
        lambda seed: _record(
            title_en="Mushoku Tensei: Jobless Reincarnation",
            title_romaji="Mushoku Tensei III",
            title_native="無職転生 III",
        ),
    )

    aliases = resolve_title_aliases({"tmdb_id": 111110})

    assert aliases == [
        "Mushoku Tensei: Jobless Reincarnation",
        "Mushoku Tensei III",
        "無職転生 III",
    ]


def test_duplicate_titles_are_deduplicated_case_insensitively(monkeypatch):
    monkeypatch.setattr(
        "lib.anime.stream_target.resolve_identity",
        lambda seed: _record(
            title_en="Mushoku Tensei III",
            title_romaji="mushoku tensei iii",
            title_native="無職転生 III",
        ),
    )

    assert resolve_title_aliases({"tmdb_id": 111110}) == ["Mushoku Tensei III", "無職転生 III"]


def test_unusable_ids_degrade_to_empty(monkeypatch):
    called = []
    monkeypatch.setattr(
        "lib.anime.stream_target.resolve_identity", lambda seed: called.append(seed) or None
    )

    assert resolve_title_aliases({}) == []
    assert called == []


def test_no_record_degrades_to_empty(monkeypatch):
    monkeypatch.setattr("lib.anime.stream_target.resolve_identity", lambda seed: None)

    assert resolve_title_aliases({"tmdb_id": 111110}) == []


def test_provider_failure_degrades_to_empty(monkeypatch):
    def boom(seed):
        raise RuntimeError("network down")

    monkeypatch.setattr("lib.anime.stream_target.resolve_identity", boom)

    assert resolve_title_aliases({"tmdb_id": 111110}) == []


# --- fallback query builder -----------------------------------------------------


@pytest.fixture
def no_tmdb_titles(monkeypatch):
    """TMDB details resolve to an empty-title payload (translations missing)."""
    monkeypatch.setattr(
        "lib.clients.tmdb.utils.utils.get_tmdb_media_details",
        lambda tmdb_id, mode: SimpleNamespace(original_title="", translations=None),
    )


def test_without_anime_target_no_aliases_are_added(monkeypatch, no_tmdb_titles):
    added = []
    monkeypatch.setattr(
        "lib.anime.stream_target.resolve_title_aliases",
        lambda ids: added.append(ids) or ["Romaji Title"],
    )

    queries = _build_title_fallback_queries(
        "Mushoku Tensei",
        {"tmdb_id": 111110},
        "tv",
    )

    assert added == []
    assert "Romaji Title" not in queries


def test_anime_target_appends_identity_titles_after_tmdb_candidates(monkeypatch):
    monkeypatch.setattr(
        "lib.clients.tmdb.utils.utils.get_tmdb_media_details",
        lambda tmdb_id, mode: SimpleNamespace(
            original_title="Mushoku Tensei III",
            translations=None,
        ),
    )
    monkeypatch.setattr(
        "lib.anime.stream_target.resolve_title_aliases",
        lambda ids: ["Jobless Reincarnation S3", "無職転生 III"],
    )

    queries = _build_title_fallback_queries(
        "Mushoku Tensei",
        {"tmdb_id": 111110},
        "tv",
        anime_target=object(),
    )

    assert queries[0] == "Mushoku Tensei"
    assert queries[-2:] == ["Jobless Reincarnation S3", "無職転生 III"]
    # The TMDB original title and the romaji alias are the same string: deduped.
    assert queries.count("Mushoku Tensei III") == 1


def test_anime_aliases_survive_a_tmdb_failure(monkeypatch):
    def boom(tmdb_id, mode):
        raise RuntimeError("tmdb down")

    monkeypatch.setattr("lib.clients.tmdb.utils.utils.get_tmdb_media_details", boom)
    monkeypatch.setattr(
        "lib.anime.stream_target.resolve_title_aliases",
        lambda ids: ["Jobless Reincarnation S3"],
    )

    queries = _build_title_fallback_queries(
        "Mushoku Tensei",
        {"tmdb_id": 111110},
        "tv",
        anime_target=object(),
    )

    assert "Jobless Reincarnation S3" in queries


def test_variant_original_title_still_appends_aliases(monkeypatch, no_tmdb_titles):
    monkeypatch.setattr(
        "lib.anime.stream_target.resolve_title_aliases",
        lambda ids: ["Romaji Title"],
    )

    queries = _build_title_fallback_queries(
        "Mushoku Tensei",
        {"tmdb_id": 111110},
        "tv",
        SearchVariant.ORIGINAL_TITLE,
        anime_target=object(),
    )

    assert "Romaji Title" in queries
