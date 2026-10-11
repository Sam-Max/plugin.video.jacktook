from urllib.parse import parse_qs

import pytest

from lib.api.tmdbv3api.as_obj import AsObj
from lib.api.tmdbv3api.objs.anime import TmdbAnime
from lib.clients.tmdb.anime import TmdbAnimeClient
from lib.utils.general.utils import Anime

ANIMATION_GENRE = 16
ANIME_KEYWORD = 210024


def _item(item_id, genre_ids):
    return AsObj({"id": item_id, "name": f"show {item_id}", "genre_ids": genre_ids})


def _page(items):
    return AsObj({"results": items, "total_results": len(items), "page": 1})


@pytest.fixture
def keyword_calls(monkeypatch):
    """Map TMDB id -> keyword ids and record every keyword request made."""
    calls = []
    keywords_by_id = {}

    def fake_keywords(self, mode, tmdb_id):
        calls.append((mode, tmdb_id))
        ids = keywords_by_id.get(tmdb_id)
        if ids is None:
            return None
        key = "results" if mode == "tv" else "keywords"
        return AsObj({key: [AsObj({"id": kid, "name": "k"}) for kid in ids]})

    monkeypatch.setattr(TmdbAnime, "tmdb_keywords", fake_keywords)
    return calls, keywords_by_id


def test_anime_search_queries_tv_endpoint_without_list_key(monkeypatch):
    seen = {}

    def fake_request_obj(self, action, params="", **kwargs):
        seen["action"] = action
        seen["params"] = parse_qs(params)
        seen["kwargs"] = kwargs
        return None

    monkeypatch.setattr(TmdbAnime, "_request_obj", fake_request_obj)

    TmdbAnime().anime_search("naruto", "tv", 2)

    assert seen["action"] == "/search/tv"
    assert seen["params"]["query"] == ["naruto"]
    assert seen["params"]["page"] == ["2"]
    assert "key" not in seen["kwargs"]


def test_anime_search_queries_movie_endpoint(monkeypatch):
    seen = {}

    def fake_request_obj(self, action, params="", **kwargs):
        seen["action"] = action
        return None

    monkeypatch.setattr(TmdbAnime, "_request_obj", fake_request_obj)

    TmdbAnime().anime_search("akira", "movies", 1)

    assert seen["action"] == "/search/movie"


def test_filter_drops_results_without_animation_genre_without_keyword_requests(keyword_calls):
    calls, _ = keyword_calls
    data = _page([_item(1, [18, 80]), _item(2, [35])])

    result = TmdbAnimeClient.filter_anime_search_results(data, "tv")

    assert list(result.results) == []
    assert result.total_results == 0
    assert calls == []


def test_filter_keeps_animation_results_only_when_anime_keyword_present(keyword_calls):
    calls, keywords_by_id = keyword_calls
    keywords_by_id[10] = [ANIME_KEYWORD]
    keywords_by_id[11] = [999]
    data = _page([_item(10, [ANIMATION_GENRE]), _item(11, [ANIMATION_GENRE]), _item(12, [35])])

    result = TmdbAnimeClient.filter_anime_search_results(data, "tv")

    assert [item.id for item in result.results] == [10]
    assert result.total_results == 1
    assert sorted(calls) == [("tv", 10), ("tv", 11)]


def test_filter_uses_keywords_key_for_movies(keyword_calls):
    _, keywords_by_id = keyword_calls
    keywords_by_id[20] = [ANIME_KEYWORD]
    data = _page([_item(20, [ANIMATION_GENRE])])

    result = TmdbAnimeClient.filter_anime_search_results(data, "movies")

    assert [item.id for item in result.results] == [20]


def test_filter_excludes_result_when_keyword_request_fails(keyword_calls):
    _, keywords_by_id = keyword_calls
    keywords_by_id[30] = None
    data = _page([_item(30, [ANIMATION_GENRE])])

    result = TmdbAnimeClient.filter_anime_search_results(data, "tv")

    assert list(result.results) == []


def test_filter_preserves_original_order(keyword_calls):
    _, keywords_by_id = keyword_calls
    for tmdb_id in (41, 42, 43):
        keywords_by_id[tmdb_id] = [ANIME_KEYWORD]
    data = _page(
        [_item(41, [ANIMATION_GENRE]), _item(42, [ANIMATION_GENRE]), _item(43, [ANIMATION_GENRE])]
    )

    result = TmdbAnimeClient.filter_anime_search_results(data, "tv")

    assert [item.id for item in result.results] == [41, 42, 43]


def test_search_category_fetches_filters_and_processes_results(monkeypatch, keyword_calls):
    _, keywords_by_id = keyword_calls
    keywords_by_id[7] = [ANIME_KEYWORD]
    from lib.clients.tmdb import tmdb as tmdb_module

    monkeypatch.setattr(tmdb_module, "set_content_type", lambda mode: None)
    monkeypatch.setattr(TmdbAnimeClient, "handle_anime_search_query", lambda self, page: "naruto")
    searched = []

    def fake_search(self, query, mode, page_no, adult=False):
        searched.append((query, mode, page_no))
        return _page([_item(7, [ANIMATION_GENRE]), _item(8, [18])])

    processed = []
    monkeypatch.setattr(TmdbAnime, "anime_search", fake_search)
    monkeypatch.setattr(
        TmdbAnimeClient,
        "process_anime_results",
        lambda self, data, submode, page, mode, category: processed.append(
            ([item.id for item in data.results], submode, page, mode, category)
        ),
    )

    tmdb_module.TmdbClient.handle_tmdb_anime_query(Anime.SEARCH, "anime", "tv", 1)

    assert searched == [("naruto", "tv", 1)]
    assert processed == [([7], "tv", 1, "anime", Anime.SEARCH)]


def test_search_category_does_nothing_when_keyboard_is_cancelled(monkeypatch):
    from lib.clients.tmdb import tmdb as tmdb_module

    monkeypatch.setattr(tmdb_module, "set_content_type", lambda mode: None)
    monkeypatch.setattr(TmdbAnimeClient, "handle_anime_search_query", lambda self, page: None)

    def fail_search(self, *args, **kwargs):
        raise AssertionError("search must not run without a query")

    monkeypatch.setattr(TmdbAnime, "anime_search", fail_search)

    tmdb_module.TmdbClient.handle_tmdb_anime_query(Anime.SEARCH, "anime", "tv", 1)


def test_anime_menu_exposes_search_entry_for_tmdb():
    from lib.utils.general.items_menus import anime_items

    search_entries = [item for item in anime_items if item["category"] == Anime.SEARCH]

    assert len(search_entries) == 1
    assert search_entries[0]["api"] == "tmdb"
    assert search_entries[0]["mode"] == "anime"


def test_empty_anime_results_close_the_directory(monkeypatch):
    closed = []
    monkeypatch.setattr(
        "lib.clients.tmdb.anime.end_of_directory", lambda cache=True: closed.append(cache)
    )
    monkeypatch.setattr("lib.clients.tmdb.anime.notification", lambda *a, **k: None)

    TmdbAnimeClient().process_anime_results(_page([]), "tv", 1, "anime", Anime.SEARCH)

    assert closed == [False]
