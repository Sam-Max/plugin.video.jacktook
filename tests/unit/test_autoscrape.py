import json
import re
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_get_autoscrape_cache_key_format():
    from lib.utils.player.utils import get_autoscrape_cache_key

    assert get_autoscrape_cache_key("tt123", 1, 2) == "as:tt123_1_2"
    assert get_autoscrape_cache_key(456, 3, 4) == "as:456_3_4"


def test_cache_autoscrape_result_calls_hybrid_cache():
    from lib.utils.player.utils import cache_autoscrape_result

    with patch("lib.utils.player.utils.cache") as mock_cache:
        data = {"url": "http://example.com", "title": "Test"}
        cache_autoscrape_result("as:key_1_2", data, 4)
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert call_args[0][0] == "as:key_1_2"
        assert call_args[0][1] == data
        assert call_args[1]["expires"] == timedelta(hours=4)


def test_cache_autoscrape_result_uses_default_ttl():
    from lib.utils.player.utils import cache_autoscrape_result

    with patch("lib.utils.player.utils.cache") as mock_cache, patch(
        "lib.utils.player.utils.get_setting", return_value=6
    ):
        data = {"url": "http://example.com"}
        cache_autoscrape_result("as:key_1_2", data)
        call_args = mock_cache.set.call_args
        assert call_args[1]["expires"] == timedelta(hours=6)


def test_autoscrape_next_episode_resolves_and_caches():
    from lib.utils.player.utils import autoscrape_next_episode

    fake_result = MagicMock()
    fake_result.title = "Test Episode"
    fake_result.indexer = "Jackett"
    fake_result.type = "tv"
    fake_result.debridType = "RD"
    fake_result.infoHash = "abc123"
    fake_result.url = "magnet:?xt=urn:btih:abc123"
    fake_result.quality = "1080p"

    resolved_data = {"url": "http://resolved", "title": "Test Episode"}

    with patch("lib.search.search_client", return_value=[fake_result]) as mock_search, patch(
        "lib.utils.player.utils.resolve_playback_url", return_value=resolved_data
    ) as mock_resolve, patch("lib.utils.player.utils.cache") as mock_cache, patch(
        "lib.utils.player.utils.get_setting",
        side_effect=lambda key, default=None: {
            "autoscrape_next_episode": True,
            "auto_play": True,
            "auto_play_quality": "1080p",
        }.get(key, default),
    ):
        item_data = {
            "mode": "tv",
            "ids": {"tmdb_id": "123", "imdb_id": "tt123"},
            "tv_data": {"season": 1, "episode": 1},
            "title": "Show Name",
        }
        next_tv_data = {"season": 1, "episode": 2, "name": "Next Ep"}

        autoscrape_next_episode(item_data, next_tv_data)

        mock_search.assert_called_once()
        mock_resolve.assert_called_once()
        assert mock_cache.set.call_count == 2, (
            f"Expected 2 cache.set calls, got {mock_cache.set.call_count}"
        )
        # First call: raw results cache
        raw_call_args = mock_cache.set.call_args_list[0]
        assert raw_call_args[0][0] == "as_results:tt123_1_2"
        assert raw_call_args[0][1] == [fake_result]
        # Second call: resolved playback data cache
        resolve_call_args = mock_cache.set.call_args_list[1]
        assert resolve_call_args[0][0] == "as:tt123_1_2"
        assert resolve_call_args[0][1] == resolved_data


def test_autoscrape_next_episode_no_results_does_not_cache():
    from lib.utils.player.utils import autoscrape_next_episode

    with patch("lib.search.search_client", return_value=[]) as mock_search, patch(
        "lib.utils.player.utils.cache"
    ) as mock_cache, patch(
        "lib.utils.player.utils.get_setting",
        side_effect=lambda key, default=None: {
            "autoscrape_next_episode": True,
            "auto_play": True,
            "auto_play_quality": "1080p",
        }.get(key, default),
    ):
        item_data = {
            "mode": "tv",
            "ids": {"tmdb_id": "123"},
            "tv_data": {"season": 1, "episode": 1},
            "title": "Show Name",
        }
        next_tv_data = {"season": 1, "episode": 2, "name": "Next Ep"}

        autoscrape_next_episode(item_data, next_tv_data)

        mock_search.assert_called_once()
        mock_cache.set.assert_not_called()


def test_autoscrape_next_episode_disabled_exits_early():
    from lib.utils.player.utils import autoscrape_next_episode

    with patch("lib.search.search_client") as mock_search, patch(
        "lib.utils.player.utils.get_setting", return_value=False
    ):
        item_data = {
            "mode": "tv",
            "ids": {"tmdb_id": "123"},
            "tv_data": {"season": 1, "episode": 1},
        }
        next_tv_data = {"season": 1, "episode": 2, "name": "Next Ep"}

        autoscrape_next_episode(item_data, next_tv_data)

        mock_search.assert_not_called()


def test_play_autoscraped_cache_hit_plays_directly():
    from lib.navigation import play_autoscraped

    cached_data = {"url": "http://cached", "title": "Cached Episode"}

    with patch("lib.navigation.cache") as mock_cache, patch(
        "lib.navigation.JacktookPLayer"
    ) as mock_player_cls, patch("lib.search.run_search_entry") as mock_search_entry, patch(
        "lib.utils.kodi.settings.auto_play_enabled", return_value=True
    ):
        mock_cache.get.return_value = cached_data

        params = {
            "mode": "tv",
            "query": "Show",
            "ids": json.dumps({"tmdb_id": "123"}),
            "tv_data": json.dumps({"season": 1, "episode": 2}),
        }

        play_autoscraped(params)

        mock_player_cls.return_value.run.assert_called_once_with(data=cached_data)
        mock_search_entry.assert_not_called()


def test_play_autoscraped_cache_hit_playnext_context_plays_directly():
    from lib.navigation import play_autoscraped

    cached_data = {"url": "http://cached", "title": "Cached Episode"}

    with patch("lib.navigation.cache") as mock_cache, patch(
        "lib.navigation.JacktookPLayer"
    ) as mock_player_cls, patch("lib.search.run_search_entry") as mock_search_entry, patch(
        "lib.utils.kodi.settings.auto_play_enabled", return_value=True
    ):
        mock_cache.get.return_value = cached_data

        params = {
            "mode": "tv",
            "query": "Show",
            "ids": json.dumps({"tmdb_id": "123"}),
            "tv_data": json.dumps({"season": 1, "episode": 2}),
            "autoplay_context": "1",
        }

        play_autoscraped(params)

        mock_player_cls.return_value.run.assert_called_once_with(
            data={
                "url": "http://cached",
                "title": "Cached Episode",
                "autoplay": True,
                "playnext_context": True,
                "direct_play": True,
            }
        )
        mock_search_entry.assert_not_called()


def test_play_autoscraped_autoplay_disabled_cached_results_shows_source_select():
    """Task 3.2: Autoplay disabled with cached results shows source select."""
    from lib.navigation import play_autoscraped

    cached_data = {"url": "http://cached", "title": "Cached Episode"}
    cached_results = [MagicMock()]

    with patch("lib.navigation.cache") as mock_cache, patch(
        "lib.navigation.JacktookPLayer"
    ) as mock_player_cls, patch("lib.search.run_search_entry") as mock_search_entry, patch(
        "lib.search.show_source_select"
    ) as mock_show_source_select, patch(
        "lib.utils.kodi.settings.auto_play_enabled", return_value=False
    ):
        # First cache.get returns cached_data (autoscrape hit)
        # Second cache.get returns cached_results (results hit)
        mock_cache.get.side_effect = [cached_data, cached_results]

        params = {
            "mode": "tv",
            "query": "Show",
            "ids": json.dumps({"tmdb_id": "123"}),
            "tv_data": json.dumps({"season": 1, "episode": 2}),
        }

        play_autoscraped(params)

        mock_player_cls.return_value.run.assert_not_called()
        mock_search_entry.assert_not_called()
        mock_show_source_select.assert_called_once()
        assert mock_show_source_select.call_args.kwargs["autoplay_context"] is None


def test_play_autoscraped_cached_source_select_preserves_playnext_context():
    from lib.navigation import play_autoscraped

    cached_data = {"url": "http://cached", "title": "Cached Episode"}
    cached_results = [MagicMock()]

    with patch("lib.navigation.cache") as mock_cache, patch(
        "lib.navigation.JacktookPLayer"
    ) as mock_player_cls, patch("lib.search.run_search_entry") as mock_search_entry, patch(
        "lib.search.show_source_select"
    ) as mock_show_source_select, patch(
        "lib.utils.kodi.settings.auto_play_enabled", return_value=False
    ):
        mock_cache.get.side_effect = [cached_data, cached_results]

        params = {
            "mode": "tv",
            "query": "Show",
            "ids": json.dumps({"tmdb_id": "123"}),
            "tv_data": json.dumps({"season": 1, "episode": 2}),
            "autoplay_context": "1",
        }

        play_autoscraped(params)

        mock_player_cls.return_value.run.assert_not_called()
        mock_search_entry.assert_not_called()
        mock_show_source_select.assert_called_once()
        assert mock_show_source_select.call_args.kwargs["autoplay_context"] == "1"


def test_play_autoscraped_autoplay_disabled_no_cached_results_falls_back():
    """Task 3.2: Autoplay disabled with no cached results falls back to search."""
    from lib.navigation import play_autoscraped

    cached_data = {"url": "http://cached", "title": "Cached Episode"}

    with patch("lib.navigation.cache") as mock_cache, patch(
        "lib.navigation.JacktookPLayer"
    ) as mock_player_cls, patch("lib.search.run_search_entry") as mock_search_entry, patch(
        "lib.search.show_source_select"
    ) as mock_show_source_select, patch(
        "lib.utils.kodi.settings.auto_play_enabled", return_value=False
    ):
        # First cache.get returns cached_data (autoscrape hit)
        # Second cache.get returns None (no cached results)
        mock_cache.get.side_effect = [cached_data, None]

        params = {
            "mode": "tv",
            "query": "Show",
            "ids": json.dumps({"tmdb_id": "123"}),
            "tv_data": json.dumps({"season": 1, "episode": 2}),
        }

        play_autoscraped(params)

        mock_player_cls.return_value.run.assert_not_called()
        mock_show_source_select.assert_not_called()
        mock_search_entry.assert_called_once_with(params)


def test_play_autoscraped_cache_miss_falls_back():
    from lib.navigation import play_autoscraped

    with patch("lib.navigation.cache") as mock_cache, patch(
        "lib.navigation.JacktookPLayer"
    ) as mock_player_cls, patch("lib.search.run_search_entry") as mock_search_entry:
        mock_cache.get.return_value = None

        params = {
            "mode": "tv",
            "query": "Show",
            "ids": json.dumps({"tmdb_id": "123"}),
            "tv_data": json.dumps({"season": 1, "episode": 2}),
        }

        play_autoscraped(params)

        mock_player_cls.return_value.run.assert_not_called()
        mock_search_entry.assert_called_once_with(params)


PLAYER_PATH = Path(__file__).resolve().parents[2] / "lib" / "player.py"


def test_build_playlist_emits_play_autoscraped_when_enabled():
    source = PLAYER_PATH.read_text()
    match = re.search(r"def build_playlist\(self\):(?P<body>.*?)def kill_dialog", source, re.S)
    assert match is not None
    body = match.group("body")
    # When autoscrape is enabled, build_url must be called with "play_autoscraped"
    assert '"play_autoscraped"' in body
    # The conditional must check get_setting("autoscrape_next_episode")
    assert 'get_setting("autoscrape_next_episode"' in body


def test_build_playlist_uses_search_when_disabled():
    source = PLAYER_PATH.read_text()
    match = re.search(r"def build_playlist\(self\):(?P<body>.*?)def kill_dialog", source, re.S)
    assert match is not None
    body = match.group("body")
    # Fallback search path must still exist
    assert '"search"' in body
    # play_autoscraped must only be in the True branch
    assert 'if get_setting("autoscrape_next_episode"' in body


def test_monitor_autoscrape_threshold_spawns_thread_once():
    source = PLAYER_PATH.read_text()

    # check_autoscrape_threshold must exist
    assert "def check_autoscrape_threshold(self):" in source

    # Must spawn a Thread with target=autoscrape_next_episode
    threshold_match = re.search(
        r"def check_autoscrape_threshold\(self\):(?P<body>.*?)def check_next_dialog",
        source,
        re.S,
    )
    assert threshold_match is not None
    threshold_body = threshold_match.group("body")
    assert "Thread(target=autoscrape_next_episode" in threshold_body

    # Must reset autoscrape_started in set_constants
    constants_match = re.search(
        r"def set_constants\(self, data\):(?P<body>.*?)def fetch_introdb_segments",
        source,
        re.S,
    )
    assert constants_match is not None
    assert "self.autoscrape_started = False" in constants_match.group("body")

    # Must call check_autoscrape_threshold inside monitor loop
    monitor_match = re.search(
        r"def monitor\(self\):(?P<body>.*?)def handle_subtitles", source, re.S
    )
    assert monitor_match is not None
    assert "self.check_autoscrape_threshold()" in monitor_match.group("body")


def test_run_next_dialog_sets_pending_action_without_direct_playback():
    from lib.gui.custom_dialogs import run_next_dialog

    with patch("lib.gui.custom_dialogs.PLAYLIST") as mock_playlist, patch(
        "lib.gui.custom_dialogs.PlayNext"
    ) as mock_window_cls, patch("lib.gui.custom_dialogs.set_property") as mock_set_property, patch(
        "lib.gui.custom_dialogs.clear_property"
    ) as mock_clear_property, patch("xbmc.Player") as mock_xbmc_player:
        mock_playlist.size.return_value = 2
        mock_playlist.getposition.return_value = 0
        mock_next_item = MagicMock()
        mock_next_item.getLabel.return_value = "1x2. Next Episode"
        mock_playlist.__getitem__.return_value = mock_next_item
        mock_window = MagicMock()
        mock_window.action = "next_episode"
        mock_window_cls.return_value = mock_window

        params = {
            "item_info": json.dumps(
                {
                    "mode": "tv",
                    "title": "Show",
                    "ids": {"tmdb_id": "123"},
                    "tv_data": {"season": 1, "episode": 1},
                }
            )
        }

        run_next_dialog(params)

        mock_set_property.assert_called_once_with("jacktook_next_dialog_action", "next_episode")
        mock_clear_property.assert_not_called()
        mock_xbmc_player.assert_not_called()
        created_item_info = mock_window_cls.call_args.kwargs["item_information"]
        assert created_item_info["next_label"] == "1x2. Next Episode"


def test_run_next_dialog_clears_pending_action_when_dialog_not_accepted():
    from lib.gui.custom_dialogs import run_next_dialog

    with patch("lib.gui.custom_dialogs.PLAYLIST") as mock_playlist, patch(
        "lib.gui.custom_dialogs.PlayNext"
    ) as mock_window_cls, patch("lib.gui.custom_dialogs.set_property") as mock_set_property, patch(
        "lib.gui.custom_dialogs.clear_property"
    ) as mock_clear_property:
        mock_playlist.size.return_value = 2
        mock_playlist.getposition.return_value = 0
        mock_window = MagicMock()
        mock_window.action = "close"
        mock_window_cls.return_value = mock_window

        params = {
            "item_info": json.dumps(
                {
                    "mode": "tv",
                    "title": "Show",
                    "ids": {"tmdb_id": "123"},
                    "tv_data": {"season": 1, "episode": 1},
                }
            )
        }

        run_next_dialog(params)

        mock_set_property.assert_not_called()
        mock_clear_property.assert_called_once_with("jacktook_next_dialog_action")


def test_run_next_dialog_shows_without_next_playlist_item():
    from lib.gui.custom_dialogs import run_next_dialog

    with patch("lib.gui.custom_dialogs.PLAYLIST") as mock_playlist, patch(
        "lib.gui.custom_dialogs.PlayNext"
    ) as mock_window_cls, patch("lib.gui.custom_dialogs.set_property") as mock_set_property, patch(
        "lib.gui.custom_dialogs.clear_property"
    ) as mock_clear_property:
        mock_playlist.size.return_value = 1
        mock_playlist.getposition.return_value = 0
        mock_window = MagicMock()
        mock_window.action = "next_episode"
        mock_window_cls.return_value = mock_window

        run_next_dialog({"item_info": "{}"})

        mock_window_cls.assert_called_once()
        created_item_info = mock_window_cls.call_args.kwargs["item_information"]
        assert "next_label" not in created_item_info
        mock_set_property.assert_called_once_with("jacktook_next_dialog_action", "next_episode")
        mock_clear_property.assert_not_called()
