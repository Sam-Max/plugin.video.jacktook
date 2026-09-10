import json
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest

from lib.api.nuvio import NuvioClient, is_nuvio_progress_sync_enabled
from lib.utils.general.items_menus import nuvio_menu_items, root_menu_items


def _client():
    return NuvioClient(access_token="access", refresh_token="refresh", expires_at="", profile_id=2)


def _response(status_code, payload=None):
    response = MagicMock(status_code=status_code)
    response.json.return_value = payload
    return response


def test_tmdb_id_from_content_id_is_tolerant():
    parse = NuvioClient._tmdb_id_from_content_id
    assert parse("tmdb:550") == 550
    assert parse("tmdb: 550 ") == 550
    assert parse("TMDB:550") == 550
    assert parse(" imdb:tt550 ") is None
    assert parse("tmdb:abc") is None
    assert parse("tmdb:") is None
    assert parse("tmdb:0") is None
    assert parse("tmdb:-5") is None
    assert parse("no-colon") is None
    assert parse(None) is None
    assert parse(550) is None


def test_get_watch_progress_returns_empty_list_without_profile():
    assert NuvioClient(access_token="access", profile_id=None).get_watch_progress() == []


def test_get_watched_history_returns_empty_list_without_profile():
    assert NuvioClient(access_token="access", profile_id=None).get_watched_history() == []


def test_get_watch_progress_normalizes_and_filters_api_entries(monkeypatch):
    post = MagicMock(
        return_value=_response(
            200,
            [
                {
                    "content_id": "tmdb:550",
                    "content_type": "movie",
                    "video_id": "tmdb:550",
                    "season": None,
                    "episode": None,
                    "progress_key": "k1",
                    "position": 120000,
                    "duration": 720000,
                    "last_watched": 1711600000000,
                },
                {
                    "content_id": "tmdb:1396",
                    "content_type": "series",
                    "video_id": "tmdb:1396:1:1",
                    "season": 1,
                    "episode": 1,
                    "progress_key": "k2",
                    "position": 900000,
                    "duration": 2700000,
                    "last_watched": 1711600001000,
                },
                {
                    "content_id": "not-tmdb:1",
                    "content_type": "movie",
                    "position": 1,
                    "duration": 100,
                    "last_watched": 5,
                },
                {
                    "content_id": "tmdb:0",
                    "content_type": "movie",
                    "position": 1,
                    "duration": 100,
                    "last_watched": 5,
                },
                {
                    "content_id": "tmdb:2",
                    "content_type": "movie",
                    "position": 0,
                    "duration": 0,
                    "last_watched": 5,
                },
                {
                    "content_id": "tmdb:3",
                    "content_type": "movie",
                    "position": 10,
                    "duration": 100,
                    "last_watched": None,
                },
                {
                    "content_id": "tmdb:4",
                    "content_type": "series",
                    "season": None,
                    "episode": None,
                    "position": 10,
                    "duration": 100,
                    "last_watched": 5,
                },
            ],
        )
    )
    monkeypatch.setattr("lib.api.nuvio.requests.post", post)

    items = _client().get_watch_progress()

    assert items == [
        {
            "tmdb_id": 550,
            "mode": "movies",
            "season": None,
            "episode": None,
            "position_ms": 120000,
            "duration_ms": 720000,
            "percent": 16.67,
            "last_watched_ms": 1711600000000,
            "progress_key": "k1",
        },
        {
            "tmdb_id": 1396,
            "mode": "tv",
            "season": 1,
            "episode": 1,
            "position_ms": 900000,
            "duration_ms": 2700000,
            "percent": 33.33,
            "last_watched_ms": 1711600001000,
            "progress_key": "k2",
        },
    ]
    assert post.call_args.args[0].endswith("/rest/v1/rpc/sync_pull_watch_progress")
    assert post.call_args.kwargs["json"] == {
        "p_profile_id": 2,
        "p_since_last_watched": None,
        "p_limit": 200,
    }


def test_get_watch_progress_caps_percent_at_100(monkeypatch):
    post = MagicMock(
        return_value=_response(
            200,
            [
                {
                    "content_id": "tmdb:550",
                    "content_type": "movie",
                    "progress_key": "k1",
                    "position": 800000,
                    "duration": 720000,
                    "last_watched": 1711600000000,
                },
            ],
        )
    )
    monkeypatch.setattr("lib.api.nuvio.requests.post", post)

    items = _client().get_watch_progress()

    assert items[0]["percent"] == 100.0


def test_get_watch_progress_filters_entries_without_progress_key(monkeypatch):
    post = MagicMock(
        return_value=_response(
            200,
            [
                {
                    "content_id": "tmdb:550",
                    "content_type": "movie",
                    "position": 100,
                    "duration": 1000,
                    "last_watched": 1711600000000,
                },
                {
                    "content_id": "tmdb:1396",
                    "content_type": "series",
                    "season": 1,
                    "episode": 1,
                    "progress_key": "  ",
                    "position": 100,
                    "duration": 1000,
                    "last_watched": 1711600000000,
                },
                {
                    "content_id": "tmdb:603",
                    "content_type": "movie",
                    "progress_key": "k3",
                    "position": 100,
                    "duration": 1000,
                    "last_watched": 1711600000000,
                },
            ],
        )
    )
    monkeypatch.setattr("lib.api.nuvio.requests.post", post)

    items = _client().get_watch_progress()

    assert [item["progress_key"] for item in items] == ["k3"]


def test_delete_watch_progress_returns_true_on_no_content(monkeypatch):
    post = MagicMock(return_value=_response(204))
    monkeypatch.setattr("lib.api.nuvio.requests.post", post)

    assert _client().delete_watch_progress("tmdb:550") is True

    assert post.call_args.args[0].endswith("/rest/v1/rpc/sync_delete_watch_progress")
    assert post.call_args.kwargs["json"] == {"p_progress_key": "tmdb:550", "p_profile_id": 2}


def test_delete_watch_progress_returns_false_on_http_error(monkeypatch):
    log = MagicMock()
    monkeypatch.setattr("lib.api.nuvio.kodilog", log)
    post = MagicMock(return_value=_response(400))
    monkeypatch.setattr("lib.api.nuvio.requests.post", post)

    assert _client().delete_watch_progress("tmdb:550") is False

    assert "watch-progress delete rejected (HTTP 400)" in " ".join(
        str(c) for c in log.call_args_list
    )


def test_delete_watch_progress_returns_false_without_profile():
    assert (
        NuvioClient(access_token="access", profile_id=None).delete_watch_progress("tmdb:550")
        is False
    )


def test_delete_watch_progress_rejects_blank_progress_key(monkeypatch):
    post = MagicMock()
    monkeypatch.setattr("lib.api.nuvio.requests.post", post)

    assert _client().delete_watch_progress("  ") is False
    assert _client().delete_watch_progress(None) is False
    post.assert_not_called()


def test_get_watched_history_normalizes_and_filters_api_entries(monkeypatch):
    post = MagicMock(
        return_value=_response(
            200,
            [
                {
                    "content_id": "tmdb:550",
                    "content_type": "movie",
                    "title": "Fight Club",
                    "season": None,
                    "episode": None,
                    "watched_at": 1711600000000,
                },
                {
                    "content_id": "tmdb:1396",
                    "content_type": "series",
                    "title": "Breaking Bad",
                    "season": 2,
                    "episode": 5,
                    "watched_at": 1711600001000,
                },
                {
                    "content_id": "junk:1",
                    "content_type": "movie",
                    "title": "Ignored",
                    "watched_at": 1711600002000,
                },
                {
                    "content_id": "tmdb:7",
                    "content_type": "series",
                    "title": "Missing Episode",
                    "season": 1,
                    "watched_at": 1711600003000,
                },
                {
                    "content_id": "tmdb:8",
                    "content_type": "movie",
                    "title": "No Timestamp",
                    "watched_at": None,
                },
            ],
        )
    )
    monkeypatch.setattr("lib.api.nuvio.requests.post", post)

    items = _client().get_watched_history(page=2, page_size=100)

    assert items == [
        {
            "tmdb_id": 550,
            "mode": "movies",
            "season": None,
            "episode": None,
            "title": "Fight Club",
            "watched_at_ms": 1711600000000,
        },
        {
            "tmdb_id": 1396,
            "mode": "tv",
            "season": 2,
            "episode": 5,
            "title": "Breaking Bad",
            "watched_at_ms": 1711600001000,
        },
    ]
    assert post.call_args.args[0].endswith("/rest/v1/rpc/sync_pull_watched_items")
    assert post.call_args.kwargs["json"] == {
        "p_profile_id": 2,
        "p_page": 2,
        "p_page_size": 100,
    }


def test_watch_pull_failures_log_failure_category_and_return_empty_list(monkeypatch):
    log = MagicMock()
    monkeypatch.setattr("lib.api.nuvio.kodilog", log)
    post = MagicMock(return_value=_response(401))
    monkeypatch.setattr("lib.api.nuvio.requests.post", post)
    client = _client()

    assert client.get_watch_progress() == []
    assert client.get_watched_history() == []

    logged = " ".join(str(call) for call in log.call_args_list)
    assert "watch-progress pull failed" in logged
    assert "watched-history pull failed" in logged


def test_watch_pull_invalid_json_and_non_list_return_empty(monkeypatch):
    invalid_json = _response(200)
    invalid_json.json.side_effect = ValueError("no json")
    non_list = _response(200, {"unexpected": "shape"})
    client = _client()

    monkeypatch.setattr("lib.api.nuvio.requests.post", MagicMock(return_value=invalid_json))
    assert client.get_watch_progress() == []
    assert client.get_watched_history() == []

    monkeypatch.setattr("lib.api.nuvio.requests.post", MagicMock(return_value=non_list))
    assert client.get_watch_progress() == []
    assert client.get_watched_history() == []


# ---------------------------------------------------------------------------
# Menu conditions
# ---------------------------------------------------------------------------


def test_nuvio_root_menu_entries_are_visible_only_when_sync_is_enabled(monkeypatch):
    root_entries = [item for item in root_menu_items if item["action"] == "nuvio_menu"]
    assert len(root_entries) == 1
    nuvio_root = root_entries[0]
    assert nuvio_root["condition"] is is_nuvio_progress_sync_enabled

    monkeypatch.setattr("lib.api.nuvio.get_setting", {}.get)
    assert nuvio_root["condition"]() is False

    enabled = {
        "nuvio_enabled": "true",
        "nuvio_authenticated": "true",
        "nuvio_access_token": "access",
        "nuvio_profile_id": "2",
    }
    monkeypatch.setattr("lib.api.nuvio.get_setting", enabled.get)
    assert nuvio_root["condition"]() is True

    assert [(item["action"], item.get("params")) for item in nuvio_menu_items] == [
        ("nuvio_continue_watching", None),
        ("nuvio_history", None),
        ("nuvio_library", {"mode": "movies"}),
        ("nuvio_library", {"mode": "tv"}),
        ("nuvio_collections", None),
    ]
    assert all(callable(item["condition"]) for item in nuvio_menu_items)

    monkeypatch.setattr("lib.api.nuvio.get_setting", {}.get)
    assert nuvio_menu_items[0]["condition"]() is False
    assert nuvio_menu_items[1]["condition"]() is False

    monkeypatch.setattr("lib.api.nuvio.get_setting", enabled.get)
    assert nuvio_menu_items[0]["condition"]() is True
    assert nuvio_menu_items[1]["condition"]() is True


# ---------------------------------------------------------------------------
# Continue Watching view
# ---------------------------------------------------------------------------


def _patch_view_shell(monkeypatch, view):
    item = MagicMock()
    monkeypatch.setattr(view, "make_list_item", MagicMock(return_value=item))
    add_items = MagicMock()
    monkeypatch.setattr(view, "add_directory_items_batch", add_items)
    monkeypatch.setattr(view, "setContent", MagicMock())
    monkeypatch.setattr(view, "end_of_directory", MagicMock())
    monkeypatch.setattr(view, "apply_section_view", MagicMock())
    monkeypatch.setattr(view, "set_pluging_category", MagicMock())
    monkeypatch.setattr(view, "notification", MagicMock())
    monkeypatch.setattr(view, "translation", lambda string_id: f"text-{string_id}")
    return item, add_items


def _stub_nuvio_client(monkeypatch, view, method_name, items):
    class _StubNuvioClient:
        def __init__(self):
            pass

        def __getattr__(self, name):
            if name == method_name:
                return lambda: items
            raise AttributeError(name)

    monkeypatch.setattr(view, "NuvioClient", _StubNuvioClient)


def test_show_nuvio_continue_watching_builds_search_actions(monkeypatch):
    from lib.utils.views import nuvio_continue_watching as view

    item, add_items = _patch_view_shell(monkeypatch, view)
    set_media_info_tag = MagicMock()
    tmdb_get = MagicMock(
        side_effect=lambda path, tmdb_id: (
            {"title": "Fight Club"} if path == "movie_details" else {"name": "Breaking Bad"}
        )
    )
    monkeypatch.setattr(view, "tmdb_get", tmdb_get)
    monkeypatch.setattr(view, "set_media_infoTag", set_media_info_tag)
    monkeypatch.setattr(
        view,
        "NuvioClient",
        MagicMock(
            return_value=MagicMock(
                get_watch_progress=MagicMock(
                    return_value=[
                        {
                            "tmdb_id": 550,
                            "mode": "movies",
                            "season": None,
                            "episode": None,
                            "position_ms": 120000,
                            "duration_ms": 720000,
                            "percent": 16.67,
                            "last_watched_ms": 1711600000000,
                            "progress_key": "k1",
                        },
                        {
                            "tmdb_id": 1396,
                            "mode": "tv",
                            "season": 1,
                            "episode": 2,
                            "position_ms": 900000,
                            "duration_ms": 2700000,
                            "percent": 33.33,
                            "last_watched_ms": 1711600001000,
                            "progress_key": "k2",
                        },
                    ]
                )
            )
        ),
    )

    view.show_nuvio_continue_watching()

    directory_items = add_items.call_args.args[0]
    assert len(directory_items) == 2

    movie_url, _movie_item, movie_is_folder = directory_items[0]
    assert "action=nuvio_resume" in movie_url
    assert "mode=movies" in movie_url
    assert "tmdb_id" in movie_url
    assert "nuvio_resume_percent" in movie_url
    assert movie_is_folder is False

    tv_url, _tv_item, tv_is_folder = directory_items[1]
    assert "action=nuvio_resume" in tv_url
    assert "mode=tv" in tv_url
    assert "season" in tv_url
    assert tv_is_folder is False

    assert view.make_list_item.call_args_list[0].kwargs["label"] == "Fight Club"
    assert view.make_list_item.call_args_list[1].kwargs["label"] == "Breaking Bad S01E02"
    tmdb_get.assert_any_call("movie_details", 550)
    tmdb_get.assert_any_call("tv_details", 1396)
    set_media_info_tag.assert_any_call(item, data={"title": "Fight Club"}, mode="movies")
    set_media_info_tag.assert_any_call(item, data={"name": "Breaking Bad"}, mode="tv")
    info_tag = item.getVideoInfoTag()
    resume_call = info_tag.setResumePoint.call_args_list[0]
    assert resume_call.args[1] == 1
    assert resume_call.args[0] == pytest.approx(0.1667)
    item.setProperty.assert_any_call("PercentPlayed", "16.67")
    item.setProperty.assert_any_call("IsPlayable", "true")
    context_menu = item.addContextMenuItems.call_args_list[0].args[0]
    assert context_menu[0][0] == "text-91027"
    assert context_menu[0][1] == (
        f"RunPlugin({view.build_url('nuvio_remove_progress', progress_key='k1')})"
    )
    assert item.addContextMenuItems.call_count == 2
    assert item.addContextMenuItems.call_args_list[1].args[0][0][1] == (
        f"RunPlugin({view.build_url('nuvio_remove_progress', progress_key='k2')})"
    )
    view.notification.assert_not_called()


def test_show_nuvio_continue_watching_falls_back_when_tmdb_fails(monkeypatch):
    from lib.utils.views import nuvio_continue_watching as view

    item, add_items = _patch_view_shell(monkeypatch, view)
    set_media_info_tag = MagicMock()
    monkeypatch.setattr(view, "tmdb_get", MagicMock(side_effect=RuntimeError("offline")))
    monkeypatch.setattr(view, "set_media_infoTag", set_media_info_tag)
    monkeypatch.setattr(
        view,
        "NuvioClient",
        MagicMock(
            return_value=MagicMock(
                get_watch_progress=MagicMock(
                    return_value=[
                        {
                            "tmdb_id": 550,
                            "mode": "movies",
                            "season": None,
                            "episode": None,
                            "position_ms": 120000,
                            "duration_ms": 720000,
                            "percent": 16.67,
                            "last_watched_ms": 1711600000000,
                            "progress_key": "k1",
                        }
                    ]
                )
            )
        ),
    )

    view.show_nuvio_continue_watching()

    url, list_item, is_folder = add_items.call_args.args[0][0]
    assert "action=nuvio_resume" in url
    assert is_folder is False
    assert view.make_list_item.call_args.kwargs["label"] == "TMDB 550"
    assert list_item is item
    assert item.setArt.call_args.args[0] == {
        "icon": view.os.path.join(view.ADDON_PATH, "resources", "img", "magnet.png")
    }
    set_media_info_tag.assert_not_called()
    item.setProperty.assert_any_call("IsPlayable", "true")


def test_show_nuvio_continue_watching_notifies_when_empty(monkeypatch):
    from lib.utils.views import nuvio_continue_watching as view

    _item, add_items = _patch_view_shell(monkeypatch, view)
    monkeypatch.setattr(
        view,
        "NuvioClient",
        MagicMock(return_value=MagicMock(get_watch_progress=MagicMock(return_value=[]))),
    )

    view.show_nuvio_continue_watching()

    assert add_items.call_args.args[0] == []
    view.notification.assert_called_once_with("text-91025", time=3000)


# ---------------------------------------------------------------------------
# History view
# ---------------------------------------------------------------------------


def test_show_nuvio_history_plays_items_directly(monkeypatch):
    from lib.utils.views import nuvio_history as view

    item, add_items = _patch_view_shell(monkeypatch, view)
    set_media_info_tag = MagicMock()
    tmdb_get = MagicMock(
        side_effect=lambda path, tmdb_id: (
            {"title": "Fight Club"} if path == "movie_details" else {"name": "Breaking Bad"}
        )
    )
    monkeypatch.setattr(view, "tmdb_get", tmdb_get)
    monkeypatch.setattr(view, "set_media_infoTag", set_media_info_tag)
    monkeypatch.setattr(
        view,
        "NuvioClient",
        MagicMock(
            return_value=MagicMock(
                get_watched_history=MagicMock(
                    return_value=[
                        {
                            "tmdb_id": 550,
                            "mode": "movies",
                            "season": None,
                            "episode": None,
                            "title": "Fight Club",
                            "watched_at_ms": 1711600000000,
                        },
                        {
                            "tmdb_id": 1396,
                            "mode": "tv",
                            "season": 2,
                            "episode": 5,
                            "title": "Breaking Bad",
                            "watched_at_ms": 1711600001000,
                        },
                    ]
                )
            )
        ),
    )

    view.show_nuvio_history()

    directory_items = add_items.call_args.args[0]
    assert len(directory_items) == 2

    movie_url, _movie_item, movie_is_folder = directory_items[0]
    assert "action=nuvio_resume" in movie_url
    assert "mode=movies" in movie_url
    assert movie_is_folder is False
    movie_params = parse_qs(urlparse(movie_url).query)
    assert movie_params["ids"] == [json.dumps({"tmdb_id": "550"})]
    assert "tv_data" not in movie_params

    tv_url, _tv_item, tv_is_folder = directory_items[1]
    assert "action=nuvio_resume" in tv_url
    assert "mode=tv" in tv_url
    assert tv_is_folder is False
    tv_params = parse_qs(urlparse(tv_url).query)
    assert tv_params["ids"] == [json.dumps({"tmdb_id": "1396"})]
    assert json.loads(tv_params["tv_data"][0]) == {
        "season": 2,
        "episode": 5,
        "name": "Breaking Bad S02E05",
    }

    assert view.make_list_item.call_args_list[0].kwargs["label"] == "Fight Club"
    assert view.make_list_item.call_args_list[1].kwargs["label"] == "Breaking Bad S02E05"
    set_media_info_tag.assert_any_call(item, data={"title": "Fight Club"}, mode="movies")
    set_media_info_tag.assert_any_call(item, data={"name": "Breaking Bad"}, mode="tv")
    item.setProperty.assert_any_call("IsPlayable", "true")
    view.notification.assert_not_called()


def test_show_nuvio_history_falls_back_when_tmdb_fails(monkeypatch):
    from lib.utils.views import nuvio_history as view

    item, add_items = _patch_view_shell(monkeypatch, view)
    set_media_info_tag = MagicMock()
    monkeypatch.setattr(view, "tmdb_get", MagicMock(side_effect=RuntimeError("offline")))
    monkeypatch.setattr(view, "set_media_infoTag", set_media_info_tag)
    monkeypatch.setattr(
        view,
        "NuvioClient",
        MagicMock(
            return_value=MagicMock(
                get_watched_history=MagicMock(
                    return_value=[
                        {
                            "tmdb_id": 1396,
                            "mode": "tv",
                            "season": 2,
                            "episode": 5,
                            "title": "",
                            "watched_at_ms": 1711600001000,
                        }
                    ]
                )
            )
        ),
    )

    view.show_nuvio_history()

    url, _list_item, is_folder = add_items.call_args.args[0][0]
    assert "action=nuvio_resume" in url
    assert is_folder is False
    assert view.make_list_item.call_args.kwargs["label"] == "S02E05"
    assert item.setArt.call_args.args[0] == {
        "icon": view.os.path.join(view.ADDON_PATH, "resources", "img", "magnet.png")
    }
    set_media_info_tag.assert_not_called()


def test_show_nuvio_history_falls_back_to_tmdb_title_when_missing(monkeypatch):
    from lib.utils.views import nuvio_history as view

    _item, _add_items = _patch_view_shell(monkeypatch, view)
    monkeypatch.setattr(view, "tmdb_get", MagicMock(return_value={"title": "Fight Club"}))
    monkeypatch.setattr(view, "set_media_infoTag", MagicMock())
    monkeypatch.setattr(
        view,
        "NuvioClient",
        MagicMock(
            return_value=MagicMock(
                get_watched_history=MagicMock(
                    return_value=[
                        {
                            "tmdb_id": 550,
                            "mode": "movies",
                            "season": None,
                            "episode": None,
                            "title": "",
                            "watched_at_ms": 1711600000000,
                        }
                    ]
                )
            )
        ),
    )

    view.show_nuvio_history()

    assert view.make_list_item.call_args.kwargs["label"] == "Fight Club"


def test_show_nuvio_history_titleless_episode_keeps_show_name(monkeypatch):
    """A series entry with no stored title must still show the show name:
    falling back to TMDB before composing the label, not a bare "S03E02"."""
    from lib.utils.views import nuvio_history as view

    _item, add_items = _patch_view_shell(monkeypatch, view)
    monkeypatch.setattr(view, "tmdb_get", MagicMock(return_value={"name": "Silo"}))
    monkeypatch.setattr(view, "set_media_infoTag", MagicMock())
    monkeypatch.setattr(
        view,
        "NuvioClient",
        MagicMock(
            return_value=MagicMock(
                get_watched_history=MagicMock(
                    return_value=[
                        {
                            "tmdb_id": 125988,
                            "mode": "tv",
                            "season": 3,
                            "episode": 2,
                            "title": "",
                            "watched_at_ms": 1711600001000,
                        }
                    ]
                )
            )
        ),
    )

    view.show_nuvio_history()

    url, _list_item, is_folder = add_items.call_args.args[0][0]
    assert view.make_list_item.call_args.kwargs["label"] == "Silo S03E02"
    assert is_folder is False
    params = parse_qs(urlparse(url).query)
    assert params["query"] == ["Silo S03E02"]
    assert json.loads(params["tv_data"][0]) == {
        "season": 3,
        "episode": 2,
        "name": "Silo S03E02",
    }


def test_show_nuvio_history_notifies_when_empty(monkeypatch):
    from lib.utils.views import nuvio_history as view

    _item, add_items = _patch_view_shell(monkeypatch, view)
    monkeypatch.setattr(
        view,
        "NuvioClient",
        MagicMock(return_value=MagicMock(get_watched_history=MagicMock(return_value=[]))),
    )

    view.show_nuvio_history()

    assert add_items.call_args.args[0] == []
    view.notification.assert_called_once_with("text-91026", time=3000)


def test_nuvio_history_play_url_reaches_direct_search(monkeypatch):
    """A history row must reach run_search_entry with resolved imdb/tvdb ids
    and a forced rescrape, exactly like a Continue Watching row does."""
    from lib import navigation
    from lib.utils.views import nuvio_history as view

    _item, add_items = _patch_view_shell(monkeypatch, view)
    monkeypatch.setattr(view, "tmdb_get", MagicMock(return_value={"name": "Breaking Bad"}))
    monkeypatch.setattr(view, "set_media_infoTag", MagicMock())
    monkeypatch.setattr(
        view,
        "NuvioClient",
        MagicMock(
            return_value=MagicMock(
                get_watched_history=MagicMock(
                    return_value=[
                        {
                            "tmdb_id": 1396,
                            "mode": "tv",
                            "season": 2,
                            "episode": 5,
                            "title": "Breaking Bad",
                            "watched_at_ms": 1711600001000,
                        }
                    ]
                )
            )
        ),
    )

    view.show_nuvio_history()
    url, _list_item, _is_folder = add_items.call_args.args[0][0]

    # Replay the exact plugin URL the way Kodi would dispatch it.
    params = {key: values[0] for key, values in parse_qs(urlparse(url).query).items()}

    run_search_entry = MagicMock()
    tmdb_metadata = MagicMock(
        return_value={"external_ids": {"imdb_id": "tt0903747", "tvdb_id": 81189}}
    )
    monkeypatch.setattr("lib.search.run_search_entry", run_search_entry)
    monkeypatch.setattr(navigation.TmdbClient, "_get_tmdb_metadata", tmdb_metadata)

    navigation.nuvio_resume(params)

    tmdb_metadata.assert_called_once_with("tv", "tv", "1396")
    search_params = run_search_entry.call_args.args[0]
    assert search_params["rescrape"] is True
    assert search_params["mode"] == "tv"
    assert json.loads(search_params["ids"]) == {
        "tmdb_id": "1396",
        "imdb_id": "tt0903747",
        "tvdb_id": 81189,
    }
    assert json.loads(search_params["tv_data"]) == {
        "season": 2,
        "episode": 5,
        "name": "Breaking Bad S02E05",
    }
    assert "nuvio_resume_percent" not in search_params


# ---------------------------------------------------------------------------
# Navigation: nuvio_remove_progress
# ---------------------------------------------------------------------------


def test_nuvio_remove_progress_refreshes_container_on_success(monkeypatch):
    import lib.navigation as navigation

    client = MagicMock(delete_watch_progress=MagicMock(return_value=True))
    monkeypatch.setattr("lib.api.nuvio.NuvioClient", MagicMock(return_value=client))
    notification = MagicMock()
    execute_builtin = MagicMock()
    monkeypatch.setattr(navigation, "notification", notification)
    monkeypatch.setattr(navigation, "execute_builtin", execute_builtin)
    monkeypatch.setattr(navigation, "translation", lambda string_id: f"text-{string_id}")

    navigation.nuvio_remove_progress({"progress_key": "tmdb:550"})

    client.delete_watch_progress.assert_called_once_with("tmdb:550")
    notification.assert_called_once_with("text-91028", time=3000)
    execute_builtin.assert_called_once_with("Container.Refresh")


def test_nuvio_remove_progress_notifies_without_refresh_on_failure(monkeypatch):
    import lib.navigation as navigation

    client = MagicMock(delete_watch_progress=MagicMock(return_value=False))
    monkeypatch.setattr("lib.api.nuvio.NuvioClient", MagicMock(return_value=client))
    notification = MagicMock()
    execute_builtin = MagicMock()
    monkeypatch.setattr(navigation, "notification", notification)
    monkeypatch.setattr(navigation, "execute_builtin", execute_builtin)
    monkeypatch.setattr(navigation, "translation", lambda string_id: f"text-{string_id}")

    navigation.nuvio_remove_progress({"progress_key": "tmdb:550"})

    client.delete_watch_progress.assert_called_once_with("tmdb:550")
    notification.assert_called_once_with("text-91029", time=3000)
    execute_builtin.assert_not_called()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action",
    [
        "nuvio_continue_watching",
        "nuvio_history",
        "nuvio_library",
        "nuvio_remove_progress",
        "nuvio_update_history",
    ],
)
def test_get_route_handler_returns_nuvio_dispatcher_for_watch_actions(action):
    import importlib
    import sys

    if "lib.router" in sys.modules:
        router = importlib.reload(sys.modules["lib.router"])
    else:
        router = importlib.import_module("lib.router")

    assert router._get_route_handler(action) is router._route_nuvio


@pytest.mark.parametrize(
    "action",
    [
        "nuvio_continue_watching",
        "nuvio_history",
        "nuvio_library",
        "nuvio_remove_progress",
        "nuvio_update_history",
    ],
)
def test_route_nuvio_dispatches_watch_actions(action):
    import importlib
    import sys
    from unittest.mock import patch

    if "lib.router" in sys.modules:
        router = importlib.reload(sys.modules["lib.router"])
    else:
        router = importlib.import_module("lib.router")

    params = {"query": "Movie"}
    with patch(f"lib.navigation.{action}") as handler:
        router._route_nuvio(action, params)

    handler.assert_called_once_with(params)


# ---------------------------------------------------------------------------
# Library view (offline, database-only)
# ---------------------------------------------------------------------------


class _FakeNuvioStore:
    """In-memory NuvioStore double keyed by profile_id."""

    def __init__(self, rows_by_profile=None):
        self._rows = rows_by_profile or {}
        self.calls = []
        self.closed = False

    def list_items(self, profile_id, content_type):
        self.calls.append((profile_id, content_type))
        return [
            row for row in self._rows.get(profile_id, []) if row.get("content_type") == content_type
        ]

    def count(self, profile_id):
        return len(self._rows.get(profile_id, []))

    def close(self):
        self.closed = True


def _movie_row(tmdb_id=550, title="Fight Club"):
    return {
        "content_type": "movie",
        "content_id": f"tmdb:{tmdb_id}",
        "tmdb_id": tmdb_id,
        "title": title,
        "poster": "poster.jpg",
        "background": "fanart.jpg",
        "description": "A movie description",
        "release_info": "1999",
        "genres": ["Drama"],
    }


def _series_row(tmdb_id=1396, title="Breaking Bad"):
    return {
        "content_type": "series",
        "content_id": f"tmdb:{tmdb_id}",
        "tmdb_id": tmdb_id,
        "title": title,
        "poster": "poster.jpg",
        "background": "fanart.jpg",
        "description": "A series description",
        "genres": ["Drama"],
    }


def _no_construct_client():
    class _NoConstructNuvioClient(NuvioClient):
        def __init__(self, *args, **kwargs):
            raise AssertionError("NuvioClient must not be constructed by the library view")

    return _NoConstructNuvioClient


def _settings(values):
    return lambda key, default=None: values.get(key, default)


def _patch_library_settings(monkeypatch, view, profile_id="2"):
    monkeypatch.setattr(view, "NuvioClient", _no_construct_client())
    monkeypatch.setattr(view, "get_setting", _settings({"nuvio_profile_id": profile_id}))
    monkeypatch.setattr(view, "sync_library_if_stale", MagicMock())


def test_has_nuvio_library_items_false_when_disabled(monkeypatch):
    from lib.utils.views import nuvio_library as view

    monkeypatch.setattr(view, "is_nuvio_progress_sync_enabled", lambda: False)
    nuvio_store = MagicMock(return_value=_FakeNuvioStore({2: [_movie_row()]}))
    monkeypatch.setattr(view, "NuvioStore", nuvio_store)

    assert view.has_nuvio_library_items() is False
    nuvio_store.assert_not_called()


def test_has_nuvio_library_items_false_when_mirror_empty(monkeypatch):
    from lib.utils.views import nuvio_library as view

    monkeypatch.setattr(view, "is_nuvio_progress_sync_enabled", lambda: True)
    _patch_library_settings(monkeypatch, view)
    store = _FakeNuvioStore({2: []})
    monkeypatch.setattr(view, "NuvioStore", MagicMock(return_value=store))

    assert view.has_nuvio_library_items() is False
    assert store.closed is True


def test_has_nuvio_library_items_true_when_populated(monkeypatch):
    from lib.utils.views import nuvio_library as view

    monkeypatch.setattr(view, "is_nuvio_progress_sync_enabled", lambda: True)
    _patch_library_settings(monkeypatch, view)
    store = _FakeNuvioStore({2: [_movie_row(), _series_row()]})
    monkeypatch.setattr(view, "NuvioStore", MagicMock(return_value=store))

    assert view.has_nuvio_library_items() is True
    assert store.closed is True


def test_library_view_never_constructs_nuvio_client(monkeypatch):
    from lib.utils.views import nuvio_library as view

    monkeypatch.setattr(view, "NuvioClient", _no_construct_client())

    with pytest.raises(AssertionError):
        view.NuvioClient()


def test_show_nuvio_library_builds_movie_search_without_network(monkeypatch):
    from lib.utils.views import nuvio_library as view

    _item, add_items = _patch_view_shell(monkeypatch, view)
    store = _FakeNuvioStore({2: [_movie_row()]})
    monkeypatch.setattr(view, "NuvioStore", MagicMock(return_value=store))
    set_media_info_tag = MagicMock()
    monkeypatch.setattr(view, "set_media_infoTag", set_media_info_tag)
    _patch_library_settings(monkeypatch, view)

    view.show_nuvio_library({"mode": "movies"})

    assert store.calls == [(2, "movie")]
    directory_items = add_items.call_args.args[0]
    assert len(directory_items) == 1
    url, _list_item, is_folder = directory_items[0]
    assert "action=search" in url
    assert "mode=movies" in url
    assert "tmdb_id" in url
    assert is_folder is False

    view.apply_section_view.assert_called_once_with("view.library", content_type="movies")
    kwargs = set_media_info_tag.call_args.kwargs
    assert kwargs["mode"] == "movies"
    assert kwargs["data"]["title"] == "Fight Club"
    assert kwargs["data"]["poster"] == "poster.jpg"
    assert kwargs["data"]["fanart"] == "fanart.jpg"
    assert kwargs["data"]["id"] == 550
    view.notification.assert_not_called()


def test_show_nuvio_library_builds_series_season_details(monkeypatch):
    from lib.utils.views import nuvio_library as view

    _item, add_items = _patch_view_shell(monkeypatch, view)
    store = _FakeNuvioStore({2: [_series_row()]})
    monkeypatch.setattr(view, "NuvioStore", MagicMock(return_value=store))
    set_media_info_tag = MagicMock()
    monkeypatch.setattr(view, "set_media_infoTag", set_media_info_tag)
    _patch_library_settings(monkeypatch, view)

    view.show_nuvio_library({"mode": "tv"})

    assert store.calls == [(2, "series")]
    directory_items = add_items.call_args.args[0]
    assert len(directory_items) == 1
    url, _list_item, is_folder = directory_items[0]
    assert "action=show_seasons_details" in url
    assert "mode=tv" in url
    assert "tmdb_id" in url
    assert is_folder is True
    view.apply_section_view.assert_called_once_with("view.library", content_type="tvshows")
    assert set_media_info_tag.call_args.kwargs["mode"] == "tv"


def test_show_nuvio_library_syncs_before_reading_the_mirror(monkeypatch):
    from lib.utils.views import nuvio_library as view

    events = []

    class _OrderedStore(_FakeNuvioStore):
        def list_items(self, profile_id, content_type):
            events.append("read")
            return super().list_items(profile_id, content_type)

    _item, _add_items = _patch_view_shell(monkeypatch, view)
    store = _OrderedStore({2: [_movie_row()]})
    monkeypatch.setattr(view, "NuvioStore", MagicMock(return_value=store))
    monkeypatch.setattr(view, "set_media_infoTag", MagicMock())
    _patch_library_settings(monkeypatch, view)
    monkeypatch.setattr(view, "sync_library_if_stale", lambda: events.append("sync"))

    view.show_nuvio_library({"mode": "movies"})

    assert events == ["sync", "read"]


def test_show_nuvio_library_is_profile_scoped(monkeypatch):
    from lib.utils.views import nuvio_library as view

    _item, add_items = _patch_view_shell(monkeypatch, view)
    store = _FakeNuvioStore({1: [_movie_row()], 2: [_series_row()]})
    monkeypatch.setattr(view, "NuvioStore", MagicMock(return_value=store))
    monkeypatch.setattr(view, "set_media_infoTag", MagicMock())
    _patch_library_settings(monkeypatch, view, profile_id="2")

    view.show_nuvio_library({"mode": "movies"})

    assert store.calls == [(2, "movie")]
    assert add_items.call_args.args[0] == []
    view.notification.assert_called_once_with("text-91034")


def test_show_nuvio_library_notifies_when_empty(monkeypatch):
    from lib.utils.views import nuvio_library as view

    _item, add_items = _patch_view_shell(monkeypatch, view)
    store = _FakeNuvioStore({2: []})
    monkeypatch.setattr(view, "NuvioStore", MagicMock(return_value=store))
    monkeypatch.setattr(view, "set_media_infoTag", MagicMock())
    _patch_library_settings(monkeypatch, view)

    view.show_nuvio_library({"mode": "movies"})

    assert add_items.call_args.args[0] == []
    view.notification.assert_called_once_with("text-91034")


def test_nuvio_library_menu_entries_are_condition_gated(monkeypatch):
    library_entries = [item for item in nuvio_menu_items if item["action"] == "nuvio_library"]

    assert len(library_entries) == 2
    assert {entry["params"]["mode"] for entry in library_entries} == {"movies", "tv"}

    monkeypatch.setattr(
        "lib.utils.views.nuvio_library.is_nuvio_progress_sync_enabled", lambda: False
    )
    assert all(entry["condition"]() is False for entry in library_entries)

    monkeypatch.setattr(
        "lib.utils.views.nuvio_library.is_nuvio_progress_sync_enabled", lambda: True
    )
    monkeypatch.setattr("lib.utils.views.nuvio_library.NuvioClient", _no_construct_client())
    monkeypatch.setattr(
        "lib.utils.views.nuvio_library.get_setting", _settings({"nuvio_profile_id": "2"})
    )
    store = _FakeNuvioStore({2: [_movie_row()]})
    monkeypatch.setattr("lib.utils.views.nuvio_library.NuvioStore", MagicMock(return_value=store))

    assert all(entry["condition"]() is True for entry in library_entries)


# ---------------------------------------------------------------------------
# Library view: Remove from Nuvio Library context menu
# ---------------------------------------------------------------------------


def test_show_nuvio_library_adds_remove_context_menu(monkeypatch):
    from lib.utils.views import nuvio_library as view

    item, add_items = _patch_view_shell(monkeypatch, view)
    store = _FakeNuvioStore({2: [_movie_row()]})
    monkeypatch.setattr(view, "NuvioStore", MagicMock(return_value=store))
    monkeypatch.setattr(view, "set_media_infoTag", MagicMock())
    _patch_library_settings(monkeypatch, view)

    view.show_nuvio_library({"mode": "movies"})

    menu = item.addContextMenuItems.call_args.args[0]
    assert menu[0][0] == "text-91040"
    assert menu[0][1] == (
        f"RunPlugin({view.build_url('nuvio_remove_from_library', content_id='tmdb:550', content_type='movie')})"
    )
    assert add_items.call_args.args[0] != []


# ---------------------------------------------------------------------------
# Navigation: nuvio_add_to_library / nuvio_remove_from_library
# ---------------------------------------------------------------------------


class _SyncThread:
    """Thread double that runs the target synchronously on ``start()``."""

    def __init__(self, target=None, args=(), kwargs=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}
        self.daemon = False
        self.started = False

    def start(self):
        self.started = True
        self._target(*self._args, **self._kwargs)


class _FakeWriteStore:
    def __init__(self, *args, **kwargs):
        self.upserted = []
        self.deleted = []
        self.closed = False
        self.setup_called = False

    def setup_nuvio_database(self):
        self.setup_called = True
        return True

    def get_or_create_origin_client_id(self):
        return "origin-1"

    def upsert_items(self, profile_id, items):
        self.upserted.append((profile_id, items))
        return True

    def delete_items(self, profile_id, keys):
        self.deleted.append((profile_id, keys))
        return True

    def close(self):
        self.closed = True


def _patch_write_handler(monkeypatch, navigation, push_result):
    client = MagicMock(profile_id=2)
    client.add_library_items = MagicMock(return_value=push_result)
    client.remove_library_items = MagicMock(return_value=push_result)
    monkeypatch.setattr("lib.api.nuvio.NuvioClient", MagicMock(return_value=client))

    stores = []

    def _store_factory(*args, **kwargs):
        store = _FakeWriteStore()
        stores.append(store)
        return store

    monkeypatch.setattr("lib.api.nuvio_store.NuvioStore", _store_factory)
    invalidate = MagicMock()
    monkeypatch.setattr("lib.api.nuvio_store.invalidate_nuvio_library_cache", invalidate)
    notification = MagicMock()
    execute_builtin = MagicMock()
    monkeypatch.setattr(navigation, "notification", notification)
    monkeypatch.setattr(navigation, "execute_builtin", execute_builtin)
    monkeypatch.setattr(navigation, "translation", lambda string_id: f"text-{string_id}")
    monkeypatch.setattr(navigation, "Thread", _SyncThread)
    monkeypatch.setattr(navigation, "_enrich_nuvio_library_item", lambda item, data: None)
    return client, stores, invalidate, notification, execute_builtin


def _payload():
    return json.dumps(
        {
            "content_id": "tmdb:550",
            "content_type": "movie",
            "title": "Fight Club",
            "ids": {"tmdb_id": 550},
            "mode": "movies",
            "added_at": 1711600000000,
        }
    )


def test_nuvio_add_to_library_pushes_and_updates_mirror(monkeypatch):
    import lib.navigation as navigation

    client, stores, invalidate, notification, execute_builtin = _patch_write_handler(
        monkeypatch, navigation, push_result=True
    )

    navigation.nuvio_add_to_library({"data": _payload()})

    client.add_library_items.assert_called_once()
    kwargs = client.add_library_items.call_args.kwargs
    assert kwargs["profile_id"] == 2
    assert kwargs["origin_client_id"] == "origin-1"
    assert kwargs["items"][0]["content_id"] == "tmdb:550"
    assert kwargs["items"][0]["content_type"] == "movie"
    assert kwargs["items"][0]["name"] == "Fight Club"

    assert len(stores) == 1
    store = stores[0]
    assert store.setup_called is True
    assert len(store.upserted) == 1
    profile_id, mirror_items = store.upserted[0]
    assert profile_id == 2
    assert mirror_items[0]["content_id"] == "tmdb:550"
    assert mirror_items[0]["tmdb_id"] == 550
    assert mirror_items[0]["title"] == "Fight Club"
    assert mirror_items[0]["added_at_ms"] == 1711600000000
    assert store.closed is True

    invalidate.assert_called_once_with()
    execute_builtin.assert_called_once_with("Container.Refresh")
    notification.assert_called_once_with("text-91041", time=3000)


def test_nuvio_add_to_library_notifies_and_leaves_mirror_on_failure(monkeypatch):
    import lib.navigation as navigation

    client, stores, invalidate, notification, execute_builtin = _patch_write_handler(
        monkeypatch, navigation, push_result=False
    )

    navigation.nuvio_add_to_library({"data": _payload()})

    client.add_library_items.assert_called_once()
    assert stores[0].upserted == []
    assert stores[0].closed is True
    invalidate.assert_not_called()
    execute_builtin.assert_not_called()
    notification.assert_called_once_with("text-91043", time=3000)


def test_nuvio_remove_from_library_pushes_and_updates_mirror(monkeypatch):
    import lib.navigation as navigation

    client, stores, invalidate, notification, execute_builtin = _patch_write_handler(
        monkeypatch, navigation, push_result=True
    )

    navigation.nuvio_remove_from_library({"content_id": "tmdb:550", "content_type": "movie"})

    client.remove_library_items.assert_called_once()
    kwargs = client.remove_library_items.call_args.kwargs
    assert kwargs["profile_id"] == 2
    assert kwargs["origin_client_id"] == "origin-1"
    assert kwargs["keys"] == [{"content_id": "tmdb:550", "content_type": "movie"}]

    assert stores[0].deleted == [(2, [{"content_id": "tmdb:550", "content_type": "movie"}])]
    assert stores[0].closed is True
    invalidate.assert_called_once_with()
    execute_builtin.assert_called_once_with("Container.Refresh")
    notification.assert_called_once_with("text-91042", time=3000)


def test_nuvio_remove_from_library_notifies_and_leaves_mirror_on_failure(monkeypatch):
    import lib.navigation as navigation

    client, stores, invalidate, notification, execute_builtin = _patch_write_handler(
        monkeypatch, navigation, push_result=False
    )

    navigation.nuvio_remove_from_library({"content_id": "tmdb:550", "content_type": "movie"})

    client.remove_library_items.assert_called_once()
    assert stores[0].deleted == []
    assert stores[0].closed is True
    invalidate.assert_not_called()
    execute_builtin.assert_not_called()
    notification.assert_called_once_with("text-91043", time=3000)


def test_nuvio_add_to_library_rejects_invalid_payload(monkeypatch):
    import lib.navigation as navigation

    client, _stores, invalidate, notification, _execute = _patch_write_handler(
        monkeypatch, navigation, push_result=True
    )

    navigation.nuvio_add_to_library({"data": "not-json"})

    client.add_library_items.assert_not_called()
    invalidate.assert_not_called()
    notification.assert_called_once_with("text-91043", time=3000)


def test_nuvio_remove_from_library_rejects_invalid_params(monkeypatch):
    import lib.navigation as navigation

    client, _stores, invalidate, notification, _execute = _patch_write_handler(
        monkeypatch, navigation, push_result=True
    )

    navigation.nuvio_remove_from_library({"content_id": "", "content_type": "movie"})
    navigation.nuvio_remove_from_library({"content_id": "tmdb:550", "content_type": "person"})

    client.remove_library_items.assert_not_called()
    invalidate.assert_not_called()
    assert notification.call_count == 2


# ---------------------------------------------------------------------------
# Nuvio history context menu
# ---------------------------------------------------------------------------


def test_nuvio_history_context_menu_requires_sync_and_valid_identity(monkeypatch):
    from lib.utils import nuvio_context

    action_url_run = MagicMock(return_value="RunPlugin(command)")
    monkeypatch.setattr(nuvio_context, "action_url_run", action_url_run)
    monkeypatch.setattr(nuvio_context, "translation", lambda value: f"label-{value}")
    monkeypatch.setattr(nuvio_context, "is_nuvio_progress_sync_enabled", lambda: False)

    assert nuvio_context.add_nuvio_history_context_menu("movie", 42) == []

    monkeypatch.setattr(nuvio_context, "is_nuvio_progress_sync_enabled", lambda: True)
    assert nuvio_context.add_nuvio_history_context_menu("movie", "bad") == []
    assert nuvio_context.add_nuvio_history_context_menu("person", 42) == []
    assert nuvio_context.add_nuvio_history_context_menu("episode", 42, None, 1) == []
    assert nuvio_context.add_nuvio_history_context_menu("episode", 42, 1, 0) == []


def test_nuvio_history_context_menu_builds_add_and_remove_entries(monkeypatch):
    from lib.utils import nuvio_context

    action_url_run = MagicMock(return_value="RunPlugin(command)")
    monkeypatch.setattr(nuvio_context, "action_url_run", action_url_run)
    monkeypatch.setattr(nuvio_context, "translation", lambda value: f"label-{value}")
    monkeypatch.setattr(nuvio_context, "is_nuvio_progress_sync_enabled", lambda: True)

    movie_menu = nuvio_context.add_nuvio_history_context_menu("movie", "42")
    assert [label for label, _command in movie_menu] == ["label-91044", "label-91045"]
    assert action_url_run.call_args_list[0].kwargs == {
        "operation": "add",
        "media_type": "movie",
        "tmdb_id": "42",
    }
    assert action_url_run.call_args_list[1].kwargs == {
        "operation": "remove",
        "media_type": "movie",
        "tmdb_id": "42",
    }

    action_url_run.reset_mock()
    episode_menu = nuvio_context.add_nuvio_history_context_menu("episode", "42", 1, "2")
    assert [label for label, _command in episode_menu] == ["label-91044", "label-91045"]
    assert action_url_run.call_args_list[0].kwargs == {
        "operation": "add",
        "media_type": "episode",
        "tmdb_id": "42",
        "season": 1,
        "episode": "2",
    }


def test_nuvio_history_context_menu_carries_display_title(monkeypatch):
    from lib.utils import nuvio_context

    action_url_run = MagicMock(return_value="RunPlugin(command)")
    monkeypatch.setattr(nuvio_context, "action_url_run", action_url_run)
    monkeypatch.setattr(nuvio_context, "translation", lambda value: f"label-{value}")
    monkeypatch.setattr(nuvio_context, "is_nuvio_progress_sync_enabled", lambda: True)

    nuvio_context.add_nuvio_history_context_menu("movie", "42", title="Fight Club")

    assert action_url_run.call_args_list[0].kwargs["title"] == "Fight Club"
    assert action_url_run.call_args_list[1].kwargs["title"] == "Fight Club"

    # A blank/absent title is simply omitted, never sent as an empty string.
    action_url_run.reset_mock()
    nuvio_context.add_nuvio_history_context_menu("movie", "42", title="   ")
    assert "title" not in action_url_run.call_args_list[0].kwargs


# ---------------------------------------------------------------------------
# Nuvio history handler
# ---------------------------------------------------------------------------


def _patch_history_handler(monkeypatch, push_result=True, delete_result=True, confirm=True):
    from lib.utils.views import nuvio_history as view

    calls = {"push": [], "delete": []}

    class _HistoryClient(NuvioClient):
        def __init__(self, *args, **kwargs):
            pass

        def push_watched_items(self, profile_id=None, items=None):
            calls["push"].append({"profile_id": profile_id, "items": items})
            return push_result

        def delete_watched_items(self, profile_id=None, keys=None):
            calls["delete"].append({"profile_id": profile_id, "keys": keys})
            return delete_result

    monkeypatch.setattr(view, "NuvioClient", _HistoryClient)
    notification = MagicMock()
    refresh = MagicMock()
    confirmation = MagicMock(return_value=confirm)
    monkeypatch.setattr(view, "notification", notification)
    monkeypatch.setattr(view, "refresh", refresh)
    monkeypatch.setattr(view, "dialogyesno", confirmation)
    monkeypatch.setattr(view, "translation", lambda value: f"text-{value}")
    monkeypatch.setattr(view, "Thread", _SyncThread)
    return view, calls, notification, refresh, confirmation


def test_update_nuvio_history_add_pushes_item_and_notifies(monkeypatch):
    view, calls, notification, refresh, _confirmation = _patch_history_handler(monkeypatch)

    view.update_nuvio_history({"operation": "add", "media_type": "movie", "tmdb_id": "550"})

    assert len(calls["push"]) == 1
    item = calls["push"][0]["items"][0]
    assert item["content_id"] == "tmdb:550"
    assert item["content_type"] == "movie"
    assert item["watched_at"] > 0
    notification.assert_called_once_with("text-91046", time=3000)
    refresh.assert_called_once()


def test_update_nuvio_history_add_carries_provided_title(monkeypatch):
    view, calls, _notification, _refresh, _confirmation = _patch_history_handler(monkeypatch)

    view.update_nuvio_history(
        {"operation": "add", "media_type": "movie", "tmdb_id": "550", "title": "Fight Club"}
    )

    assert calls["push"][0]["items"][0]["title"] == "Fight Club"


def test_update_nuvio_history_add_episode_includes_season_and_episode(monkeypatch):
    view, calls, _notification, _refresh, _confirmation = _patch_history_handler(monkeypatch)

    view.update_nuvio_history(
        {"operation": "add", "media_type": "episode", "tmdb_id": 1396, "season": 2, "episode": 5}
    )

    item = calls["push"][0]["items"][0]
    assert item["content_type"] == "series"
    assert item["season"] == 2
    assert item["episode"] == 5


def test_update_nuvio_history_remove_confirms_then_deletes(monkeypatch):
    view, calls, notification, refresh, confirmation = _patch_history_handler(monkeypatch)

    view.update_nuvio_history({"operation": "remove", "media_type": "movie", "tmdb_id": 550})

    confirmation.assert_called_once_with("text-91049", "text-91050")
    assert calls["delete"] == [{"profile_id": None, "keys": [{"content_id": "tmdb:550"}]}]
    notification.assert_called_once_with("text-91047", time=3000)
    refresh.assert_called_once()


def test_update_nuvio_history_remove_episode_deletes_with_season_and_episode(monkeypatch):
    view, calls, _notification, _refresh, _confirmation = _patch_history_handler(monkeypatch)

    view.update_nuvio_history(
        {
            "operation": "remove",
            "media_type": "episode",
            "tmdb_id": "1396",
            "season": 2,
            "episode": 5,
        }
    )

    assert calls["delete"][0]["keys"] == [{"content_id": "tmdb:1396", "season": 2, "episode": 5}]


def test_update_nuvio_history_remove_declined_makes_no_request(monkeypatch):
    view, calls, notification, refresh, _confirmation = _patch_history_handler(
        monkeypatch, confirm=False
    )

    view.update_nuvio_history({"operation": "remove", "media_type": "movie", "tmdb_id": 550})

    assert calls["delete"] == []
    notification.assert_not_called()
    refresh.assert_not_called()


def test_update_nuvio_history_add_failure_notifies_error(monkeypatch):
    view, calls, notification, refresh, _confirmation = _patch_history_handler(
        monkeypatch, push_result=False
    )

    view.update_nuvio_history({"operation": "add", "media_type": "movie", "tmdb_id": 550})

    assert len(calls["push"]) == 1
    notification.assert_called_once_with("text-91048", time=3000)
    refresh.assert_not_called()


def test_update_nuvio_history_remove_failure_notifies_error(monkeypatch):
    view, calls, notification, refresh, _confirmation = _patch_history_handler(
        monkeypatch, delete_result=False
    )

    view.update_nuvio_history({"operation": "remove", "media_type": "movie", "tmdb_id": 550})

    assert len(calls["delete"]) == 1
    notification.assert_called_once_with("text-91048", time=3000)
    refresh.assert_not_called()


@pytest.mark.parametrize(
    "params",
    [
        None,
        "not-a-dict",
        {},
        {"operation": "add"},
        {"operation": "add", "media_type": "person", "tmdb_id": 550},
        {"operation": "delete", "media_type": "movie", "tmdb_id": 550},
        {"operation": "add", "media_type": "movie", "tmdb_id": 0},
        {"operation": "add", "media_type": "movie", "tmdb_id": "bad"},
        {"operation": "add", "media_type": "episode", "tmdb_id": 1396, "season": 2},
        {
            "operation": "add",
            "media_type": "episode",
            "tmdb_id": 1396,
            "season": 2,
            "episode": 0,
        },
    ],
)
def test_update_nuvio_history_invalid_params_make_no_request(monkeypatch, params):
    view, calls, notification, refresh, _confirmation = _patch_history_handler(monkeypatch)

    view.update_nuvio_history(params)

    assert calls["push"] == []
    assert calls["delete"] == []
    notification.assert_not_called()
    refresh.assert_not_called()


# ---------------------------------------------------------------------------
# History view: Remove from Nuvio History context menu
# ---------------------------------------------------------------------------


def test_show_nuvio_history_adds_remove_context_menu(monkeypatch):
    from lib.utils.views import nuvio_history as view

    item, add_items = _patch_view_shell(monkeypatch, view)
    monkeypatch.setattr(view, "tmdb_get", MagicMock(return_value=None))
    monkeypatch.setattr(view, "set_media_infoTag", MagicMock())

    class _HistoryViewClient(NuvioClient):
        def __init__(self, *args, **kwargs):
            pass

        def get_watched_history(self, page=1, page_size=500):
            return [
                {
                    "tmdb_id": 550,
                    "mode": "movies",
                    "season": None,
                    "episode": None,
                    "title": "Fight Club",
                    "watched_at_ms": 1711600000000,
                },
                {
                    "tmdb_id": 1396,
                    "mode": "tv",
                    "season": 2,
                    "episode": 5,
                    "title": "Breaking Bad",
                    "watched_at_ms": 1711600001000,
                },
            ]

    monkeypatch.setattr(view, "NuvioClient", _HistoryViewClient)

    view.show_nuvio_history()

    assert add_items.call_args.args[0] != []
    movie_menu = item.addContextMenuItems.call_args_list[0].args[0]
    assert movie_menu[0][0] == "text-91045"
    assert movie_menu[0][1] == (
        f"RunPlugin({view.build_url('nuvio_update_history', operation='remove', media_type='movie', tmdb_id=550)})"
    )
    tv_menu = item.addContextMenuItems.call_args_list[1].args[0]
    assert "media_type=episode" in tv_menu[0][1]
    assert "season=2" in tv_menu[0][1]
    assert "episode=5" in tv_menu[0][1]
