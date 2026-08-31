import json
from unittest.mock import MagicMock

import pytest

from lib.api.trakt.trakt import TraktScrobble
from lib.utils.general.items_menus import root_menu_items


def test_trakt_playback_maps_only_safe_canonical_sessions():
    movie = TraktScrobble.playback_item(
        {
            "id": "10",
            "type": "movie",
            "progress": "42.5",
            "paused_at": "2026-08-06T12:00:00Z",
            "movie": {
                "title": "Movie",
                "ids": {"tmdb": "123"},
                "overview": "Movie overview",
            },
        }
    )
    episode = TraktScrobble.playback_item(
        {
            "id": 11,
            "type": "episode",
            "progress": 12,
            "paused_at": "2026-08-06T12:00:00+00:00",
            "show": {
                "title": "Show",
                "ids": {"tmdb": 456},
                "overview": "Show overview",
            },
            "episode": {
                "title": "Special",
                "season": 0,
                "number": 1,
                "overview": "Episode overview",
            },
        }
    )

    assert movie["trakt_playback_id"] == 10
    assert movie["overview"] == "Movie overview"
    assert "poster" not in movie
    assert "fanart" not in movie
    assert episode["tv_data"] == {"name": "Special", "season": 0, "episode": 1}
    assert episode["overview"] == "Episode overview"
    assert "poster" not in episode
    assert "fanart" not in episode
    assert TraktScrobble.playback_item(
        {
            "id": 12,
            "type": "movie",
            "progress": 80,
            "paused_at": "2026-08-06T12:00:00Z",
            "movie": {"title": "Bad", "ids": {"tmdb": 1}},
        }
    ) is None
    assert TraktScrobble.playback_item(
        {
            "id": 13,
            "type": "movie",
            "progress": True,
            "paused_at": "2026-08-06T12:00:00Z",
            "movie": {"title": "Bad", "ids": {"tmdb": 1}},
        }
    ) is None


def test_trakt_playback_retrieval_and_deletion_use_authenticated_contract(monkeypatch):
    client = TraktScrobble()
    call_trakt = MagicMock(return_value=[])
    monkeypatch.setattr("lib.api.trakt.trakt.is_trakt_auth", lambda: True)
    monkeypatch.setattr(client, "call_trakt", call_trakt)

    assert client.get_playback() == []
    call_trakt.assert_called_once_with(
        "sync/playback",
        params={"limit": 1000, "extended": "full"},
        with_auth=True,
        pagination=False,
    )

    response = MagicMock(status_code=204)
    delete = MagicMock(return_value=response)
    monkeypatch.setattr("lib.api.trakt.trakt.requests.delete", delete)
    monkeypatch.setattr(client, "ensure_token_valid", lambda: None)
    monkeypatch.setattr("lib.api.trakt.trakt.get_property", lambda _key: "token")
    monkeypatch.setattr(client, "_trakt_headers", lambda: {"trakt-api-key": "client"})

    assert client.delete_playback("42") is True
    delete.assert_called_once_with(
        "https://api.trakt.tv/sync/playback/42",
        headers={"trakt-api-key": "client", "Authorization": "Bearer token"},
        timeout=20,
    )


def test_trakt_menu_is_visible_only_for_enabled_authenticated_accounts(monkeypatch):
    item = next(item for item in root_menu_items if item["action"] == "trakt_continue_watching")
    for enabled, authenticated, expected_visible in (
        (False, False, False),
        (False, True, False),
        (True, False, False),
        (True, True, True),
    ):
        settings = {"trakt_enabled": enabled}
        monkeypatch.setattr(
            "lib.utils.views.trakt_continue_watching.get_setting",
            lambda setting_id: settings[setting_id],
        )
        monkeypatch.setattr(
            "lib.utils.views.trakt_continue_watching.is_trakt_auth", lambda: authenticated
        )

        assert item["condition"]() is expected_visible


def test_trakt_continue_watching_builds_resume_and_explicit_discard_actions(monkeypatch):
    from lib.utils.views import trakt_continue_watching as view

    item = MagicMock()
    monkeypatch.setattr(view, "make_list_item", MagicMock(return_value=item))
    add_items = MagicMock()
    monkeypatch.setattr(view, "add_directory_items_batch", add_items)
    monkeypatch.setattr(view, "setContent", MagicMock())
    monkeypatch.setattr(view, "end_of_directory", MagicMock())
    monkeypatch.setattr(view, "apply_section_view", MagicMock())
    monkeypatch.setattr(view, "set_pluging_category", MagicMock())
    truncate_text = MagicMock(return_value="Truncated description")
    monkeypatch.setattr(view, "truncate_text", truncate_text)
    tmdb_get = MagicMock(return_value={"id": 1})
    set_media_info_tag = MagicMock()
    monkeypatch.setattr(view, "tmdb_get", tmdb_get)
    monkeypatch.setattr(view, "set_media_infoTag", set_media_info_tag)
    monkeypatch.setattr(
        view.TraktScrobble,
        "get_playback",
        lambda _self: [
            {
                "query": "Show",
                "mode": "tv",
                "media_type": "tv",
                "ids": {"tmdb_id": 1},
                "tv_data": {"name": "Episode", "season": 2, "episode": 3},
                "trakt_playback_id": 9,
                "trakt_resume_progress": 50,
                "overview": "Episode description",
            }
        ],
    )

    view.show_trakt_continue_watching()

    url, list_item, is_folder = add_items.call_args.args[0][0]
    assert "action=trakt_resume" in url
    assert "trakt_playback_id=9" in url
    assert is_folder is False
    assert view.make_list_item.call_args.kwargs["label"] == "Show S02E03"
    tmdb_get.assert_called_once_with("tv_details", 1)
    set_media_info_tag.assert_called_once_with(list_item, data={"id": 1}, mode="tv")
    list_item.setArt.assert_not_called()
    truncate_text.assert_not_called()
    list_item.getVideoInfoTag().setTitle.assert_called_once_with("Show S02E03")
    list_item.setProperty.assert_any_call("PercentPlayed", "50")
    assert list_item.addContextMenuItems.call_args.args[0][0][0] == "Discard Trakt Resume"


def test_trakt_continue_watching_uses_movie_tmdb_details(monkeypatch):
    from lib.utils.views import trakt_continue_watching as view

    item = MagicMock()
    monkeypatch.setattr(view, "make_list_item", MagicMock(return_value=item))
    monkeypatch.setattr(view, "add_directory_items_batch", MagicMock())
    monkeypatch.setattr(view, "setContent", MagicMock())
    monkeypatch.setattr(view, "end_of_directory", MagicMock())
    monkeypatch.setattr(view, "apply_section_view", MagicMock())
    monkeypatch.setattr(view, "set_pluging_category", MagicMock())
    tmdb_get = MagicMock(return_value={"id": 2})
    set_media_info_tag = MagicMock()
    monkeypatch.setattr(view, "tmdb_get", tmdb_get)
    monkeypatch.setattr(view, "set_media_infoTag", set_media_info_tag)
    monkeypatch.setattr(
        view.TraktScrobble,
        "get_playback",
        lambda _self: [
            {
                "query": "Movie",
                "mode": "movies",
                "media_type": "movie",
                "ids": {"tmdb_id": 2},
                "tv_data": {},
                "trakt_playback_id": 9,
                "trakt_resume_progress": 50,
            }
        ],
    )

    view.show_trakt_continue_watching()

    tmdb_get.assert_called_once_with("movie_details", 2)
    set_media_info_tag.assert_called_once_with(item, data={"id": 2}, mode="movies")
    item.setArt.assert_not_called()


def test_trakt_continue_watching_uses_icon_when_tmdb_metadata_is_unavailable(monkeypatch):
    from lib.utils.views import trakt_continue_watching as view

    item = MagicMock()
    monkeypatch.setattr(view, "make_list_item", MagicMock(return_value=item))
    add_items = MagicMock()
    monkeypatch.setattr(view, "add_directory_items_batch", add_items)
    monkeypatch.setattr(view, "setContent", MagicMock())
    monkeypatch.setattr(view, "end_of_directory", MagicMock())
    monkeypatch.setattr(view, "apply_section_view", MagicMock())
    monkeypatch.setattr(view, "set_pluging_category", MagicMock())
    monkeypatch.setattr(view, "tmdb_get", MagicMock(return_value=None))
    truncate_text = MagicMock(return_value="Truncated overview")
    monkeypatch.setattr(view, "truncate_text", truncate_text)
    set_media_info_tag = MagicMock()
    monkeypatch.setattr(view, "set_media_infoTag", set_media_info_tag)
    monkeypatch.setattr(
        view.TraktScrobble,
        "get_playback",
        lambda _self: [
            {
                "query": "Movie",
                "mode": "movies",
                "media_type": "movie",
                "ids": {"tmdb_id": 1},
                "tv_data": {},
                "trakt_playback_id": 9,
                "trakt_resume_progress": 50,
                "overview": "Movie overview",
            }
        ],
    )

    view.show_trakt_continue_watching()

    art = item.setArt.call_args.args[0]
    assert art == {"icon": view.os.path.join(view.ADDON_PATH, "resources", "img", "magnet.png")}
    set_media_info_tag.assert_not_called()
    truncate_text.assert_called_once_with("Movie overview")
    item.getVideoInfoTag().setPlot.assert_called_once_with("Truncated overview")
    assert add_items.call_args.args[0][0][1] is item


def test_trakt_discard_refreshes_only_after_successful_delete(monkeypatch):
    from lib.utils.views import trakt_continue_watching as view

    delete = MagicMock(return_value=False)
    monkeypatch.setattr(view.TraktScrobble, "delete_playback", delete)
    refresh = MagicMock()
    monkeypatch.setattr(view, "executebuiltin", refresh)

    view.discard_trakt_playback({"playback_id": "9"})
    refresh.assert_not_called()

    delete.return_value = True
    view.discard_trakt_playback({"playback_id": "9"})
    refresh.assert_called_once_with("Container.Refresh")


def test_trakt_resume_resolves_external_ids_and_forces_rescrape(monkeypatch):
    from lib import navigation

    run_search_entry = MagicMock()
    tmdb_metadata = MagicMock(
        return_value={"external_ids": {"imdb_id": "tt1234567", "tvdb_id": 98765}}
    )
    monkeypatch.setattr("lib.search.run_search_entry", run_search_entry)
    monkeypatch.setattr(navigation.TmdbClient, "_get_tmdb_metadata", tmdb_metadata)
    params = {
        "query": "Movie",
        "mode": "movies",
        "media_type": "movie",
        "ids": json.dumps({"tmdb_id": 123}),
        "trakt_playback_id": "9",
        "trakt_resume_progress": "50",
    }

    navigation.trakt_resume(params)

    tmdb_metadata.assert_called_once_with("movies", "movie", 123)
    run_search_entry.assert_called_once()
    search_params = run_search_entry.call_args.args[0]
    assert search_params["rescrape"] is True
    assert json.loads(search_params["ids"]) == {
        "tmdb_id": 123,
        "imdb_id": "tt1234567",
        "tvdb_id": 98765,
    }


@pytest.mark.parametrize(
    "tmdb_response",
    [None, RuntimeError("TMDB unavailable")],
    ids=["metadata unavailable", "TMDB request fails"],
)
def test_trakt_resume_continues_search_when_tmdb_metadata_is_unavailable(
    monkeypatch, tmdb_response
):
    from lib import navigation

    run_search_entry = MagicMock()
    tmdb_metadata = MagicMock()
    if isinstance(tmdb_response, Exception):
        tmdb_metadata.side_effect = tmdb_response
    else:
        tmdb_metadata.return_value = tmdb_response
    monkeypatch.setattr("lib.search.run_search_entry", run_search_entry)
    monkeypatch.setattr(navigation.TmdbClient, "_get_tmdb_metadata", tmdb_metadata)
    params = {
        "query": "Movie",
        "mode": "movies",
        "media_type": "movie",
        "ids": json.dumps({"tmdb_id": 123}),
        "trakt_playback_id": "9",
        "trakt_resume_progress": "50",
    }

    navigation.trakt_resume(params)

    run_search_entry.assert_called_once()
    search_params = run_search_entry.call_args.args[0]
    assert search_params["query"] == "Movie"
    assert search_params["rescrape"] is True
    assert json.loads(search_params["ids"]) == {"tmdb_id": 123}
