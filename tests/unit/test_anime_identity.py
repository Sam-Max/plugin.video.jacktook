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
    monkeypatch.setattr(simkl_provider, "anime_detail", lambda simkl_id: None)
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
    # Simkl is now consulted even for an AniList/MAL seed when the first
    # AniList fetch fails; it degrades to None here so the refetch path runs.
    monkeypatch.setattr(simkl_provider, "resolve_ids", lambda provider, value: None)
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


class _FakeCache:
    """Minimal in-memory cache that records every ``set`` call."""

    def __init__(self):
        self.store = {}
        self.set_calls = 0

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, expires=None):
        self.set_calls += 1
        self.store[key] = value


def test_resolve_identity_does_not_cache_degraded_record(monkeypatch):
    calls = []

    def failing_provider(*args, **kwargs):
        calls.append(1)
        return None

    monkeypatch.setattr(anilist_provider, "fetch_by_anilist_id", failing_provider)
    monkeypatch.setattr(anilist_provider, "fetch_by_mal_id", failing_provider)
    monkeypatch.setattr(simkl_provider, "resolve_ids", failing_provider)
    monkeypatch.setattr(simkl_provider, "anime_detail", failing_provider)
    monkeypatch.setattr(anizip_provider, "mappings", lambda anilist_id=None, mal_id=None: None)

    fake_cache = _FakeCache()
    monkeypatch.setattr(identity, "_CACHE", fake_cache)

    first = identity.resolve_identity({"anilist_id": 1})
    second = identity.resolve_identity({"anilist_id": 1})

    assert first is not None
    assert first.title_en is None
    assert first.anilist_id == 1
    # A degraded record must not be cached so the next call retries providers.
    assert fake_cache.set_calls == 0
    assert first is not second
    assert len(calls) >= 2


def test_resolve_identity_caches_substantive_record(monkeypatch):
    calls = []

    def fetch_by_anilist_id(anime_id):
        calls.append(anime_id)
        return {"id": anime_id, "title": {"english": "Show"}}

    monkeypatch.setattr(anilist_provider, "fetch_by_anilist_id", fetch_by_anilist_id)
    monkeypatch.setattr(anilist_provider, "fetch_by_mal_id", lambda mal_id: None)
    monkeypatch.setattr(simkl_provider, "resolve_ids", _fail)
    monkeypatch.setattr(simkl_provider, "anime_detail", _fail)
    monkeypatch.setattr(anizip_provider, "mappings", lambda anilist_id=None, mal_id=None: {})

    fake_cache = _FakeCache()
    monkeypatch.setattr(identity, "_CACHE", fake_cache)

    first = identity.resolve_identity({"anilist_id": 1})
    second = identity.resolve_identity({"anilist_id": 1})

    assert first is second
    assert fake_cache.set_calls == 1
    assert calls == [1]


def test_resolve_identity_uses_simkl_titles_without_anilist(monkeypatch):
    anilist_calls = []
    anizip_calls = []

    def fetch_by_anilist_id(anime_id):
        anilist_calls.append(anime_id)
        return {"id": anime_id, "title": {"english": "AniList Title"}}

    monkeypatch.setattr(anilist_provider, "fetch_by_anilist_id", fetch_by_anilist_id)
    monkeypatch.setattr(anilist_provider, "fetch_by_mal_id", _fail)
    monkeypatch.setattr(
        simkl_provider,
        "resolve_ids",
        lambda provider, value: {
            "simkl": 100,
            "mal": 20,
            "anilist": 30,
            "tmdb": 5,
            "tvdb": 50,
            "imdb": "tt1",
        },
    )
    monkeypatch.setattr(
        simkl_provider,
        "anime_detail",
        lambda simkl_id: {
            "ids": {
                "simkl": 100,
                "mal": 20,
                "anilist": 30,
                "tmdb": 5,
                "tvdb": 50,
                "imdb": "tt1",
            },
            "en_title": "English Simkl",
            "romaji": "Romaji Simkl",
            "title": "Romaji Simkl",
            "overview": "Overview",
            "year": 2013,
            "episodes": 25,
        },
    )

    def mappings(anilist_id=None, mal_id=None):
        anizip_calls.append((anilist_id, mal_id))
        return {}

    monkeypatch.setattr(anizip_provider, "mappings", mappings)

    record = identity.resolve_identity({"tmdb_id": 5})

    assert record.title_en == "English Simkl"
    assert record.title_romaji == "Romaji Simkl"
    assert record.episodes == 25
    assert record.year == 2013
    # Simkl supplied the titles, so AniList and AniZip must not be called.
    assert anilist_calls == []
    assert anizip_calls == []


def test_resolve_identity_falls_back_to_anilist_when_simkl_has_no_title(monkeypatch):
    anilist_calls = []

    def fetch_by_anilist_id(anime_id):
        anilist_calls.append(anime_id)
        return {"id": anime_id, "title": {"english": "AniList Title"}}

    monkeypatch.setattr(anilist_provider, "fetch_by_anilist_id", fetch_by_anilist_id)
    monkeypatch.setattr(anilist_provider, "fetch_by_mal_id", _fail)
    monkeypatch.setattr(
        simkl_provider,
        "resolve_ids",
        lambda provider, value: {"simkl": 100, "anilist": 30},
    )
    monkeypatch.setattr(
        simkl_provider,
        "anime_detail",
        lambda simkl_id: {"ids": {"simkl": 100, "anilist": 30}},
    )
    monkeypatch.setattr(
        anizip_provider,
        "mappings",
        lambda anilist_id=None, mal_id=None: {"anilist_id": 30},
    )

    record = identity.resolve_identity({"tmdb_id": 5})

    assert anilist_calls == [30]
    assert record.anilist_id == 30
    assert record.title_en == "AniList Title"


def test_resolve_identity_returns_partial_record_when_simkl_fails(monkeypatch):
    monkeypatch.setattr(anilist_provider, "fetch_by_anilist_id", lambda anime_id: None)
    monkeypatch.setattr(anilist_provider, "fetch_by_mal_id", lambda mal_id: None)
    monkeypatch.setattr(simkl_provider, "resolve_ids", lambda provider, value: None)
    monkeypatch.setattr(simkl_provider, "anime_detail", _fail)
    monkeypatch.setattr(anizip_provider, "mappings", lambda anilist_id=None, mal_id=None: None)

    record = identity.resolve_identity({"tmdb_id": 5})

    assert record is not None
    assert record.tmdb_id == 5
    assert record.title_en is None


def test_resolve_identity_anilist_fallback_when_simkl_fails(monkeypatch):
    anilist_calls = []

    def fetch_by_mal_id(mal_id):
        anilist_calls.append(mal_id)
        return {"id": 9, "idMal": mal_id, "title": {"english": "AniList Title"}}

    monkeypatch.setattr(anilist_provider, "fetch_by_mal_id", fetch_by_mal_id)
    monkeypatch.setattr(anilist_provider, "fetch_by_anilist_id", _fail)
    monkeypatch.setattr(simkl_provider, "resolve_ids", _fail)
    monkeypatch.setattr(simkl_provider, "anime_detail", _fail)
    monkeypatch.setattr(anizip_provider, "mappings", lambda anilist_id=None, mal_id=None: {})

    record = identity.resolve_identity({"mal_id": 7})

    assert anilist_calls == [7]
    assert record.title_en == "AniList Title"


def test_simkl_anime_detail_maps_title_to_romaji(monkeypatch):
    monkeypatch.setattr(simkl_provider, "_CACHE", _FakeCache())
    monkeypatch.setattr(
        simkl_provider,
        "_request",
        lambda endpoint, params: {
            "title": "Shingeki no Kyojin",
            "en_title": "Attack on Titan",
            "overview": "Desc",
            "year": 2013,
            "total_episodes": 25,
            "ids": {"simkl": 1, "mal": 2, "anilist": 3, "tmdb": 4, "tvdb": 5, "imdb": "tt6"},
        },
    )

    detail = simkl_provider.anime_detail(1)

    assert detail["romaji"] == "Shingeki no Kyojin"
    assert detail["title"] == "Shingeki no Kyojin"
    assert detail["en_title"] == "Attack on Titan"
    assert detail["year"] == 2013
    assert detail["episodes"] == 25
    assert detail["ids"]["simkl"] == 1


def test_simkl_anime_detail_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr(simkl_provider, "_CACHE", _FakeCache())
    monkeypatch.setattr(simkl_provider, "_request", lambda endpoint, params: None)

    assert simkl_provider.anime_detail(1) is None


def test_simkl_resolve_ids_adds_type_for_tmdb(monkeypatch):
    seen = []
    monkeypatch.setattr(simkl_provider, "_CACHE", _FakeCache())

    def _request(endpoint, params):
        seen.append(dict(params))
        return {"ids": {"simkl": 1}}

    monkeypatch.setattr(simkl_provider, "_request", _request)

    simkl_provider.resolve_ids("tmdb", 85937, media_type="tv")

    assert seen[0]["tmdb"] == 85937
    assert seen[0]["type"] == "tv"


def test_simkl_resolve_ids_omits_type_without_media_type(monkeypatch):
    seen = []
    monkeypatch.setattr(simkl_provider, "_CACHE", _FakeCache())

    def _request(endpoint, params):
        seen.append(dict(params))
        return {"ids": {"simkl": 1}}

    monkeypatch.setattr(simkl_provider, "_request", _request)

    simkl_provider.resolve_ids("tmdb", 85937)

    assert "type" not in seen[0]


def test_simkl_resolve_ids_only_types_tmdb(monkeypatch):
    seen = []
    monkeypatch.setattr(simkl_provider, "_CACHE", _FakeCache())

    def _request(endpoint, params):
        seen.append(dict(params))
        return {"ids": {"simkl": 1}}

    monkeypatch.setattr(simkl_provider, "_request", _request)

    simkl_provider.resolve_ids("tvdb", 41135, media_type="tv")

    assert "type" not in seen[0]


def test_simkl_resolve_ids_cache_separates_tv_and_movie(monkeypatch):
    calls = []
    monkeypatch.setattr(simkl_provider, "_CACHE", _FakeCache())

    def _request(endpoint, params):
        calls.append(dict(params))
        return {"ids": {"simkl": 1 if params.get("type") == "tv" else 2}}

    monkeypatch.setattr(simkl_provider, "_request", _request)

    tv = simkl_provider.resolve_ids("tmdb", 85937, media_type="tv")
    movie = simkl_provider.resolve_ids("tmdb", 85937, media_type="movie")
    tv_again = simkl_provider.resolve_ids("tmdb", 85937, media_type="tv")

    assert tv["simkl"] == 1
    assert movie["simkl"] == 2
    assert tv_again is tv
    assert len(calls) == 2


def test_simkl_normalize_detail_returns_none_for_empty_payload():
    assert simkl_provider._normalize_detail({}) is None
    # Keys with no usable values are just as empty as a missing ids block.
    assert simkl_provider._normalize_detail({"ids": {"simkl": None}}) is None
    # A title-only payload is still valid even without ids.
    assert simkl_provider._normalize_detail({"title": "Show"})["title"] == "Show"


def test_simkl_anime_detail_does_not_cache_empty_payload(monkeypatch):
    fake_cache = _FakeCache()
    monkeypatch.setattr(simkl_provider, "_CACHE", fake_cache)
    monkeypatch.setattr(simkl_provider, "_request", lambda endpoint, params: {})

    assert simkl_provider.anime_detail(7) is None
    assert fake_cache.set_calls == 0


def test_resolve_identity_forwards_media_type_hint_for_tmdb(monkeypatch):
    seen = {}

    def resolve_ids(provider, value, media_type=None):
        seen["provider"] = provider
        seen["media_type"] = media_type
        return {
            "simkl": 100,
            "anilist": 30,
            "mal": 20,
            "tmdb": 85937,
            "tvdb": 41135,
            "imdb": "tt1",
        }

    monkeypatch.setattr(simkl_provider, "resolve_ids", resolve_ids)
    monkeypatch.setattr(
        simkl_provider,
        "anime_detail",
        lambda simkl_id: {
            "ids": {
                "simkl": 100,
                "anilist": 30,
                "mal": 20,
                "tmdb": 85937,
                "tvdb": 41135,
                "imdb": "tt1",
            },
            "en_title": "Demon Slayer: Kimetsu no Yaiba",
            "romaji": "Kimetsu no Yaiba",
            "title": "Kimetsu no Yaiba",
        },
    )
    monkeypatch.setattr(anilist_provider, "fetch_by_anilist_id", _fail)
    monkeypatch.setattr(anilist_provider, "fetch_by_mal_id", _fail)
    monkeypatch.setattr(anizip_provider, "mappings", _fail)

    record = identity.resolve_identity({"tmdb_id": 85937, "media_type": "tv"})

    assert seen == {"provider": "tmdb", "media_type": "tv"}
    assert record.title_en == "Demon Slayer: Kimetsu no Yaiba"
    assert record.title_romaji == "Kimetsu no Yaiba"
    assert record.tvdb_id == 41135


def test_resolve_identity_accepts_type_alias_hint(monkeypatch):
    seen = {}

    def resolve_ids(provider, value, media_type=None):
        seen["media_type"] = media_type
        return {
            "simkl": 100,
            "anilist": 30,
            "mal": 20,
            "tmdb": 85937,
            "tvdb": 41135,
            "imdb": "tt1",
        }

    monkeypatch.setattr(simkl_provider, "resolve_ids", resolve_ids)
    monkeypatch.setattr(
        simkl_provider,
        "anime_detail",
        lambda simkl_id: {
            "ids": {
                "simkl": 100,
                "anilist": 30,
                "mal": 20,
                "tmdb": 85937,
                "tvdb": 41135,
                "imdb": "tt1",
            },
            "en_title": "Movie Title",
            "romaji": "Movie Title",
            "title": "Movie Title",
        },
    )
    monkeypatch.setattr(anilist_provider, "fetch_by_anilist_id", _fail)
    monkeypatch.setattr(anilist_provider, "fetch_by_mal_id", _fail)
    monkeypatch.setattr(anizip_provider, "mappings", _fail)

    record = identity.resolve_identity({"tmdb_id": 85937, "type": "movie"})

    assert seen["media_type"] == "movie"
    assert record.title_en == "Movie Title"


def test_resolve_identity_prefers_tvdb_over_tmdb_without_hint(monkeypatch):
    calls = []

    def resolve_ids(provider, value, media_type=None):
        calls.append((provider, value, media_type))
        return {
            "simkl": 100,
            "anilist": 30,
            "mal": 20,
            "tmdb": 999,
            "tvdb": 41135,
            "imdb": "tt1",
        }

    monkeypatch.setattr(simkl_provider, "resolve_ids", resolve_ids)
    monkeypatch.setattr(
        simkl_provider,
        "anime_detail",
        lambda simkl_id: {
            "ids": {
                "simkl": 100,
                "anilist": 30,
                "mal": 20,
                "tmdb": 999,
                "tvdb": 41135,
                "imdb": "tt1",
            },
            "en_title": "Correct Anime",
            "romaji": "Correct Anime",
            "title": "Correct Anime",
        },
    )
    monkeypatch.setattr(anilist_provider, "fetch_by_anilist_id", _fail)
    monkeypatch.setattr(anilist_provider, "fetch_by_mal_id", _fail)
    monkeypatch.setattr(anizip_provider, "mappings", _fail)

    record = identity.resolve_identity({"tmdb_id": 85937, "tvdb_id": 41135})

    assert calls == [("tvdb", 41135, None)]
    assert record.title_en == "Correct Anime"


def test_resolve_identity_prefers_imdb_over_tmdb_without_hint(monkeypatch):
    calls = []

    def resolve_ids(provider, value, media_type=None):
        calls.append((provider, value, media_type))
        return {
            "simkl": 100,
            "anilist": 30,
            "mal": 20,
            "tmdb": 999,
            "tvdb": 41135,
            "imdb": "tt123",
        }

    monkeypatch.setattr(simkl_provider, "resolve_ids", resolve_ids)
    monkeypatch.setattr(
        simkl_provider,
        "anime_detail",
        lambda simkl_id: {
            "ids": {
                "simkl": 100,
                "anilist": 30,
                "mal": 20,
                "tmdb": 999,
                "tvdb": 41135,
                "imdb": "tt123",
            },
            "en_title": "Correct Anime",
            "romaji": "Correct Anime",
            "title": "Correct Anime",
        },
    )
    monkeypatch.setattr(anilist_provider, "fetch_by_anilist_id", _fail)
    monkeypatch.setattr(anilist_provider, "fetch_by_mal_id", _fail)
    monkeypatch.setattr(anizip_provider, "mappings", _fail)

    record = identity.resolve_identity({"tmdb_id": 85937, "imdb_id": "tt123"})

    assert calls == [("imdb", "tt123", None)]
    assert record.title_en == "Correct Anime"


def test_resolve_identity_uses_simkl_title_when_anilist_seed_fails(monkeypatch):
    simkl_providers = []

    monkeypatch.setattr(anilist_provider, "fetch_by_anilist_id", lambda anime_id: None)
    monkeypatch.setattr(anilist_provider, "fetch_by_mal_id", _fail)

    def resolve_ids(provider, value, media_type=None):
        simkl_providers.append(provider)
        return {
            "simkl": 100,
            "anilist": 30,
            "mal": 20,
            "tmdb": 85937,
            "tvdb": 41135,
            "imdb": "tt1",
        }

    monkeypatch.setattr(simkl_provider, "resolve_ids", resolve_ids)
    monkeypatch.setattr(
        simkl_provider,
        "anime_detail",
        lambda simkl_id: {
            "ids": {
                "simkl": 100,
                "anilist": 30,
                "mal": 20,
                "tmdb": 85937,
                "tvdb": 41135,
                "imdb": "tt1",
            },
            "en_title": "Simkl English",
            "romaji": "Simkl Romaji",
            "title": "Simkl Romaji",
        },
    )
    monkeypatch.setattr(anizip_provider, "mappings", _fail)

    record = identity.resolve_identity({"anilist_id": 1})

    assert simkl_providers == ["anilist"]
    assert record.title_en == "Simkl English"
    assert record.anilist_id == 30


def test_resolve_identity_cache_separates_tv_and_movie_hints(monkeypatch):
    def resolve_ids(provider, value, media_type=None):
        return {
            "simkl": 100 if media_type == "tv" else 200,
            "anilist": 30,
            "mal": 20,
            "tmdb": 1,
            "tvdb": 41135,
            "imdb": "tt1",
        }

    def anime_detail(simkl_id):
        title = "TV Title" if simkl_id == 100 else "Movie Title"
        return {
            "ids": {
                "simkl": simkl_id,
                "anilist": 30,
                "mal": 20,
                "tmdb": 1,
                "tvdb": 41135,
                "imdb": "tt1",
            },
            "en_title": title,
            "romaji": title,
            "title": title,
        }

    monkeypatch.setattr(simkl_provider, "resolve_ids", resolve_ids)
    monkeypatch.setattr(simkl_provider, "anime_detail", anime_detail)
    monkeypatch.setattr(anilist_provider, "fetch_by_anilist_id", _fail)
    monkeypatch.setattr(anilist_provider, "fetch_by_mal_id", _fail)
    monkeypatch.setattr(anizip_provider, "mappings", _fail)

    fake_cache = _FakeCache()
    monkeypatch.setattr(identity, "_CACHE", fake_cache)

    tv = identity.resolve_identity({"tmdb_id": 1, "media_type": "tv"})
    movie = identity.resolve_identity({"tmdb_id": 1, "media_type": "movie"})

    assert tv.title_en == "TV Title"
    assert movie.title_en == "Movie Title"
    assert tv is not movie
    assert fake_cache.set_calls == 2

