import importlib
import re
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest

PLAYER_PATH = Path(__file__).resolve().parents[2] / "lib" / "player.py"


def test_monitor_finally_uses_non_destructive_cleanup():
    source = PLAYER_PATH.read_text()
    monitor_match = re.search(
        r"def monitor\(self\):(?P<body>.*?)def handle_subtitles", source, re.S
    )

    assert monitor_match is not None

    monitor_body = monitor_match.group("body")
    finally_match = re.search(r"finally:\n(?P<body>(?:\s+.*\n)+)", monitor_body)

    assert finally_match is not None

    finally_body = finally_match.group("body")
    assert "self.cancel_playback()" not in finally_body


def test_cancel_playback_signals_kodi_and_stops_player():
    source = PLAYER_PATH.read_text()
    cancel_match = re.search(
        r"def cancel_playback\(self\):(?P<body>.*?)def _cleanup_playback_session",
        source,
        re.S,
    )

    assert cancel_match is not None

    cancel_body = cancel_match.group("body")
    assert "self._cleanup_playback_session()" in cancel_body
    # Must signal Kodi to avoid spinners (setResolvedUrl with False)
    assert "setResolvedUrl(ADDON_HANDLE, False, ListItem(offscreen=True))" in cancel_body
    # Must actually stop playback started by Player.play()
    assert "self.stop()" in cancel_body


def test_play_video_always_uses_player_play_not_resolved_url(monkeypatch):
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module)
    test_player.url = "http://stream"
    test_player.play = MagicMock()
    test_player.monitor = MagicMock()
    test_player.cancel_playback = MagicMock()
    test_player._check_volume = MagicMock(return_value=True)
    test_player._handle_trakt_scrobble = MagicMock()
    test_player.handle_subtitles = MagicMock()
    list_item = MagicMock()

    test_player.play_video(list_item)

    test_player.play.assert_called_once_with("http://stream", list_item)
    test_player.monitor.assert_called_once_with()


def test_failed_trakt_scrobble_keeps_direct_playback(monkeypatch):
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module)
    test_player.url = "http://stream"
    test_player.play = MagicMock()
    test_player.monitor = MagicMock()
    test_player.cancel_playback = MagicMock()
    test_player._check_volume = MagicMock(return_value=True)
    test_player.handle_subtitles = MagicMock()
    trakt_api = MagicMock()
    trakt_api.return_value.scrobble.trakt_get_last_tracked_position.return_value = 0
    trakt_api.return_value.scrobble.trakt_start_scrobble.side_effect = RuntimeError("network down")
    monkeypatch.setattr(player_module, "is_trakt_auth", lambda: True)
    monkeypatch.setattr(player_module, "get_setting", lambda _key: True)
    monkeypatch.setattr(player_module, "TraktAPI", trakt_api)
    monkeypatch.setattr(player_module, "kodilog", MagicMock())
    list_item = MagicMock()

    test_player.play_video(list_item)

    test_player.play.assert_called_once_with("http://stream", list_item)
    test_player.monitor.assert_called_once_with()
    test_player.cancel_playback.assert_not_called()
    assert any("start scrobble failed; continuing playback" in str(call) for call in player_module.kodilog.call_args_list)


def test_failed_trakt_metadata_setup_does_not_abort_tracking_setup(monkeypatch):
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module)
    trakt_lists = MagicMock()
    trakt_lists.return_value.make_trakt_slug.side_effect = RuntimeError("network down")
    monkeypatch.setattr(player_module, "TraktLists", trakt_lists)
    monkeypatch.setattr(player_module, "kodilog", MagicMock())
    monkeypatch.setattr(player_module, "set_property", MagicMock())

    test_player.add_external_trakt_scrolling()

    player_module.set_property.assert_not_called()
    assert any("metadata setup failed; continuing playback" in str(call) for call in player_module.kodilog.call_args_list)


def test_live_tv_skips_authenticated_trakt_scrobbling_and_resume(monkeypatch):
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module)
    test_player.data["is_live_tv"] = True
    test_player._is_trakt_scrobble_active = False
    trakt_api = MagicMock()
    monkeypatch.setattr(player_module, "is_trakt_auth", lambda: True)
    monkeypatch.setattr(player_module, "get_setting", lambda _key: True)
    monkeypatch.setattr(player_module, "TraktAPI", trakt_api)
    monkeypatch.setattr(player_module, "set_watched_file", MagicMock())
    monkeypatch.setattr(player_module, "set_property", MagicMock())

    test_player._handle_trakt_scrobble(MagicMock())
    test_player.add_external_trakt_scrolling()
    test_player.mark_watched(test_player.data)
    test_player.handle_playback_stop()

    trakt_api.assert_not_called()
    player_module.set_property.assert_not_called()
    player_module.set_watched_file.assert_not_called()
    assert test_player._is_trakt_scrobble_active is False


@pytest.mark.parametrize(
    "ids",
    (
        {"tmdb_id": "", "original_id": "ustv-1234"},
        {"tmdb_id": "ustv-1234"},
        {"original_id": "opaque-addon-id"},
        None,
    ),
)
def test_opaque_or_blank_ids_skip_trakt_tracking_without_live_tv_inference(monkeypatch, ids):
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module)
    test_player.data["ids"] = ids
    trakt_api = MagicMock()
    monkeypatch.setattr(player_module, "is_trakt_auth", lambda: True)
    monkeypatch.setattr(player_module, "get_setting", lambda _key: True)
    monkeypatch.setattr(player_module, "TraktAPI", trakt_api)

    test_player._handle_trakt_scrobble(MagicMock())

    assert test_player._is_live_tv() is False
    assert test_player._is_trakt_tracking_excluded() is True
    trakt_api.assert_not_called()


def test_informational_placeholder_skips_trakt_scrobbling_resume_and_history(monkeypatch):
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module)
    test_player.data["is_informational_placeholder"] = True
    test_player._is_trakt_scrobble_active = False
    trakt_api = MagicMock()
    monkeypatch.setattr(player_module, "is_trakt_auth", lambda: True)
    monkeypatch.setattr(player_module, "get_setting", lambda _key: True)
    monkeypatch.setattr(player_module, "TraktAPI", trakt_api)
    monkeypatch.setattr(player_module, "set_watched_file", MagicMock())
    monkeypatch.setattr(player_module, "set_property", MagicMock())

    test_player._handle_trakt_scrobble(MagicMock())
    test_player.add_external_trakt_scrolling()
    test_player.mark_watched(test_player.data)
    test_player.handle_playback_stop()

    trakt_api.assert_not_called()
    player_module.set_property.assert_not_called()
    player_module.set_watched_file.assert_not_called()
    assert test_player._is_trakt_scrobble_active is False


def test_non_live_tv_keeps_authenticated_trakt_scrobbling(monkeypatch):
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module)
    test_player._is_trakt_scrobble_active = False
    trakt_api = MagicMock()
    trakt_api.return_value.scrobble.trakt_get_last_tracked_position.return_value = 25
    monkeypatch.setattr(player_module, "is_trakt_auth", lambda: True)
    monkeypatch.setattr(player_module, "get_setting", lambda _key: True)
    monkeypatch.setattr(player_module, "TraktAPI", trakt_api)
    list_item = MagicMock()

    test_player._handle_trakt_scrobble(list_item)

    trakt_api.return_value.scrobble.trakt_get_last_tracked_position.assert_called_once_with(
        test_player.data
    )
    trakt_api.return_value.scrobble.trakt_start_scrobble.assert_called_once_with(test_player.data)
    list_item.setProperty.assert_called_once_with("StartPercent", "25")
    assert test_player._is_trakt_scrobble_active is True


def test_valid_movie_keeps_authenticated_trakt_scrobbling(monkeypatch):
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module)
    test_player.data = {"mode": "movies", "ids": {"tmdb_id": "123"}}
    trakt_api = MagicMock()
    trakt_api.return_value.scrobble.trakt_get_last_tracked_position.return_value = 0
    monkeypatch.setattr(player_module, "is_trakt_auth", lambda: True)
    monkeypatch.setattr(player_module, "get_setting", lambda _key: True)
    monkeypatch.setattr(player_module, "TraktAPI", trakt_api)

    test_player._handle_trakt_scrobble(MagicMock())

    trakt_api.return_value.scrobble.trakt_get_last_tracked_position.assert_called_once_with(
        test_player.data
    )
    trakt_api.return_value.scrobble.trakt_start_scrobble.assert_called_once_with(test_player.data)
    assert test_player._is_trakt_scrobble_active is True


def test_run_does_not_add_next_episode_to_kodi_playlist():
    source = PLAYER_PATH.read_text()
    run_match = re.search(
        r"def run\(self, data=None\):(?P<body>.*?)def _drain_nextep_queue", source, re.S
    )

    assert run_match is not None

    run_body = run_match.group("body")
    assert "self.build_playlist()" not in run_body


def _episode(number, name="Episode", air_date="2020-01-01"):
    return SimpleNamespace(episode_number=number, name=name, air_date=air_date)


def _player_module(monkeypatch):
    class FakeXbmcPlayer:
        pass

    monkeypatch.setattr(sys.modules["xbmc"], "Player", FakeXbmcPlayer)
    from lib import player as player_module

    return importlib.reload(player_module)


def _player_for_episode(player_module, season=1, episode=1):
    JacktookPLayer = player_module.JacktookPLayer

    player = JacktookPLayer.__new__(JacktookPLayer)
    player.data = {
        "mode": "tv",
        "title": "Test Show",
        "ids": {"tmdb_id": 123, "imdb_id": "tt123"},
        "tv_data": {"season": season, "episode": episode},
    }
    return player


def _player_instance():
    from lib.player import JacktookPLayer

    player = object.__new__(JacktookPLayer)
    player.data = {
        "mode": "tv",
        "title": "Show",
        "ids": {"tmdb_id": "123"},
        "tv_data": {"season": 1, "episode": 1},
    }
    player.playnext = MagicMock()
    player.play = MagicMock()
    player.run = MagicMock()
    player.PLAYLIST = MagicMock()
    return player


class FakeThread:
    def __init__(self, *args, **kwargs):
        self.target = kwargs.get("target")
        self.args = kwargs.get("args", ())
        self.daemon = False

    def start(self):
        pass


def test_get_next_episode_data_same_season(monkeypatch):
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module, season=1, episode=1)
    details = SimpleNamespace(number_of_seasons=1)
    season_details = SimpleNamespace(episodes=[_episode(1, "Pilot"), _episode(2, "Second")])

    def fake_tmdb_get(path, params=None):
        if path == "tv_details":
            return details
        if path == "season_details":
            return season_details
        return None

    monkeypatch.setattr(player_module, "tmdb_get", fake_tmdb_get)

    assert test_player._get_next_episode_data() == {
        "name": "Second",
        "episode": 2,
        "season": 1,
    }


def test_get_next_episode_data_season_boundary(monkeypatch):
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module, season=1, episode=10)
    details = SimpleNamespace(number_of_seasons=2)
    season_one = SimpleNamespace(episodes=[_episode(number) for number in range(1, 11)])
    season_two = SimpleNamespace(episodes=[_episode(1, "Season Two Premiere")])

    def fake_tmdb_get(path, params=None):
        if path == "tv_details":
            return details
        if path == "season_details" and params["season"] == 1:
            return season_one
        if path == "season_details" and params["season"] == 2:
            return season_two
        return None

    monkeypatch.setattr(player_module, "tmdb_get", fake_tmdb_get)

    assert test_player._get_next_episode_data() == {
        "name": "Season Two Premiere",
        "episode": 1,
        "season": 2,
    }


def test_get_next_episode_data_accepts_string_season_episode(monkeypatch):
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module, season="1", episode="1")
    details = SimpleNamespace(number_of_seasons=1)
    season_details = SimpleNamespace(episodes=[_episode(1, "Pilot"), _episode(2, "Second")])

    def fake_tmdb_get(path, params=None):
        if path == "tv_details":
            return details
        if path == "season_details":
            assert params["season"] == 1
            return season_details
        return None

    monkeypatch.setattr(player_module, "tmdb_get", fake_tmdb_get)

    assert test_player._get_next_episode_data() == {
        "name": "Second",
        "episode": 2,
        "season": 1,
    }


def _make_fake_date(fixed_today):
    """Create a fake date module with a fixed today() for deterministic testing."""

    class FakeDate(date):
        @classmethod
        def today(cls):
            return fixed_today

    # Replace date's __new__ to return FakeDate instances for specific dates
    # while keeping date() construction working normally
    original_new = date.__new__

    class PatchedDate(FakeDate):
        def __new__(cls, year, month, day):
            return original_new(cls, year, month, day)

    return PatchedDate


def test_get_next_episode_data_future_air_date_returns_none(monkeypatch):
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module, season=1, episode=1)
    details = SimpleNamespace(number_of_seasons=1)
    season_details = SimpleNamespace(
        episodes=[_episode(1, "Pilot"), _episode(2, "Future", "2999-01-01")]
    )

    def fake_tmdb_get(path, params=None):
        if path == "tv_details":
            return details
        if path == "season_details":
            return season_details
        return None

    monkeypatch.setattr(player_module, "tmdb_get", fake_tmdb_get)
    monkeypatch.setattr(player_module, "date", _make_fake_date(date(2020, 6, 15)))

    assert test_player._get_next_episode_data() is None


def test_get_next_episode_data_past_air_date_returns_episode(monkeypatch):
    """Task 2.6: Past air date returns episode with mocked today()."""
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module, season=1, episode=1)
    details = SimpleNamespace(number_of_seasons=1)
    season_details = SimpleNamespace(
        episodes=[_episode(1, "Pilot", "2020-01-01"), _episode(2, "Aired", "2020-01-15")]
    )

    def fake_tmdb_get(path, params=None):
        if path == "tv_details":
            return details
        if path == "season_details":
            return season_details
        return None

    monkeypatch.setattr(player_module, "tmdb_get", fake_tmdb_get)
    monkeypatch.setattr(player_module, "date", _make_fake_date(date(2020, 6, 15)))

    assert test_player._get_next_episode_data() == {
        "name": "Aired",
        "episode": 2,
        "season": 1,
    }


def test_queue_from_autoscrape_cache_missing_id_returns_false(monkeypatch):
    """Missing id_value returns False early."""
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module)
    ids = {}
    next_tv_data = {"season": 1, "episode": 2}

    result = test_player._queue_from_autoscrape_cache(next_tv_data, ids)

    assert result is False


def test_queue_from_autoscrape_cache_cache_miss_returns_false(monkeypatch):
    """Cache miss returns False."""
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module)
    ids = {"tmdb_id": 123}
    next_tv_data = {"season": 1, "episode": 2}

    monkeypatch.setattr(player_module.cache, "get", lambda key: None)

    result = test_player._queue_from_autoscrape_cache(next_tv_data, ids)

    assert result is False


def test_queue_from_autoscrape_cache_cache_hit_autoplay_enabled(monkeypatch):
    """Cache hit with autoplay enabled: queues data, stops player, returns True."""
    player_module = _player_module(monkeypatch)
    player_module.JacktookPLayer._nextep_queue.clear()
    test_player = _player_for_episode(player_module)
    ids = {"tmdb_id": 123}
    next_tv_data = {"season": 1, "episode": 2}
    cached_data = {"url": "http://cached", "title": "Cached Ep"}
    test_player.stop = MagicMock()

    monkeypatch.setattr(player_module.cache, "get", lambda key: cached_data)
    monkeypatch.setattr("lib.utils.kodi.settings.auto_play_enabled", lambda: True)
    clear_mock = MagicMock()
    monkeypatch.setattr(player_module, "clear_property", clear_mock)

    result = test_player._queue_from_autoscrape_cache(next_tv_data, ids)

    assert result is True
    assert len(player_module.JacktookPLayer._nextep_queue) == 1
    entry = player_module.JacktookPLayer._nextep_queue[0]
    assert entry["data"]["autoplay"] is True
    assert entry["data"]["playnext_context"] is True
    test_player.stop.assert_called_once_with()
    clear_mock.assert_called_once_with("jacktook_next_dialog_action")
    player_module.JacktookPLayer._nextep_queue.clear()


def test_queue_from_autoscrape_cache_cache_hit_autoplay_disabled(monkeypatch):
    """Cache hit with autoplay disabled: queues with results, stops player, returns True."""
    player_module = _player_module(monkeypatch)
    player_module.JacktookPLayer._nextep_queue.clear()
    test_player = _player_for_episode(player_module)
    ids = {"tmdb_id": 123}
    next_tv_data = {"season": 1, "episode": 2}
    cached_data = {"url": "http://cached", "title": "Cached Ep"}
    test_player.stop = MagicMock()

    monkeypatch.setattr(player_module.cache, "get", lambda key: cached_data)
    monkeypatch.setattr("lib.utils.kodi.settings.auto_play_enabled", lambda: False)
    clear_mock = MagicMock()
    monkeypatch.setattr(player_module, "clear_property", clear_mock)

    result = test_player._queue_from_autoscrape_cache(next_tv_data, ids)

    assert result is True
    assert len(player_module.JacktookPLayer._nextep_queue) == 1
    test_player.stop.assert_called_once_with()
    clear_mock.assert_called_once_with("jacktook_next_dialog_action")
    player_module.JacktookPLayer._nextep_queue.clear()


def test_drain_nextep_queue_clears_empty_queue(monkeypatch):
    """Empty queue is handled without error."""
    player_module = _player_module(monkeypatch)
    player_module.JacktookPLayer._nextep_queue.clear()
    test_player = _player_for_episode(player_module)

    test_player._drain_nextep_queue()  # Should not raise or hang


def test_check_still_watching_threshold_disabled(monkeypatch):
    """Task 2.2: Threshold is zero skips dialog immediately."""
    from lib.player import JacktookPLayer

    player = _player_instance()
    monkeypatch.setattr("lib.player.get_setting", lambda key, default=None: 0)

    result = JacktookPLayer._check_still_watching_threshold(player)

    assert result is False


def test_check_still_watching_threshold_below_threshold(monkeypatch):
    """Task 2.2: Count below threshold increments counter."""
    from lib.player import JacktookPLayer

    player = _player_instance()
    set_property_mock = MagicMock()

    monkeypatch.setattr("lib.player.get_setting", lambda key, default=None: 3)
    monkeypatch.setattr("lib.player.get_property", lambda key: "1")
    monkeypatch.setattr("lib.player.set_property", set_property_mock)

    result = JacktookPLayer._check_still_watching_threshold(player)

    assert result is False
    set_property_mock.assert_called_once_with("jacktook_consecutive_autoplays", "2")


def test_check_still_watching_threshold_reached_user_continues(monkeypatch):
    """Task 2.2: Count reaches threshold, user continues, resets to 1."""
    import xbmcgui

    from lib.player import JacktookPLayer

    player = _player_instance()
    set_property_mock = MagicMock()
    clear_property_mock = MagicMock()
    dialog = MagicMock()
    dialog.yesno.return_value = True

    monkeypatch.setattr("lib.player.get_setting", lambda key, default=None: 3)
    monkeypatch.setattr("lib.player.get_property", lambda key: "3")
    monkeypatch.setattr("lib.player.set_property", set_property_mock)
    monkeypatch.setattr("lib.player.clear_property", clear_property_mock)
    monkeypatch.setattr(xbmcgui, "Dialog", lambda: dialog)

    result = JacktookPLayer._check_still_watching_threshold(player)

    assert result is False
    set_property_mock.assert_called_once_with("jacktook_consecutive_autoplays", "1")


def test_check_still_watching_threshold_reached_user_stops(monkeypatch):
    """Task 2.2: Count reaches threshold, user stops, returns True."""
    import xbmcgui

    from lib.player import JacktookPLayer

    player = _player_instance()
    set_property_mock = MagicMock()
    clear_property_mock = MagicMock()
    dialog = MagicMock()
    dialog.yesno.return_value = False

    monkeypatch.setattr("lib.player.get_setting", lambda key, default=None: 3)
    monkeypatch.setattr("lib.player.get_property", lambda key: "3")
    monkeypatch.setattr("lib.player.set_property", set_property_mock)
    monkeypatch.setattr("lib.player.clear_property", clear_property_mock)
    monkeypatch.setattr(xbmcgui, "Dialog", lambda: dialog)

    result = JacktookPLayer._check_still_watching_threshold(player)

    assert result is True
    set_property_mock.assert_not_called()
    assert clear_property_mock.call_args_list == [
        call("jacktook_consecutive_autoplays"),
        call("jacktook_next_dialog_action"),
    ]


def test_check_still_watching_threshold_invalid_count_str(monkeypatch):
    """Task 2.2: Invalid count_str defaults to 1, increments correctly."""
    from lib.player import JacktookPLayer

    player = _player_instance()
    set_property_mock = MagicMock()

    monkeypatch.setattr("lib.player.get_setting", lambda key, default=None: 2)
    monkeypatch.setattr("lib.player.get_property", lambda key: "abc")
    monkeypatch.setattr("lib.player.set_property", set_property_mock)

    result = JacktookPLayer._check_still_watching_threshold(player)

    assert result is False
    set_property_mock.assert_called_once_with("jacktook_consecutive_autoplays", "2")


def test_build_playlist_adds_next_episode(monkeypatch):
    """Task 2.3: Has next episode data adds to PLAYLIST."""
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module)
    test_player.preferred_group = "GRP"
    next_data = {"name": "Next Ep", "episode": 2, "season": 1}

    monkeypatch.setattr(test_player, "_get_next_episode_data", lambda: next_data)
    monkeypatch.setattr(
        player_module,
        "get_setting",
        lambda key, default=None: True if key == "autoscrape_next_episode" else default,
    )
    monkeypatch.setattr(
        player_module,
        "build_url",
        lambda action, **kw: "plugin://play_autoscraped",
    )
    playlist = MagicMock()
    playlist.size.return_value = 0
    test_player.PLAYLIST = playlist

    test_player.build_playlist()

    playlist.add.assert_called_once()
    call_url = playlist.add.call_args[1]["url"]
    assert call_url == "plugin://play_autoscraped"


def test_build_playlist_no_next_episode(monkeypatch):
    """Task 2.3: No next episode data returns early."""
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module)
    test_player.preferred_group = "GRP"

    monkeypatch.setattr(test_player, "_get_next_episode_data", lambda: None)
    playlist = MagicMock()
    test_player.PLAYLIST = playlist

    test_player.build_playlist()

    playlist.add.assert_not_called()


def test_build_playlist_deduplicates(monkeypatch):
    """Task 2.3: Duplicate URL in playlist is skipped."""
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module)
    test_player.preferred_group = "GRP"
    next_data = {"name": "Next Ep", "episode": 2, "season": 1}

    monkeypatch.setattr(test_player, "_get_next_episode_data", lambda: next_data)
    monkeypatch.setattr(
        player_module,
        "get_setting",
        lambda key, default=None: True if key == "autoscrape_next_episode" else default,
    )
    monkeypatch.setattr(
        player_module,
        "build_url",
        lambda action, **kw: "plugin://play_autoscraped",
    )
    # Playlist already has the URL
    mock_item = MagicMock()
    mock_item.getPath.return_value = "plugin://play_autoscraped"
    playlist = MagicMock()
    playlist.size.return_value = 1
    playlist.__getitem__.return_value = mock_item
    test_player.PLAYLIST = playlist

    test_player.build_playlist()

    playlist.add.assert_not_called()


def test_build_playlist_search_fallback(monkeypatch):
    """Task 2.3: Uses search URL format when autoscrape disabled."""
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module)
    test_player.preferred_group = "GRP"
    next_data = {"name": "Next Ep", "episode": 2, "season": 1}

    monkeypatch.setattr(test_player, "_get_next_episode_data", lambda: next_data)
    monkeypatch.setattr(
        player_module,
        "get_setting",
        lambda key, default=None: False if key == "autoscrape_next_episode" else default,
    )
    monkeypatch.setattr(
        player_module,
        "build_url",
        lambda action, **kw: "plugin://search",
    )
    playlist = MagicMock()
    playlist.size.return_value = 0
    test_player.PLAYLIST = playlist

    test_player.build_playlist()

    playlist.add.assert_called_once()
    call_url = playlist.add.call_args[1]["url"]
    assert call_url == "plugin://search"


def test_handle_subtitles_skips_on_autoplay(monkeypatch):
    """Task 2.4: Autoplay flag set skips subtitle handling."""
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module)
    test_player.data["autoplay"] = True
    test_player.showSubtitles = MagicMock()

    list_item = MagicMock()
    test_player.handle_subtitles(list_item)

    test_player.showSubtitles.assert_not_called()


def test_handle_subtitles_autoplay_stream_subtitles_attach_returned_subtitles(monkeypatch):
    player_module = _player_module(monkeypatch)
    from lib.clients.subtitle import submanager

    test_player = _player_for_episode(player_module)
    test_player.data["autoplay"] = True
    test_player.data["stream_subtitles"] = [
        {"url": "https://example.com/sub.en.srt", "lang": "eng"}
    ]
    test_player.notification = MagicMock()
    test_player.setSubtitleStream = MagicMock()

    class FakeSubtitleManager:
        def __init__(self, data, notification):
            assert data is test_player.data
            assert notification is test_player.notification

        def fetch_subtitles(self, auto_select=False):
            assert auto_select is True
            return ["/path/to/embedded.srt"]

    monkeypatch.setattr(submanager, "SubtitleManager", FakeSubtitleManager)
    monkeypatch.setattr(
        player_module,
        "get_setting",
        lambda key, default=None: True if key == "stremio_subtitle_enabled" else default,
    )
    monkeypatch.setattr(player_module, "get_property", lambda key: "")

    list_item = MagicMock()
    test_player.handle_subtitles(list_item)

    list_item.setSubtitles.assert_called_once_with(["/path/to/embedded.srt"])
    test_player.setSubtitleStream.assert_called_once_with(0)
    assert test_player.subtitles_found is True


def test_handle_subtitles_uses_unified_automation_setting(monkeypatch):
    player_module = _player_module(monkeypatch)
    from lib.clients.subtitle import submanager

    test_player = _player_for_episode(player_module)
    test_player.notification = MagicMock()
    test_player.setSubtitleStream = MagicMock()

    class FakeSubtitleManager:
        def __init__(self, *_args):
            pass

        def fetch_subtitles(self, auto_select=False):
            assert auto_select is True
            return ["/path/to/automatic.srt"]

    monkeypatch.setattr(submanager, "SubtitleManager", FakeSubtitleManager)
    monkeypatch.setattr(player_module, "subtitle_automation_enabled", lambda: True)
    monkeypatch.setattr(
        player_module,
        "get_setting",
        lambda key, default=None: True if key == "stremio_subtitle_enabled" else default,
    )
    monkeypatch.setattr(player_module, "get_property", lambda _key: "")

    list_item = MagicMock()
    test_player.handle_subtitles(list_item)

    list_item.setSubtitles.assert_called_once_with(["/path/to/automatic.srt"])
    test_player.setSubtitleStream.assert_called_once_with(0)


def test_handle_subtitles_preserves_manual_selection_when_automation_disabled(monkeypatch):
    player_module = _player_module(monkeypatch)
    from lib.clients.subtitle import submanager

    test_player = _player_for_episode(player_module)
    test_player.notification = MagicMock()
    test_player.setSubtitleStream = MagicMock()

    class FakeSubtitleManager:
        def __init__(self, *_args):
            pass

        def fetch_subtitles(self, auto_select=False):
            assert auto_select is False
            return ["/path/to/manual.srt"]

    monkeypatch.setattr(submanager, "SubtitleManager", FakeSubtitleManager)
    monkeypatch.setattr(player_module, "subtitle_automation_enabled", lambda: False)
    monkeypatch.setattr(
        player_module,
        "get_setting",
        lambda key, default=None: True if key == "stremio_subtitle_enabled" else default,
    )
    monkeypatch.setattr(player_module, "get_property", lambda _key: "")

    list_item = MagicMock()
    test_player.handle_subtitles(list_item)

    list_item.setSubtitles.assert_called_once_with(["/path/to/manual.srt"])
    test_player.setSubtitleStream.assert_called_once_with(0)


@pytest.mark.parametrize(
    ("unified_enabled", "expected_auto_select"),
    [(True, True), (False, False)],
)
def test_handle_subtitles_migrates_with_kodi_strings_before_subtitle_lookup(
    monkeypatch, unified_enabled, expected_auto_select
):
    player_module = _player_module(monkeypatch)
    from lib.clients.subtitle import submanager
    from lib.utils.kodi import settings

    test_player = _player_for_episode(player_module)
    test_player.notification = MagicMock()
    test_player.setSubtitleStream = MagicMock()
    values = {
        "subtitle_automation_migrated": False,
        "subtitle_automation": unified_enabled,
        "auto_subtitle_selection": False,
        "auto_subtitle_download": False,
    }
    writes = []

    def kodi_set_setting(key, value):
        assert isinstance(value, str)
        writes.append((key, value))
        values[key] = value

    class FakeSubtitleManager:
        def __init__(self, *_args):
            pass

        def fetch_subtitles(self, auto_select=False):
            assert auto_select is expected_auto_select
            return ["/path/to/subtitle.srt"]

    monkeypatch.setattr(settings, "get_setting", lambda key, default=None: values.get(key, default))
    monkeypatch.setattr(settings, "set_setting", kodi_set_setting)
    monkeypatch.setattr(
        player_module, "subtitle_automation_enabled", settings.subtitle_automation_enabled
    )
    monkeypatch.setattr(submanager, "SubtitleManager", FakeSubtitleManager)
    monkeypatch.setattr(
        player_module,
        "get_setting",
        lambda key, default=None: True if key == "stremio_subtitle_enabled" else default,
    )
    monkeypatch.setattr(player_module, "get_property", lambda _key: "")

    list_item = MagicMock()
    test_player.handle_subtitles(list_item)

    assert writes == [
        ("subtitle_automation", "true" if unified_enabled else "false"),
        ("subtitle_automation_migrated", "true"),
    ]
    list_item.setSubtitles.assert_called_once_with(["/path/to/subtitle.srt"])


def test_advance_across_season_boundary_series_end(monkeypatch):
    """Task 2.5: At series end (last ep of last season) returns None."""
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module)
    episodes = [SimpleNamespace(episode_number=10)]
    tv_details = SimpleNamespace(number_of_seasons=3)

    result = test_player._advance_across_season_boundary(
        "123", season=3, episode=10, episodes=episodes, tv_details=tv_details
    )

    assert result is None


def test_advance_across_season_boundary_single_season(monkeypatch):
    """Task 2.5: Single season show advances within season."""
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module)
    episodes = [
        SimpleNamespace(episode_number=1),
        SimpleNamespace(episode_number=2),
        SimpleNamespace(episode_number=3),
    ]
    tv_details = SimpleNamespace(number_of_seasons=1)

    result = test_player._advance_across_season_boundary(
        "123", season=1, episode=1, episodes=episodes, tv_details=tv_details
    )

    assert result == (1, 2, episodes)


def test_advance_across_season_boundary_crosses_season(monkeypatch):
    """Task 2.5: Season boundary crossing fetches next season episodes."""
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module)
    current_episodes = [SimpleNamespace(episode_number=8)]
    next_episodes = [SimpleNamespace(episode_number=1)]
    tv_details = SimpleNamespace(number_of_seasons=2)

    monkeypatch.setattr(
        test_player,
        "_fetch_season_episodes",
        lambda tmdb_id, season: next_episodes,
    )

    result = test_player._advance_across_season_boundary(
        "123",
        season=1,
        episode=8,
        episodes=current_episodes,
        tv_details=tv_details,
    )

    assert result == (2, 1, next_episodes)


def test_advance_across_season_boundary_fetch_fails(monkeypatch):
    """Task 2.5: Next season episodes fetch fails returns None."""
    player_module = _player_module(monkeypatch)
    test_player = _player_for_episode(player_module)
    current_episodes = [SimpleNamespace(episode_number=8)]
    tv_details = SimpleNamespace(number_of_seasons=2)

    monkeypatch.setattr(
        test_player,
        "_fetch_season_episodes",
        lambda tmdb_id, season: None,
    )

    result = test_player._advance_across_season_boundary(
        "123",
        season=1,
        episode=8,
        episodes=current_episodes,
        tv_details=tv_details,
    )

    assert result is None


def test_handle_next_dialog_action_fallback_uses_season_boundary_episode(monkeypatch):
    """Without cache, fires background search thread with season-crossing TV data."""
    player_module = _player_module(monkeypatch)
    player_module.JacktookPLayer._nextep_queue.clear()

    class FakePlaylist:
        def size(self):
            return -1

        def getposition(self):
            return -1

        def clear(self):
            self.cleared = True

    test_player = _player_for_episode(player_module, season=1, episode=10)
    test_player.PLAYLIST = FakePlaylist()
    threads = []

    class CapturingThread(FakeThread):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            threads.append(self)

    monkeypatch.setattr(player_module, "Thread", CapturingThread)

    def fake_get_setting(key, default=None):
        if key == "playnext_threshold":
            return 0
        return default

    monkeypatch.setattr(player_module, "get_setting", fake_get_setting)
    monkeypatch.setattr(player_module, "get_property", lambda key: "")
    monkeypatch.setattr(player_module, "clear_property", lambda key: None)
    monkeypatch.setattr(player_module.cache, "get", lambda key: None)
    monkeypatch.setattr(
        test_player,
        "_get_next_episode_data",
        lambda: {"name": "Season Two Premiere", "episode": 1, "season": 2},
    )

    test_player._handle_next_dialog_action()

    assert len(threads) == 1
    target, args = threads[0].target, threads[0].args
    assert target == test_player._background_search_and_queue
    item_data, next_tv_data = args
    assert item_data["mode"] == "tv"
    assert next_tv_data == {"name": "Season Two Premiere", "episode": 1, "season": 2}
