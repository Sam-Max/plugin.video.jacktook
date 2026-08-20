from unittest.mock import MagicMock

from lib.clients.easynews import ADULT_GROUP_RE, Easynews


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
    page1 = _search_response([("hash-1", "Movie 1080p"), ("hash-2", "Movie 720p")])
    page2 = _search_response([("hash-3", "Movie 4K")])
    page3 = _search_response([("hash-4", "Movie 480p")])
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
    repeated_page = _search_response([("hash-1", "Movie 1080p"), ("hash-2", "Movie 720p")])
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
    page1 = _search_response([("hash-1", "Movie 1080p")])
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
    page1 = _search_response([("hash-1", "Movie 1080p"), ("hash-2", "Movie 720p")])

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
