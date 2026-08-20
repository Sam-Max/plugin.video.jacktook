from unittest.mock import MagicMock

from lib.clients.easynews import ADULT_GROUP_RE, Easynews


def _response_with_item(item):
    response = MagicMock()
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
