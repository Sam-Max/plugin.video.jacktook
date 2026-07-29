from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lib.clients import yamtrack


def _movie_data(**overrides):
    data = {
        "mode": "movies",
        "ids": {"tmdb_id": 27205, "imdb_id": "tt1375666"},
        "progress": 90,
    }
    data.update(overrides)
    return data


def _episode_data(**overrides):
    data = {
        "mode": "tv",
        "ids": {"tmdb_id": 1396, "tvdb_id": 81189, "imdb_id": "tt0903747"},
        "tv_data": {"season": 0, "episode": 1},
        "query": "Breaking Bad",
        "title": "Breaking.Bad.S00E01.1080p.WEB-DL",
        "progress": 90,
    }
    data.update(overrides)
    return data


def _settings(enabled=True, base_url="http://yamtrack.local:8000/", token="a/b c"):
    values = {
        "yamtrack_enabled": enabled,
        "yamtrack_base_url": base_url,
        "yamtrack_token": token,
    }
    return lambda key, default=None: values.get(key, default)


def test_movie_payload_prefers_tmdb_and_nests_user_data():
    assert yamtrack.build_payload(_movie_data()) == {
        "Event": "Stop",
        "Item": {
            "Type": "Movie",
            "ProviderIds": {"Tmdb": "27205"},
            "UserData": {"Played": True},
        },
    }


def test_movie_payload_falls_back_to_imdb():
    data = _movie_data(ids={"tmdb_id": "", "imdb_id": "tt1375666"})

    assert yamtrack.build_payload(data)["Item"]["ProviderIds"] == {"Imdb": "tt1375666"}


def test_episode_payload_uses_episode_tvdb_and_never_show_ids(monkeypatch):
    lookup = MagicMock(return_value=SimpleNamespace(tvdb_id=349232, imdb_id="tt9999999"))
    monkeypatch.setattr(yamtrack, "tmdb_get", lookup)

    payload = yamtrack.build_payload(_episode_data())

    lookup.assert_called_once_with(
        "episode_external_ids", {"id": "1396", "season": 0, "episode": 1}
    )
    assert payload == {
        "Event": "Stop",
        "Item": {
            "Type": "Episode",
            "ProviderIds": {"Tvdb": "349232"},
            "SeriesName": "Breaking Bad",
            "ParentIndexNumber": 0,
            "IndexNumber": 1,
            "UserData": {"Played": True},
        },
    }
    assert "81189" not in str(payload)
    assert "tt0903747" not in str(payload)


def test_episode_payload_falls_back_to_episode_imdb(monkeypatch):
    monkeypatch.setattr(
        yamtrack,
        "tmdb_get",
        MagicMock(return_value={"tvdb_id": None, "imdb_id": "tt9999999"}),
    )

    payload = yamtrack.build_payload(_episode_data())

    assert payload["Item"]["ProviderIds"] == {"Imdb": "tt9999999"}


def test_episode_series_name_uses_tmdb_fallback_not_release_title(monkeypatch):
    def fake_tmdb_get(path, _params):
        if path == "episode_external_ids":
            return {"tvdb_id": 349232}
        return SimpleNamespace(name="Breaking Bad")

    monkeypatch.setattr(yamtrack, "tmdb_get", fake_tmdb_get)

    payload = yamtrack.build_payload(_episode_data(query=""))

    assert payload["Item"]["SeriesName"] == "Breaking Bad"
    assert payload["Item"]["SeriesName"] != _episode_data()["title"]


@pytest.mark.parametrize(
    "tv_data",
    ({"season": -1, "episode": 1}, {"season": 1, "episode": 0}, {"season": 1}),
)
def test_episode_rejects_invalid_position_without_lookup(monkeypatch, tv_data):
    lookup = MagicMock()
    monkeypatch.setattr(yamtrack, "tmdb_get", lookup)

    assert yamtrack.build_payload(_episode_data(tv_data=tv_data)) is None
    lookup.assert_not_called()


def test_webhook_url_normalizes_base_and_encodes_token_as_one_segment():
    url = yamtrack.build_webhook_url("HTTP://yamtrack.local:8000/root/", "a/b c")

    assert url == "http://yamtrack.local:8000/root/webhook/jellyfin/a%2Fb%20c"


@pytest.mark.parametrize(
    "base_url",
    (
        "ftp://yamtrack.local",
        "http://user:pass@yamtrack.local",
        "http://yamtrack.local?token=bad",
        "//yamtrack.local",
    ),
)
def test_webhook_url_rejects_invalid_or_credentialed_base(base_url):
    with pytest.raises(ValueError, match="Invalid Yamtrack base URL"):
        yamtrack.build_webhook_url(base_url, "token")


@pytest.mark.parametrize(
    ("enabled", "base_url", "token"),
    ((False, "http://yamtrack.local", "token"), (True, "", "token"), (True, "http://x", "")),
)
def test_disabled_or_incomplete_config_does_not_request(monkeypatch, enabled, base_url, token):
    post = MagicMock()
    monkeypatch.setattr(yamtrack, "get_setting", _settings(enabled, base_url, token))
    monkeypatch.setattr(yamtrack.requests, "post", post)

    assert yamtrack.send_watched_state(_movie_data()) is False
    post.assert_not_called()


def test_send_posts_exactly_once_without_retry(monkeypatch):
    post = MagicMock(side_effect=RuntimeError("network failed"))
    monkeypatch.setattr(yamtrack, "get_setting", _settings())
    monkeypatch.setattr(yamtrack.requests, "post", post)
    monkeypatch.setattr(yamtrack, "kodilog", MagicMock())

    assert yamtrack.send_watched_state(_movie_data()) is False
    post.assert_called_once()


def test_send_uses_bounded_timeout_and_200_as_acceptance(monkeypatch):
    response = SimpleNamespace(status_code=200)
    post = MagicMock(return_value=response)
    monkeypatch.setattr(yamtrack, "get_setting", _settings())
    monkeypatch.setattr(yamtrack.requests, "post", post)

    assert yamtrack.send_watched_state(_movie_data()) is True
    assert post.call_args.kwargs["timeout"] == yamtrack.REQUEST_TIMEOUT


def test_request_logs_never_expose_token_url_or_raw_exception(monkeypatch):
    token = "secret/token"
    full_url = "http://yamtrack.local/webhook/jellyfin/secret%2Ftoken"
    monkeypatch.setattr(yamtrack, "get_setting", _settings(token=token))
    monkeypatch.setattr(
        yamtrack.requests,
        "post",
        MagicMock(side_effect=RuntimeError(f"failed POST {full_url}")),
    )
    log = MagicMock()
    monkeypatch.setattr(yamtrack, "kodilog", log)

    yamtrack.send_watched_state(_movie_data())

    logged = " ".join(str(item) for item in log.call_args_list)
    assert token not in logged
    assert full_url not in logged
    assert "failed POST" not in logged


def test_below_watched_threshold_does_not_build_or_request(monkeypatch):
    post = MagicMock()
    lookup = MagicMock()
    monkeypatch.setattr(yamtrack, "get_setting", _settings())
    monkeypatch.setattr(yamtrack, "tmdb_get", lookup)
    monkeypatch.setattr(yamtrack.requests, "post", post)

    assert yamtrack.send_watched_state(_episode_data(progress=89.9)) is False
    lookup.assert_not_called()
    post.assert_not_called()
