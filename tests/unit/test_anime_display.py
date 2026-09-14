import dataclasses
import re
from types import SimpleNamespace

from lib.anime import display
from lib.anime.normalize import AnimeRecord
from lib.anime.providers import anilist as anilist_provider


def test_resolve_menu_title_prefers_english_for_language_zero(monkeypatch):
    record = AnimeRecord(title_en="English Title", title_romaji="Romaji Title")
    monkeypatch.setattr(display, "resolve_identity", lambda ids: record)

    assert display.resolve_menu_title({"tmdb_id": 1}, 0) == "English Title"


def test_resolve_menu_title_prefers_romaji_for_language_one(monkeypatch):
    record = AnimeRecord(title_en="English Title", title_romaji="Romaji Title")
    monkeypatch.setattr(display, "resolve_identity", lambda ids: record)

    assert display.resolve_menu_title({"tmdb_id": 1}, 1) == "Romaji Title"


def test_resolve_menu_title_coerces_string_language(monkeypatch):
    record = AnimeRecord(title_en="English Title", title_romaji="Romaji Title")
    monkeypatch.setattr(display, "resolve_identity", lambda ids: record)

    assert display.resolve_menu_title({"tmdb_id": 1}, "1") == "Romaji Title"


def test_resolve_menu_title_returns_none_when_provider_fails(monkeypatch):
    monkeypatch.setattr(display, "resolve_identity", lambda ids: None)

    assert display.resolve_menu_title({"tmdb_id": 1}, 0) is None


def test_resolve_menu_title_returns_none_without_titles(monkeypatch):
    monkeypatch.setattr(display, "resolve_identity", lambda ids: AnimeRecord(tmdb_id=1))

    assert display.resolve_menu_title({"tmdb_id": 1}, 0) is None


def test_resolve_menu_title_swallows_identity_exceptions(monkeypatch):
    def boom(ids):
        raise RuntimeError("boom")

    monkeypatch.setattr(display, "resolve_identity", boom)

    assert display.resolve_menu_title({"tmdb_id": 1}, 0) is None


def test_resolve_menu_record_swallows_identity_exceptions(monkeypatch):
    def boom(ids):
        raise RuntimeError("boom")

    monkeypatch.setattr(display, "resolve_identity", boom)

    assert display.resolve_menu_record({"tmdb_id": 1}) is None


def test_pick_original_title_returns_the_other_language():
    record = AnimeRecord(title_en="English Title", title_romaji="Romaji Title")

    assert display.pick_original_title(record, 0) == "Romaji Title"
    assert display.pick_original_title(record, 1) == "English Title"


def test_pick_original_title_returns_none_without_alternate():
    record = AnimeRecord(title_en="English Title")

    assert display.pick_original_title(record, 0) is None
    assert display.pick_original_title(None, 0) is None


# --- AniList detail provider -------------------------------------------------


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


def _fail(*args, **kwargs):
    raise AssertionError("unexpected call")


def _character_edge(name, role, image=None):
    node = {"id": 1, "name": {"full": name}}
    if image is not None:
        node["image"] = {"medium": image}
    return {"role": role, "node": node}


def _staff_edge(name, role):
    return {"role": role, "node": {"id": 2, "name": {"full": name}}}


def _studio_edge(name):
    return {"isMain": True, "node": {"id": 3, "name": name}}


def _detail_payload(characters=(), staff=(), studios=()):
    return {
        "data": {
            "Media": {
                "characters": {"edges": list(characters)},
                "staff": {"edges": list(staff)},
                "studios": {"edges": list(studios)},
            }
        }
    }


def test_detail_query_carries_the_expected_fields_and_caps():
    fields = anilist_provider.DETAIL_FIELDS

    assert "studios(isMain: true)" in fields
    assert "characters(sort: [ROLE, RELEVANCE, ID], perPage: 8)" in fields
    assert "staff(sort: [RELEVANCE, ID], perPage: 6)" in fields
    assert "image {" in fields
    assert "Media(id: $id, type: ANIME)" in anilist_provider.MEDIA_BY_ID_DETAIL_QUERY
    assert "Media(idMal: $idMal, type: ANIME)" in anilist_provider.MEDIA_BY_MAL_DETAIL_QUERY
    # The detail query must not reuse the listing field set.
    for listing_only in ("idMal", "bannerImage", "duration", "startDate"):
        assert listing_only not in anilist_provider.MEDIA_BY_ID_DETAIL_QUERY


def test_anime_fields_are_unchanged_and_free_of_detail_fields():
    names = re.findall(r"^ {4}(\w+)", anilist_provider.ANIME_FIELDS, re.MULTILINE)

    assert tuple(names) == (
        "id",
        "idMal",
        "title",
        "synonyms",
        "format",
        "status",
        "episodes",
        "duration",
        "description",
        "coverImage",
        "bannerImage",
        "startDate",
    )
    for detail in ("characters", "staff", "studios"):
        assert detail not in anilist_provider.ANIME_FIELDS


def test_anime_record_fields_are_unchanged():
    assert tuple(field.name for field in dataclasses.fields(AnimeRecord)) == (
        "anilist_id",
        "mal_id",
        "anidb_id",
        "kitsu_id",
        "tmdb_id",
        "tvdb_id",
        "imdb_id",
        "simkl_id",
        "title_en",
        "title_romaji",
        "title_native",
        "title_default",
        "episodes",
        "format",
        "status",
        "year",
        "description",
        "cover",
        "banner",
        "synonyms",
    )


def test_media_cast_and_studio_normalizes_and_caps(monkeypatch):
    cache = _FakeCache()
    monkeypatch.setattr(anilist_provider, "_CACHE", cache)
    payload = _detail_payload(
        characters=[
            _character_edge(f"Character {i}", "MAIN", f"http://img/{i}.jpg") for i in range(12)
        ],
        staff=[_staff_edge(f"Staff {i}", "Director") for i in range(9)],
        studios=[
            _studio_edge("WIT STUDIO"),
            _studio_edge(""),
            _studio_edge("   "),
            _studio_edge("MAPPA"),
        ],
    )
    monkeypatch.setattr(anilist_provider, "_post", lambda query, variables: payload)

    extras = anilist_provider.media_cast_and_studio(anilist_id=16498)

    assert len(extras["cast"]) == 8
    assert len(extras["staff"]) == 6
    assert extras["studios"] == ["WIT STUDIO", "MAPPA"]
    assert [entry["name"] for entry in extras["cast"]] == [f"Character {i}" for i in range(8)]
    assert extras["cast"][0] == {
        "name": "Character 0",
        "role": "MAIN",
        "image": "http://img/0.jpg",
    }
    assert set(extras["cast"][0]) == {"name", "role", "image"}
    assert set(extras["staff"][0]) == {"name", "role"}
    assert extras["staff"][0] == {"name": "Staff 0", "role": "Director"}
    assert cache.set_calls == 1


def test_media_cast_and_studio_returns_none_for_unusable_payloads(monkeypatch):
    cache = _FakeCache()
    monkeypatch.setattr(anilist_provider, "_CACHE", cache)

    for payload in (None, "nope", [], {"data": None}, {"data": {}}, {"data": {"Media": []}}):
        monkeypatch.setattr(
            anilist_provider, "_post", lambda query, variables, payload=payload: payload
        )
        assert anilist_provider.media_cast_and_studio(anilist_id=1) is None

    assert cache.set_calls == 0


def test_media_cast_and_studio_returns_none_when_the_request_raises(monkeypatch):
    monkeypatch.setattr(anilist_provider, "_CACHE", _FakeCache())

    def boom(query, variables):
        raise RuntimeError("network")

    monkeypatch.setattr(anilist_provider, "_post", boom)

    assert anilist_provider.media_cast_and_studio(anilist_id=1) is None


def test_media_cast_and_studio_returns_none_and_skips_fetch_without_ids(monkeypatch):
    monkeypatch.setattr(anilist_provider, "_CACHE", _FakeCache())
    monkeypatch.setattr(anilist_provider, "_post", _fail)

    assert anilist_provider.media_cast_and_studio() is None


def test_media_cast_and_studio_prefers_anilist_id_over_mal_id(monkeypatch):
    monkeypatch.setattr(anilist_provider, "_CACHE", _FakeCache())
    seen = []

    def fake_post(query, variables):
        seen.append((query, variables))
        return _detail_payload(characters=[_character_edge("Eren", "MAIN")])

    monkeypatch.setattr(anilist_provider, "_post", fake_post)

    by_id = anilist_provider.media_cast_and_studio(anilist_id=16498, mal_id=2)
    by_mal = anilist_provider.media_cast_and_studio(mal_id=2)

    assert seen[0] == (anilist_provider.MEDIA_BY_ID_DETAIL_QUERY, {"id": 16498})
    assert seen[1] == (anilist_provider.MEDIA_BY_MAL_DETAIL_QUERY, {"idMal": 2})
    assert by_id["cast"][0]["name"] == "Eren"
    assert by_mal["cast"][0]["name"] == "Eren"


def test_media_cast_and_studio_caches_the_normalized_result(monkeypatch):
    cache = _FakeCache()
    monkeypatch.setattr(anilist_provider, "_CACHE", cache)
    calls = []

    def fake_post(query, variables):
        calls.append(variables)
        return _detail_payload(characters=[_character_edge("Eren", "MAIN", "http://img/e.jpg")])

    monkeypatch.setattr(anilist_provider, "_post", fake_post)

    first = anilist_provider.media_cast_and_studio(anilist_id=7)
    second = anilist_provider.media_cast_and_studio(anilist_id=7)

    assert calls == [{"id": 7}]
    assert first == second
    assert cache.set_calls == 1
    # Only the normalized result is cached, never the raw payload.
    assert cache.store["anilist:cast:id:7"] == first
    assert "data" not in cache.store["anilist:cast:id:7"]


def test_media_cast_and_studio_cache_namespace_is_separate_from_media(monkeypatch):
    cache = _FakeCache()
    cache.store["anilist:id:7"] = {"id": 7, "title": {"romaji": "Show"}}
    monkeypatch.setattr(anilist_provider, "_CACHE", cache)
    monkeypatch.setattr(
        anilist_provider,
        "_post",
        lambda query, variables: _detail_payload(studios=[_studio_edge("WIT STUDIO")]),
    )

    extras = anilist_provider.media_cast_and_studio(anilist_id=7)

    assert extras == {"cast": [], "staff": [], "studios": ["WIT STUDIO"]}
    assert "anilist:cast:id:7" in cache.store


# --- Display helpers ---------------------------------------------------------


class _FakeListInfoTag:
    def __init__(self):
        self.set_cast_calls = []
        self.set_studio_calls = []

    def setCast(self, actors):
        self.set_cast_calls.append(actors)

    def setStudio(self, studios):
        self.set_studio_calls.append(studios)


class _FakeListItem:
    def __init__(self):
        self.info = _FakeListInfoTag()
        self.properties = {}

    def getVideoInfoTag(self):
        return self.info

    def setProperty(self, key, value):
        self.properties[key] = value

    def addContextMenuItems(self, items):
        pass


class _FakeXbmc:
    """Records every ``xbmc.Actor`` construction."""

    def __init__(self):
        self.actors = []

    def Actor(self, **kwargs):
        self.actors.append(kwargs)
        return kwargs


def test_resolve_menu_extras_returns_none_without_ids_and_skips_the_fetch(monkeypatch):
    monkeypatch.setattr(display, "resolve_identity", lambda ids: AnimeRecord(tmdb_id=1))
    monkeypatch.setattr(display.anilist, "media_cast_and_studio", _fail)

    assert display.resolve_menu_extras({"tmdb_id": 1}) is None


def test_resolve_menu_extras_fetches_when_an_id_is_known(monkeypatch):
    monkeypatch.setattr(
        display, "resolve_identity", lambda ids: AnimeRecord(anilist_id=9, mal_id=3)
    )
    seen = []

    def fake_fetch(anilist_id=None, mal_id=None):
        seen.append((anilist_id, mal_id))
        return {
            "cast": [{"name": "Eren", "role": "MAIN", "image": ""}],
            "staff": [],
            "studios": ["WIT"],
        }

    monkeypatch.setattr(display.anilist, "media_cast_and_studio", fake_fetch)

    extras = display.resolve_menu_extras({"tmdb_id": 1})

    assert seen == [(9, 3)]
    assert extras["studios"] == ["WIT"]


def test_resolve_menu_extras_falls_back_to_mal_id(monkeypatch):
    monkeypatch.setattr(display, "resolve_identity", lambda ids: AnimeRecord(mal_id=3))
    seen = []

    def fake_fetch(anilist_id=None, mal_id=None):
        seen.append((anilist_id, mal_id))
        return {"cast": [], "staff": [{"name": "A", "role": "Director"}], "studios": []}

    monkeypatch.setattr(display.anilist, "media_cast_and_studio", fake_fetch)

    assert display.resolve_menu_extras({"tmdb_id": 1})["staff"][0]["name"] == "A"
    assert seen == [(None, 3)]


def test_resolve_menu_extras_returns_none_on_provider_failure(monkeypatch):
    monkeypatch.setattr(display, "resolve_identity", lambda ids: AnimeRecord(anilist_id=9))

    def boom(anilist_id=None, mal_id=None):
        raise RuntimeError("network")

    monkeypatch.setattr(display.anilist, "media_cast_and_studio", boom)
    assert display.resolve_menu_extras({"tmdb_id": 1}) is None

    for value in (None, "nope", {}, {"cast": [], "staff": [], "studios": []}):
        monkeypatch.setattr(
            display.anilist,
            "media_cast_and_studio",
            lambda anilist_id=None, mal_id=None, value=value: value,
        )
        assert display.resolve_menu_extras({"tmdb_id": 1}) is None


def test_resolve_menu_extras_swallows_identity_exceptions(monkeypatch):
    def boom(ids):
        raise RuntimeError("boom")

    monkeypatch.setattr(display, "resolve_identity", boom)

    assert display.resolve_menu_extras({"tmdb_id": 1}) is None


def test_apply_anime_extras_renders_cast_staff_and_studios(monkeypatch):
    fake_xbmc = _FakeXbmc()
    monkeypatch.setattr(display, "xbmc", fake_xbmc)
    list_item = _FakeListItem()
    extras = {
        "cast": [
            {"name": "Eren", "role": "MAIN", "image": "http://img/e.jpg"},
            {"name": "  Mikasa  ", "role": "MAIN", "image": ""},
            {"name": "", "role": "SUPPORTING", "image": "http://img/none.jpg"},
        ],
        "staff": [{"name": "Wit", "role": "Director"}],
        "studios": ["WIT STUDIO", "", "MAPPA"],
    }

    display.apply_anime_extras(list_item, extras)

    assert fake_xbmc.actors == [
        {"name": "Eren", "role": "MAIN", "thumbnail": "http://img/e.jpg", "order": 0},
        {"name": "Mikasa", "role": "MAIN", "thumbnail": "", "order": 1},
        {"name": "Wit", "role": "Director", "thumbnail": "", "order": 2},
    ]
    assert list_item.info.set_cast_calls == [fake_xbmc.actors]
    assert list_item.info.set_studio_calls == [["WIT STUDIO", "MAPPA"]]


def test_apply_anime_extras_changes_nothing_without_a_payload(monkeypatch):
    fake_xbmc = _FakeXbmc()
    monkeypatch.setattr(display, "xbmc", fake_xbmc)
    list_item = _FakeListItem()

    for extras in (
        None,
        {},
        "nope",
        [],
        {"cast": [], "staff": [], "studios": []},
        {"cast": "nope", "staff": None, "studios": None},
        {"cast": [{"name": ""}], "staff": ["nope"], "studios": [""]},
    ):
        display.apply_anime_extras(list_item, extras)

    assert list_item.info.set_cast_calls == []
    assert list_item.info.set_studio_calls == []
    assert fake_xbmc.actors == []


def test_apply_anime_extras_never_raises_for_a_broken_list_item(monkeypatch):
    monkeypatch.setattr(display, "xbmc", _FakeXbmc())
    extras = {"cast": [{"name": "Eren", "role": "MAIN", "image": ""}], "studios": ["WIT"]}

    display.apply_anime_extras(None, extras)
    display.apply_anime_extras(object(), extras)


# --- Detail-view hooks --------------------------------------------------------


def _sync_collect(results, func, *args, **kwargs):
    collected = []
    for item in results:
        result = func(item, *args, **kwargs)
        if result is not None:
            collected.append(result)
    return collected


def _episode(number):
    return SimpleNamespace(name=f"Episode {number}", episode_number=number)


def _patch_episode_hook(monkeypatch, shows_view, episodes, extras):
    seeds = []
    applied = []

    def fake_resolve(seed):
        seeds.append(seed)
        return extras

    def fake_apply(list_item, resolved):
        applied.append((list_item, resolved))

    monkeypatch.setattr(
        shows_view, "tmdb_get", lambda *args, **kwargs: SimpleNamespace(episodes=episodes)
    )
    monkeypatch.setattr(shows_view, "get_fanart_details", lambda **kwargs: {})
    monkeypatch.setattr(shows_view, "execute_thread_pool_collection", _sync_collect)
    monkeypatch.setattr(shows_view, "make_list_item", lambda label=None, **kwargs: _FakeListItem())
    monkeypatch.setattr(shows_view, "set_media_infoTag", lambda *args, **kwargs: None)
    monkeypatch.setattr(shows_view, "add_tmdb_episode_context_menu", lambda *args, **kwargs: [])
    monkeypatch.setattr(shows_view, "is_trakt_auth", lambda: False)
    monkeypatch.setattr(shows_view, "add_simkl_history_context_menu", lambda *args, **kwargs: [])
    monkeypatch.setattr(shows_view, "add_nuvio_history_context_menu", lambda *args, **kwargs: [])
    monkeypatch.setattr(shows_view, "add_directory_items_batch", lambda items: None)
    monkeypatch.setattr(shows_view, "build_url", lambda *args, **kwargs: "url")
    monkeypatch.setattr(shows_view, "resolve_menu_extras", fake_resolve)
    monkeypatch.setattr(shows_view, "apply_anime_extras", fake_apply)

    return seeds, applied


def test_show_episode_info_resolves_anime_extras_once_per_title(monkeypatch):
    from lib.utils.views import shows as shows_view

    extras = {
        "cast": [{"name": "Eren", "role": "MAIN", "image": ""}],
        "staff": [],
        "studios": ["WIT"],
    }
    seeds, applied = _patch_episode_hook(
        monkeypatch, shows_view, [_episode(1), _episode(2), _episode(3)], extras
    )
    ids = {"tmdb_id": 1, "tvdb_id": 2, "imdb_id": ""}

    count = shows_view.show_episode_info("Show", 1, ids, "tv", "", anime=True)

    assert count == 3
    assert len(seeds) == 1
    assert seeds[0] == {"tmdb_id": 1, "tvdb_id": 2, "imdb_id": "", "media_type": "tv"}
    assert len(applied) == 3
    assert len({id(list_item) for list_item, _ in applied}) == 3
    assert all(resolved is extras for _, resolved in applied)


def test_show_episode_info_skips_anime_extras_for_non_anime(monkeypatch):
    from lib.utils.views import shows as shows_view

    seeds, applied = _patch_episode_hook(
        monkeypatch,
        shows_view,
        [_episode(1), _episode(2)],
        {"cast": [], "staff": [], "studios": []},
    )

    count = shows_view.show_episode_info("Show", 1, {"tmdb_id": 1}, "tv", "", anime=False)

    assert count == 2
    assert seeds == []
    assert applied == []


def test_show_season_info_resolves_anime_extras_once_per_title(monkeypatch):
    from lib.utils.views import shows as shows_view

    seasons = [
        SimpleNamespace(name="Season 1", overview="First", season_number=1),
        SimpleNamespace(name="Season 2", overview="Second", season_number=2),
    ]
    details = SimpleNamespace(name="Show", seasons=seasons, external_ids={})
    extras = {"cast": [], "staff": [{"name": "Wit", "role": "Director"}], "studios": ["WIT"]}
    seeds = []
    applied = []

    def fake_resolve(seed):
        seeds.append(seed)
        return extras

    def fake_apply(list_item, resolved):
        applied.append((list_item, resolved))

    monkeypatch.setattr(shows_view, "tmdb_get", lambda *args, **kwargs: details)
    monkeypatch.setattr(shows_view, "get_fanart_details", lambda **kwargs: {})
    monkeypatch.setattr(shows_view, "execute_thread_pool_collection", _sync_collect)
    monkeypatch.setattr(shows_view, "make_list_item", lambda label=None, **kwargs: _FakeListItem())
    monkeypatch.setattr(shows_view, "set_media_infoTag", lambda *args, **kwargs: None)
    monkeypatch.setattr(shows_view, "add_tmdb_show_context_menu", lambda *args, **kwargs: [])
    monkeypatch.setattr(shows_view, "is_trakt_auth", lambda: False)
    monkeypatch.setattr(shows_view, "add_directory_items_batch", lambda items: None)
    monkeypatch.setattr(shows_view, "build_url", lambda *args, **kwargs: "url")
    monkeypatch.setattr(shows_view, "resolve_menu_extras", fake_resolve)
    monkeypatch.setattr(shows_view, "apply_anime_extras", fake_apply)

    shows_view.show_season_info({"tvdb_id": 2}, "tv", "", anime=True)

    assert len(seeds) == 1
    assert seeds[0]["media_type"] == "tv"
    assert seeds[0]["tvdb_id"] == 2
    assert len(applied) == 2
    assert all(resolved is extras for _, resolved in applied)
