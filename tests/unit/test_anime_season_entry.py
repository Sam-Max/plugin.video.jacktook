from lib.anime import season_entry
from lib.anime.providers import simkl as simkl_provider

# Live-verified Simkl shapes for a multi-cour show (Mushoku Tensei): the base
# entry covers season 1 only, and season 3 lives in the sequel entry 2832226
# (ids anilist 178789 / mal 59193 / kitsu 49002). Values are the real ones the
# API returned so the tests pin the actual wire shapes.


def _entry(
    simkl_id,
    mapped_seasons,
    anilist_id=None,
    mal_id=None,
    kitsu_id=None,
    relations=None,
    total_episodes=None,
):
    """Build a normalized entry in the shape ``fetch_entry`` returns."""
    return {
        "simkl_id": simkl_id,
        "anilist_id": anilist_id,
        "mal_id": mal_id,
        "kitsu_id": kitsu_id,
        "mapped_seasons": mapped_seasons,
        "relations": relations or [],
        "total_episodes": total_episodes,
    }


BASE = _entry(
    1059371,
    [1],
    anilist_id=108465,
    mal_id=39535,
    kitsu_id=42323,
    relations=[
        {"simkl_id": 1524389, "relation_type": "sequel", "year": 2021, "title": "Part 2"},
        {"simkl_id": 1863030, "relation_type": "sequel", "year": 2023, "title": "Season 2"},
        {
            "simkl_id": 2204668,
            "relation_type": "sequel",
            "year": 2024,
            "title": "Season 2 Part 2",
        },
        {"simkl_id": 2832226, "relation_type": "sequel", "year": 2026, "title": "Season 3"},
    ],
    total_episodes=11,
)
PART2 = _entry(1524389, [1], total_episodes=11)
SEASON2 = _entry(1863030, [2], total_episodes=12)
SEASON2_PART2 = _entry(2204668, [2], total_episodes=12)
SEASON3 = _entry(
    2832226,
    [3],
    anilist_id=178789,
    mal_id=59193,
    kitsu_id=49002,
    total_episodes=14,
)
ENTRIES = {entry["simkl_id"]: entry for entry in (BASE, PART2, SEASON2, SEASON2_PART2, SEASON3)}

SEASON3_IDS = {
    "simkl_id": 2832226,
    "anilist_id": 178789,
    "mal_id": 59193,
    "kitsu_id": 49002,
}
BASE_IDS = {
    "simkl_id": 1059371,
    "anilist_id": 108465,
    "mal_id": 39535,
    "kitsu_id": 42323,
}


class _FetchSpy:
    """Stands in for ``fetch_entry`` and records every simulated fetch."""

    def __init__(self, entries, fail_ids=()):
        self.entries = entries
        self.fail_ids = set(fail_ids)
        self.calls = []

    def __call__(self, simkl_id):
        self.calls.append(simkl_id)
        if simkl_id in self.fail_ids:
            return None
        return self.entries.get(simkl_id)


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


def _install(monkeypatch, entries, fail_ids=()):
    spy = _FetchSpy(entries, fail_ids)
    monkeypatch.setattr(season_entry, "fetch_entry", spy)
    monkeypatch.setattr(season_entry, "_CACHE", _FakeCache())
    return spy


# ── resolve_season_entry ─────────────────────────────────────


def test_base_hit_returns_the_base_ids(monkeypatch):
    spy = _install(monkeypatch, ENTRIES)

    result = season_entry.resolve_season_entry(1059371, 1)

    assert result == BASE_IDS
    # Season 1 is covered by the base entry: no sequel fetches.
    assert spy.calls == [1059371]


def test_chain_hit_resolves_the_season_three_entry(monkeypatch):
    spy = _install(monkeypatch, ENTRIES)

    result = season_entry.resolve_season_entry(1059371, 3)

    assert result == SEASON3_IDS
    # The walk follows the sequel relations in order until the cour entry
    # covering the season shows up.
    assert spy.calls == [1059371, 1524389, 1863030, 2204668, 2832226]


def test_returns_none_when_the_season_is_absent_everywhere(monkeypatch):
    spy = _install(monkeypatch, ENTRIES)

    assert season_entry.resolve_season_entry(1059371, 9) is None
    assert spy.calls == [1059371, 1524389, 1863030, 2204668, 2832226]


def test_returns_none_when_the_base_entry_cannot_be_fetched(monkeypatch):
    spy = _install(monkeypatch, ENTRIES, fail_ids={1059371})

    assert season_entry.resolve_season_entry(1059371, 3) is None
    assert spy.calls == [1059371]


def test_returns_none_when_a_sequel_fetch_fails(monkeypatch):
    spy = _install(monkeypatch, ENTRIES, fail_ids={1863030})

    # The failing cour is skipped; the walk still finds season 3 downstream.
    result = season_entry.resolve_season_entry(1059371, 3)

    assert result == SEASON3_IDS
    assert 1863030 in spy.calls


def test_swallows_fetch_exceptions(monkeypatch):
    def boom(simkl_id):
        raise RuntimeError("boom")

    monkeypatch.setattr(season_entry, "fetch_entry", boom)
    monkeypatch.setattr(season_entry, "_CACHE", _FakeCache())

    assert season_entry.resolve_season_entry(1059371, 3) is None


def test_rejects_unusable_input(monkeypatch):
    spy = _install(monkeypatch, ENTRIES)

    for base_simkl_id in (None, 0, -1, "x", {}):
        assert season_entry.resolve_season_entry(base_simkl_id, 1) is None
    for season in (None, 0, -1, "x", {}):
        assert season_entry.resolve_season_entry(1059371, season) is None

    assert spy.calls == []


def test_resolution_cache_reuse(monkeypatch):
    spy = _install(monkeypatch, ENTRIES)

    first = season_entry.resolve_season_entry(1059371, 3)
    second = season_entry.resolve_season_entry(1059371, 3)

    assert first == SEASON3_IDS
    assert first is second
    assert spy.calls == [1059371, 1524389, 1863030, 2204668, 2832226]


def test_cache_keys_are_per_season(monkeypatch):
    _install(monkeypatch, ENTRIES)

    assert season_entry.resolve_season_entry(1059371, 1) == BASE_IDS
    assert season_entry.resolve_season_entry(1059371, 3) == SEASON3_IDS


def test_walk_cap_is_respected(monkeypatch):
    entries = {}
    relations = []
    # Noise first: non-sequel types and id-less sequels must never be fetched.
    relations.append({"simkl_id": 9999999, "relation_type": "prequel", "year": 2010})
    relations.append({"simkl_id": None, "relation_type": "sequel", "year": 2011})
    for position in range(1, 15):
        simkl_id = 3000000 + position
        relations.append(
            {
                "simkl_id": simkl_id,
                "relation_type": "sequel",
                "year": 2020 + position,
                "title": f"Cour {position}",
            }
        )
        entries[simkl_id] = _entry(simkl_id, [3] if position == 13 else [2])
    entries[9999999] = _entry(9999999, [3])
    chain_base = _entry(1059371, [1], relations=relations)
    all_entries = dict(entries)
    all_entries[1059371] = chain_base
    spy = _install(monkeypatch, all_entries)

    result = season_entry.resolve_season_entry(1059371, 3)

    # The cap stops the walk after 12 sequel fetches: the covering entry at
    # position 13 is never reached, and the prequel noise is never fetched.
    assert result is None
    assert len(spy.calls) == 13
    assert spy.calls[0] == 1059371
    assert 9999999 not in spy.calls
    assert 3000013 not in spy.calls


def test_walk_finds_the_target_at_the_cap_boundary(monkeypatch):
    entries = {}
    relations = []
    for position in range(1, 15):
        simkl_id = 3000000 + position
        relations.append(
            {
                "simkl_id": simkl_id,
                "relation_type": "sequel",
                "year": 2020 + position,
                "title": f"Cour {position}",
            }
        )
        entries[simkl_id] = _entry(simkl_id, [3] if position == 12 else [2])
    chain_base = _entry(1059371, [1], relations=relations)
    all_entries = dict(entries)
    all_entries[1059371] = chain_base
    spy = _install(monkeypatch, all_entries)

    result = season_entry.resolve_season_entry(1059371, 3)

    assert result == {
        "simkl_id": 3000012,
        "anilist_id": None,
        "mal_id": None,
        "kitsu_id": None,
    }
    assert len(spy.calls) == 13


# ── simkl.fetch_entry normalization ──────────────────────────


def _raw_base_payload():
    return {
        "title": "Mushoku Tensei: Jobless Reincarnation",
        "en_title": "Mushoku Tensei: Jobless Reincarnation",
        "ids": {
            "simkl": 1059371,
            "anilist": 108465,
            "mal": 39535,
            "kitsu": 42323,
            "tvdb": 371310,
            "tmdb": 94664,
        },
        "mapped_tvdb_seasons": [1],
        "total_episodes": 11,
        "relations": [
            {
                "relation_type": "sequel",
                "is_direct": True,
                "year": 2021,
                "title": "Part 2",
                "en_title": "Mushoku Tensei: Jobless Reincarnation Part 2",
                "ids": {"simkl": 1524389},
            },
            {
                "relation_type": "sequel",
                "is_direct": False,
                "year": 2023,
                "title": "Season 2",
                "en_title": "Mushoku Tensei II",
                "ids": {"simkl": 1863030},
            },
            {
                "relation_type": "sequel",
                "is_direct": False,
                "year": 2024,
                "title": "Season 2 Part 2",
                "en_title": "Mushoku Tensei II Part 2",
                "ids": {"simkl": 2204668},
            },
            {
                "relation_type": "sequel",
                "is_direct": False,
                "year": 2026,
                "title": "Season 3",
                "en_title": "Mushoku Tensei III",
                "ids": {"simkl": 2832226},
            },
        ],
    }


def _raw_season_three_payload():
    return {
        "title": "Mushoku Tensei III: Jobless Reincarnation Season 3",
        "ids": {
            "simkl": 2832226,
            "anilist": 178789,
            "mal": 59193,
            "kitsu": 49002,
            "anidb": 18727,
        },
        "mapped_tvdb_seasons": [3],
        "total_episodes": 14,
        "first_aired": "2026-07-03",
    }


def _install_simkl_request(monkeypatch, payload, calls=None):
    fake_cache = _FakeCache()
    monkeypatch.setattr(simkl_provider, "_CACHE", fake_cache)

    def _request(endpoint, params):
        if calls is not None:
            calls.append((endpoint, params))
        return payload

    monkeypatch.setattr(simkl_provider, "_request", _request)
    return fake_cache


def test_fetch_entry_normalizes_the_live_season_three_payload(monkeypatch):
    _install_simkl_request(monkeypatch, _raw_season_three_payload())

    entry = simkl_provider.fetch_entry(2832226)

    assert entry == {
        "simkl_id": 2832226,
        "anilist_id": 178789,
        "mal_id": 59193,
        "kitsu_id": 49002,
        "mapped_seasons": [3],
        "relations": [],
        "total_episodes": 14,
    }


def test_fetch_entry_normalizes_the_live_base_payload_relations(monkeypatch):
    _install_simkl_request(monkeypatch, _raw_base_payload())

    entry = simkl_provider.fetch_entry(1059371)

    assert entry["simkl_id"] == 1059371
    assert entry["anilist_id"] == 108465
    assert entry["mal_id"] == 39535
    assert entry["kitsu_id"] == 42323
    assert entry["mapped_seasons"] == [1]
    assert entry["total_episodes"] == 11
    assert entry["relations"] == [
        {
            "simkl_id": 1524389,
            "relation_type": "sequel",
            "year": 2021,
            "title": "Mushoku Tensei: Jobless Reincarnation Part 2",
        },
        {
            "simkl_id": 1863030,
            "relation_type": "sequel",
            "year": 2023,
            "title": "Mushoku Tensei II",
        },
        {
            "simkl_id": 2204668,
            "relation_type": "sequel",
            "year": 2024,
            "title": "Mushoku Tensei II Part 2",
        },
        {
            "simkl_id": 2832226,
            "relation_type": "sequel",
            "year": 2026,
            "title": "Mushoku Tensei III",
        },
    ]


def test_fetch_entry_uses_the_cache(monkeypatch):
    calls = []
    _install_simkl_request(monkeypatch, _raw_season_three_payload(), calls)

    first = simkl_provider.fetch_entry(2832226)
    second = simkl_provider.fetch_entry(2832226)

    assert first is second
    assert len(calls) == 1


def test_fetch_entry_returns_none_for_shapeless_payloads(monkeypatch):
    fake_cache = _install_simkl_request(monkeypatch, None)

    for payload in (
        None,
        "garbage",
        42,
        [],
        {},
        {"mapped_tvdb_seasons": [1]},
        {"ids": {"anilist": 108465}},
    ):
        monkeypatch.setattr(simkl_provider, "_request", lambda endpoint, params, p=payload: p)
        assert simkl_provider.fetch_entry(1059371) is None

    # Shapeless payloads must never poison the cache.
    assert fake_cache.set_calls == 0


def test_fetch_entry_drops_garbage_seasons_and_relations(monkeypatch):
    payload = {
        "ids": {"simkl": 1059371},
        "mapped_tvdb_seasons": [1, "2", None, "x", 3],
        "relations": [
            "garbage",
            {"relation_type": "sequel"},
            {"relation_type": "sequel", "title": "Cour", "ids": {"simkl": "3000001"}},
        ],
    }
    _install_simkl_request(monkeypatch, payload)

    entry = simkl_provider.fetch_entry(1059371)

    assert entry["mapped_seasons"] == [1, 2, 3]
    assert entry["relations"] == [
        {"simkl_id": None, "relation_type": "sequel", "year": None, "title": None},
        {"simkl_id": 3000001, "relation_type": "sequel", "year": None, "title": "Cour"},
    ]
