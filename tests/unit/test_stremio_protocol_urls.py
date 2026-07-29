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
