from lib.clients.stremio.protocol import build_resource_url


def test_resource_url_contract_encodes_components_and_joins_sorted_extras():
    assert build_resource_url(
        "https://example.com/config",
        "catalog",
        "movie/type",
        "id:part/value",
        {"skip": 100, "search": "game of thrones"},
    ) == (
        "https://example.com/config/catalog/movie%2Ftype/id%3Apart%2Fvalue/"
        "search=game%20of%20thrones&skip=100.json"
    )


def test_resource_url_keeps_base_query_after_resource_path():
    assert build_resource_url(
        "https://bingecat.com/stremio/token/nuvio?bcv=54",
        "catalog",
        "movie",
        "aicat_streamservice_5224868",
    ) == (
        "https://bingecat.com/stremio/token/nuvio/catalog/movie/"
        "aicat_streamservice_5224868.json?bcv=54"
    )


def test_resource_url_appends_extras_after_base_query():
    assert (
        build_resource_url(
            "https://example.com/addon?bcv=54",
            "catalog",
            "movie",
            "popular",
            {"genre": "Drama"},
        )
        == "https://example.com/addon/catalog/movie/popular/genre=Drama.json?bcv=54"
    )
