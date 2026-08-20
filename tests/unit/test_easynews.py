from unittest.mock import MagicMock

from lib.clients.easynews import ADULT_GROUP_RE, Easynews, is_series_query
from lib.utils.parsers.title_parser import matches_title, sanitize_title


def _response_with_item(item):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "downURL": "https://members.easynews.com",
        "dlFarm": "farm1",
        "dlPort": "443",
        "data": [
            {
                "0": "posthash",
                "4": "1024",
                "10": "Example 1080p",
                "11": ".mkv",
                "14": "1h",
                "type": "VIDEO",
                **item,
            }
        ],
    }
    return response


def _search_response(posts):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "downURL": "https://members.easynews.com",
        "dlFarm": "farm1",
        "dlPort": "443",
        "data": [
            {
                "0": post_hash,
                "4": "1024",
                "10": post_title,
                "11": ".mkv",
                "14": "1h",
                "type": "VIDEO",
            }
            for post_hash, post_title in posts
        ],
    }
    return response


def test_parse_response_adds_https_to_protocol_relative_download_url():
    response = MagicMock()
    response.json.return_value = {
        "downURL": "//members.easynews.com",
        "dlFarm": "farm1",
        "dlPort": "443",
        "data": [
            {
                "0": "posthash",
                "4": "1024",
                "10": "Example 1080p",
                "11": ".mkv",
                "14": "1h",
                "type": "VIDEO",
            }
        ],
    }

    results = Easynews("user", "password", 10, MagicMock()).parse_response(response)

    assert results[0].url == "https://members.easynews.com/farm1/443/posthash.mkv/Example%201080p.mkv"


def test_parse_response_filters_adult_newsgroups():
    response = _response_with_item({"9": "alt.binaries.erotica.xxx"})

    results = Easynews("user", "password", 10, MagicMock()).parse_response(response)

    assert results == []


def test_parse_response_allows_non_adult_newsgroups():
    response = _response_with_item({"9": "alt.binaries.movies.hd"})

    results = Easynews("user", "password", 10, MagicMock()).parse_response(response)

    assert len(results) == 1


def test_parse_response_filters_password_protected_posts():
    response = _response_with_item({"passwd": "1"})

    results = Easynews("user", "password", 10, MagicMock()).parse_response(response)

    assert results == []


def test_parse_response_allows_posts_without_password():
    response = _response_with_item({})

    results = Easynews("user", "password", 10, MagicMock()).parse_response(response)

    assert len(results) == 1


def test_search_paginates_until_total_cap():
    client = Easynews("user", "password", 10, MagicMock())
    page1 = _search_response([("hash-1", "Movie 2021"), ("hash-2", "Movie 2022")])
    page2 = _search_response([("hash-3", "Movie 2023")])
    page3 = _search_response([("hash-4", "Movie 2024")])
    empty_page = MagicMock()
    empty_page.raise_for_status.return_value = None
    empty_page.json.return_value = {
        "downURL": "https://members.easynews.com",
        "dlFarm": "farm1",
        "dlPort": "443",
        "data": [],
    }
    client.session.get = MagicMock(
        side_effect=[
            page1,
            page2,
            page3,
            empty_page,
        ]
    )

    results = client.search("Movie", "movies", "movies")

    assert len(results) == 4
    assert client.session.get.call_count == 4
    assert client.session.get.call_args_list[0].kwargs["params"]["pno"] == 1
    assert client.session.get.call_args_list[1].kwargs["params"]["pno"] == 2
    assert client.session.get.call_args_list[2].kwargs["params"]["pno"] == 3
    assert client.session.get.call_args_list[3].kwargs["params"]["pno"] == 4


def test_search_stops_when_page_repeats():
    client = Easynews("user", "password", 10, MagicMock())
    repeated_page = _search_response([("hash-1", "Movie 2021"), ("hash-2", "Movie 2022")])
    client.session.get = MagicMock(
        side_effect=[
            repeated_page,
            repeated_page,
        ]
    )

    results = client.search("Movie", "movies", "movies")

    assert len(results) == 2
    assert client.session.get.call_count == 2


def test_search_stops_on_empty_page():
    client = Easynews("user", "password", 10, MagicMock())
    page1 = _search_response([("hash-1", "Movie 2021")])
    empty_page = MagicMock()
    empty_page.raise_for_status.return_value = None
    empty_page.json.return_value = {
        "downURL": "https://members.easynews.com",
        "dlFarm": "farm1",
        "dlPort": "443",
        "data": [],
    }
    client.session.get = MagicMock(side_effect=[page1, empty_page])

    results = client.search("Movie", "movies", "movies")

    assert len(results) == 1
    assert client.session.get.call_count == 2


def test_search_returns_partial_results_on_page_error():
    client = Easynews("user", "password", 10, MagicMock())
    page1 = _search_response([("hash-1", "Movie 2021"), ("hash-2", "Movie 2022")])

    def failing_get(*_args, **_kwargs):
        if client.session.get.call_count >= 2:
            raise ConnectionError("boom")
        return page1

    client.session.get = MagicMock(side_effect=failing_get)

    results = client.search("Movie", "movies", "movies")

    assert len(results) == 2
    assert client.session.get.call_count == 2


def test_search_returns_empty_on_first_page_error():
    client = Easynews("user", "password", 10, MagicMock())
    client.session.get = MagicMock(side_effect=ConnectionError("boom"))

    results = client.search("Movie", "movies", "movies")

    assert results == []
    assert client.session.get.call_count == 1


def test_parse_response_filters_title_mismatch():
    response = _response_with_item({"10": "Totally Different Movie"})

    results = Easynews("user", "password", 10, MagicMock()).parse_response(
        response, query="Dune"
    )

    assert results == []


def test_parse_response_keeps_exact_title_match():
    response = _response_with_item({"10": "Dune"})

    results = Easynews("user", "password", 10, MagicMock()).parse_response(
        response, query="Dune"
    )

    assert len(results) == 1


def test_parse_response_keeps_movie_with_year():
    response = _response_with_item({"10": "Dune 2021"})

    results = Easynews("user", "password", 10, MagicMock()).parse_response(
        response, query="Dune 2021"
    )

    assert len(results) == 1


def test_parse_response_keeps_series_episode():
    response = _response_with_item({"10": "Dune S01E01"})

    results = Easynews("user", "password", 10, MagicMock()).parse_response(
        response, query="Dune S01E01"
    )

    assert len(results) == 1


def test_parse_response_rejects_series_episode_wrong_show():
    response = _response_with_item({"10": "Foundation S01E01"})

    results = Easynews("user", "password", 10, MagicMock()).parse_response(
        response, query="Dune S01E01"
    )

    assert results == []


def test_sanitize_title_normalizes_forms():
    assert sanitize_title("Slangedræber.2023.1080p") == sanitize_title("Slangedraeber 2023 1080p")
    assert sanitize_title("Tom & Jerry (2021)") == "tom and jerry 2021"


def test_matches_title_strict_movie():
    assert matches_title("Dune", "Dune", strict=True)
    assert matches_title("Dune 2021", "Dune 2021", strict=True)
    assert matches_title("Dune 2021 2160p", "Dune", strict=True) is False
    assert matches_title("Dune Part Two", "Dune", strict=True) is False
    assert matches_title("Dune 2", "Dune", strict=True) is False


def test_matches_title_non_strict_series():
    assert matches_title("Dune S01E01 1080p", "Dune S01E01", strict=False)
    assert matches_title("Foundation S01E01", "Dune S01E01", strict=False) is False


def test_is_series_query_detects_episode_codes():
    assert is_series_query("Dune S01E01")
    assert is_series_query("Dune S01")
    assert not is_series_query("Dune 2021")


def test_adult_group_regex_matches_expected_tokens():
    adult_groups = [
        "alt.binaries.erotica",
        "alt.binaries.xxx",
        "alt.binaries.porn.movies",
        "a.b.pron",
        "alt.binaries.masturbation",
        "alt.binaries.bestiality",
        "alt.binaries.incest",
        "alt.binaries.hentai",
        "alt.binaries.shemale",
        "alt.binaries.transsexual",
        "alt.binaries.sex",
    ]
    for group in adult_groups:
        assert ADULT_GROUP_RE.search(group), f"expected adult match for {group}"


def test_adult_group_regex_does_not_match_innocent_tokens():
    innocent_groups = [
        "alt.binaries.movies",
        "alt.binaries.gay",
        "alt.binaries.teen",
        "alt.binaries.documentaries",
        "alt.binaries.multimedia",
        "alt.binaries.tv",
    ]
    for group in innocent_groups:
        assert not ADULT_GROUP_RE.search(group), f"expected no adult match for {group}"
