from unittest.mock import MagicMock, patch

from lib.api.imdb import ratings
from lib.api.imdb.ratings import apply_imdb_ratings, get_imdb_ratings


class FakeCache:
    def __init__(self, data=None):
        self.data = dict(data or {})

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value, expires=None):
        self.data[key] = value


def _response(titles):
    response = MagicMock()
    response.json.return_value = {"data": {"titles": titles}}
    return response


def _title(imdb_id, rating, votes):
    return {"id": imdb_id, "ratingsSummary": {"aggregateRating": rating, "voteCount": votes}}


def test_ratings_are_fetched_in_one_batch_and_cached():
    cache = FakeCache({"imdb_rating|tt0000001": (7.0, 10)})
    titles = [_title("tt1520211", 8.1, 1220075), _title("tt9999999", None, 0)]
    with patch.object(ratings, "cache", cache), patch(
        "requests.post", return_value=_response(titles)
    ) as post:
        result = get_imdb_ratings(["tt0000001", "tt1520211", "tt9999999", "", "bad"])

    assert result == {"tt0000001": (7.0, 10), "tt1520211": (8.1, 1220075)}
    post.assert_called_once()
    assert '"tt1520211", "tt9999999"' in post.call_args.kwargs["json"]["query"]
    assert cache.data["imdb_rating|tt9999999"] == (0.0, 0)


def test_failed_request_is_not_cached():
    import requests

    cache = FakeCache()
    with patch.object(ratings, "cache", cache), patch(
        "requests.post", side_effect=requests.RequestException("boom")
    ):
        assert get_imdb_ratings(["tt1520211"]) == {}
    assert cache.data == {}


def _item(props):
    item = MagicMock()
    item.getProperty.side_effect = lambda key: props.get(key, "")
    return item


def test_apply_sets_imdb_rating_and_label2():
    known = _item({"jacktook.imdb.id": "tt0111161"})
    resolved = _item({"jacktook.imdb.tmdb_ref": "tv:1402"})
    unrated = _item({"jacktook.imdb.tmdb_ref": "movie:1"})
    plain = _item({})
    items = [("u", item, True) for item in (known, resolved, unrated, plain)]

    with patch.object(
        ratings, "resolve_imdb_ids", return_value={("tv", "1402"): "tt1520211"}
    ) as resolve, patch.object(
        ratings,
        "get_imdb_ratings",
        return_value={"tt0111161": (9.3, 3256924), "tt1520211": (8.1, 1220075)},
    ):
        apply_imdb_ratings(items)

    assert list(resolve.call_args.args[0]) == [("tv", "1402"), ("movie", "1")]
    known.getVideoInfoTag().setRating.assert_called_once_with(9.3, 3256924, "imdb", True)
    known.setLabel2.assert_called_once_with("9.3")
    known.getVideoInfoTag().setIMDBNumber.assert_not_called()
    resolved.getVideoInfoTag().setIMDBNumber.assert_called_once_with("tt1520211")
    resolved.setLabel2.assert_called_once_with("8.1")
    unrated.setLabel2.assert_not_called()
    plain.setLabel2.assert_not_called()


def test_apply_without_rateable_items_makes_no_requests():
    with patch.object(ratings, "resolve_imdb_ids") as resolve:
        apply_imdb_ratings([("u", _item({}), True)])
    resolve.assert_not_called()
