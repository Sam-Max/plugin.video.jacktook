from unittest.mock import MagicMock

import pytest

from lib.api.nuvio import NuvioClient
from lib.utils.general.items_menus import root_menu_items


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
    continue_watching = next(
        item for item in root_menu_items if item["action"] == "nuvio_continue_watching"
    )
    history = next(item for item in root_menu_items if item["action"] == "nuvio_history")

    monkeypatch.setattr(
        "lib.utils.views.nuvio_continue_watching.is_nuvio_progress_sync_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "lib.utils.views.nuvio_history.is_nuvio_progress_sync_enabled", lambda: False
    )
    assert continue_watching["condition"]() is False
    assert history["condition"]() is False

    monkeypatch.setattr(
        "lib.utils.views.nuvio_continue_watching.is_nuvio_progress_sync_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "lib.utils.views.nuvio_history.is_nuvio_progress_sync_enabled", lambda: True
    )
    assert continue_watching["condition"]() is True
    assert history["condition"]() is True


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


def test_show_nuvio_history_builds_folder_urls_for_tv_and_search_for_movies(monkeypatch):
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
    assert "action=search" in movie_url
    assert "mode=movies" in movie_url
    assert movie_is_folder is False

    tv_url, _tv_item, tv_is_folder = directory_items[1]
    assert "action=show_seasons_details" in tv_url
    assert "mode=tv" in tv_url
    assert tv_is_folder is True

    assert view.make_list_item.call_args_list[0].kwargs["label"] == "Fight Club"
    assert view.make_list_item.call_args_list[1].kwargs["label"] == "Breaking Bad S02E05"
    set_media_info_tag.assert_any_call(item, data={"title": "Fight Club"}, mode="movies")
    set_media_info_tag.assert_any_call(item, data={"name": "Breaking Bad"}, mode="tv")
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
    assert "action=show_seasons_details" in url
    assert is_folder is True
    assert view.make_list_item.call_args.kwargs["label"] == "S02E05"
    assert item.setArt.call_args.args[0] == {
        "icon": view.os.path.join(view.ADDON_PATH, "resources", "img", "magnet.png")
    }
    set_media_info_tag.assert_not_called()


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
    view.notification.assert_called_once_with("text-91025", time=3000)


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
    ["nuvio_continue_watching", "nuvio_history", "nuvio_remove_progress"],
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
    ["nuvio_continue_watching", "nuvio_history", "nuvio_remove_progress"],
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
