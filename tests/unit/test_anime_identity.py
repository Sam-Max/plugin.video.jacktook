from lib.anime import identity
from lib.anime.providers import anilist as anilist_provider
from lib.anime.providers import anizip as anizip_provider
from lib.anime.providers import simkl as simkl_provider


def _fail(*args, **kwargs):
    raise AssertionError("unexpected provider call")


def test_resolve_identity_prefers_anilist_id(monkeypatch):
    monkeypatch.setattr(
        anilist_provider,
        "fetch_by_anilist_id",
        lambda anime_id: {"id": anime_id, "idMal": 2, "title": {"english": "Show"}},
    )
    monkeypatch.setattr(anilist_provider, "fetch_by_mal_id", _fail)
    monkeypatch.setattr(simkl_provider, "resolve_ids", _fail)
    monkeypatch.setattr(simkl_provider, "anime_detail", _fail)
    monkeypatch.setattr(anizip_provider, "mappings", lambda anilist_id=None, mal_id=None: {})

    record = identity.resolve_identity({"anilist_id": 1})

    assert record is not None
    assert record.anilist_id == 1
    assert record.title_en == "Show"


def test_resolve_identity_uses_mal_when_anilist_id_missing(monkeypatch):
    calls = []

    def fetch_by_mal_id(mal_id):
        calls.append(mal_id)
        return {"id": 10, "idMal": mal_id, "title": {"romaji": "Romaji"}}

    monkeypatch.setattr(anilist_provider, "fetch_by_mal_id", fetch_by_mal_id)
    monkeypatch.setattr(anilist_provider, "fetch_by_anilist_id", lambda anime_id: {"id": anime_id})
    monkeypatch.setattr(simkl_provider, "resolve_ids", _fail)
    monkeypatch.setattr(simkl_provider, "anime_detail", _fail)
    monkeypatch.setattr(anizip_provider, "mappings", lambda anilist_id=None, mal_id=None: {})

    record = identity.resolve_identity({"mal_id": 7})

    assert calls == [7]
    assert record.mal_id == 7


def test_resolve_identity_falls_back_to_simkl_and_anizip(monkeypatch):
    monkeypatch.setattr(
        simkl_provider,
        "resolve_ids",
        lambda provider, value: {"simkl": 10, "mal": 20, "anilist": 30},
    )
    monkeypatch.setattr(
        anizip_provider,
        "mappings",
        lambda anilist_id=None, mal_id=None: {
            "tvdb_id": 40,
            "tmdb_id": 50,
            "imdb_id": "tt5",
        },
    )
    monkeypatch.setattr(
        anilist_provider,
        "fetch_by_anilist_id",
        lambda anime_id: {"id": anime_id, "idMal": 20, "title": {"english": "Show"}},
    )
    monkeypatch.setattr(anilist_provider, "fetch_by_mal_id", lambda mal_id: None)

    record = identity.resolve_identity({"tvdb_id": 40})

    assert record.anilist_id == 30
    assert record.mal_id == 20
    assert record.tmdb_id == 50
    assert record.tvdb_id == 40
    assert record.imdb_id == "tt5"


def test_resolve_identity_refetches_anilist_after_anizip(monkeypatch):
    fetched = []

    def fetch_by_anilist_id(anime_id):
        fetched.append(anime_id)
        return {"id": anime_id, "title": {"english": "Resolved"}}

    monkeypatch.setattr(anilist_provider, "fetch_by_mal_id", lambda mal_id: None)
    monkeypatch.setattr(anilist_provider, "fetch_by_anilist_id", fetch_by_anilist_id)
    monkeypatch.setattr(simkl_provider, "resolve_ids", _fail)
    monkeypatch.setattr(simkl_provider, "anime_detail", _fail)
    monkeypatch.setattr(
        anizip_provider,
        "mappings",
        lambda anilist_id=None, mal_id=None: {"anilist_id": 42},
    )

    record = identity.resolve_identity({"mal_id": 7})

    assert fetched == [42]
    assert record.anilist_id == 42
    assert record.title_en == "Resolved"


def test_resolve_identity_uses_simkl_detail_for_simkl_id(monkeypatch):
    monkeypatch.setattr(
        anilist_provider,
        "fetch_by_anilist_id",
        lambda anime_id: {"id": anime_id, "title": {"english": "Show"}},
    )
    monkeypatch.setattr(anilist_provider, "fetch_by_mal_id", lambda mal_id: None)
    monkeypatch.setattr(
        simkl_provider,
        "anime_detail",
        lambda simkl_id: {"mal": 5, "anilist": 6},
    )
    monkeypatch.setattr(simkl_provider, "resolve_ids", _fail)
    monkeypatch.setattr(anizip_provider, "mappings", lambda anilist_id=None, mal_id=None: {})

    record = identity.resolve_identity({"simkl_id": 99})

    assert record.simkl_id == 99
    assert record.anilist_id == 6


def test_resolve_identity_returns_partial_record_when_providers_fail(monkeypatch):
    monkeypatch.setattr(anilist_provider, "fetch_by_anilist_id", lambda anime_id: None)
    monkeypatch.setattr(anilist_provider, "fetch_by_mal_id", lambda mal_id: None)
    monkeypatch.setattr(simkl_provider, "resolve_ids", lambda provider, value: None)
    monkeypatch.setattr(simkl_provider, "anime_detail", lambda simkl_id: None)
    monkeypatch.setattr(anizip_provider, "mappings", lambda anilist_id=None, mal_id=None: None)

    record = identity.resolve_identity({"anilist_id": 1})

    assert record is not None
    assert record.anilist_id == 1
    assert record.title_en is None


def test_resolve_identity_returns_none_for_empty_ids():
    assert identity.resolve_identity(None) is None
    assert identity.resolve_identity({}) is None
