import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, quote, urlparse

import pytest


@pytest.fixture(autouse=True)
def fresh_player_module(monkeypatch):
    import lib
    import xbmc

    class FakeKodiPlayer:
        def __init__(self, *args, **kwargs):
            pass

    original_player_module = sys.modules.get("lib.player")

    monkeypatch.setattr(xbmc, "Player", FakeKodiPlayer)
    sys.modules.pop("lib.player", None)
    if hasattr(lib, "player"):
        delattr(lib, "player")

    try:
        yield
    finally:
        sys.modules.pop("lib.player", None)
        if hasattr(lib, "player"):
            delattr(lib, "player")

        if original_player_module is not None:
            sys.modules["lib.player"] = original_player_module
            setattr(lib, "player", original_player_module)


def _query(url):
    return parse_qs(urlparse(url).query)


def _current_pack_data(magnet="magnet:?xt=urn:btih:PACKHASH"):
    return {
        "mode": "tv",
        "is_pack": True,
        "ids": {"tmdb_id": "37606", "imdb_id": "tt1942683"},
        "tv_data": {"season": 5, "episode": 3, "name": "L'Ami"},
        "url": (
            "plugin://plugin.video.elementum/play"
            f"?uri={quote(magnet)}&type=tv&tmdb=37606"
            "&show=37606&season=5&episode=3"
        ),
        "magnet": magnet,
        "progress": 95.0,
        "current_time": 1200,
        "total_time": 1260,
        "subtitles_path": ["current.srt"],
    }


def test_source_pack_marker_is_preserved_in_playback_data():
    from lib.gui.base_window import BaseWindow

    class TestWindow(BaseWindow):
        def handle_action(self, action_id, control_id=None):
            pass

    window = object.__new__(TestWindow)
    window.item_information = {
        "mode": "tv",
        "ids": {"tmdb_id": "37606"},
        "tv_data": {"season": 5, "episode": 3},
    }
    source = SimpleNamespace(
        type="torrent",
        indexer="Jackett",
        infoHash="PACKHASH",
        title="Season pack",
        isPack=True,
        streamSubtitles=[],
        stremioMetadata={},
        debridType="",
    )

    data = window.prepare_source_data(
        source,
        url="",
        magnet="magnet:?xt=urn:btih:PACKHASH",
        is_torrent=True,
    )

    assert data["is_pack"] is True


def test_build_elementum_pack_next_playback_reuses_same_uri():
    from lib.utils.player import utils

    current = _current_pack_data()
    next_tv_data = {"season": 5, "episode": 4, "name": "L'Ennui"}

    with patch.object(utils, "is_elementum_addon", return_value=True):
        result = utils.build_elementum_pack_next_playback(current, next_tv_data)

    assert result is not None
    query = _query(result["url"])
    assert query["uri"] == [current["magnet"]]
    assert query["show"] == ["37606"]
    assert query["season"] == ["5"]
    assert query["episode"] == ["4"]
    assert result["tv_data"] == next_tv_data
    assert result["playnext_context"] is True
    assert "autoplay" not in result
    assert "progress" not in result
    assert "subtitles_path" not in result


@pytest.mark.parametrize(
    "mutation,next_tv_data",
    [
        ({"is_pack": False}, {"season": 5, "episode": 4}),
        ({"url": "plugin://plugin.video.other/play"}, {"season": 5, "episode": 4}),
        ({}, {"season": 6, "episode": 1}),
    ],
)
def test_build_elementum_pack_next_playback_rejects_unsafe_reuse(mutation, next_tv_data):
    from lib.utils.player import utils

    current = _current_pack_data()
    current.update(mutation)

    with patch.object(utils, "is_elementum_addon", return_value=True):
        assert utils.build_elementum_pack_next_playback(current, next_tv_data) is None


def test_explicit_pack_playnext_is_queued_without_global_autoplay(monkeypatch):
    from lib.player import JacktookPLayer

    player = object.__new__(JacktookPLayer)
    player.data = _current_pack_data()
    player.stop = MagicMock()
    clear_property = MagicMock()
    next_data = {
        "url": "plugin://plugin.video.elementum/play?episode=4",
        "mode": "tv",
        "tv_data": {"season": 5, "episode": 4},
    }
    monkeypatch.setattr(
        "lib.player.build_elementum_pack_next_playback",
        lambda *_args, **_kwargs: next_data,
    )
    monkeypatch.setattr("lib.player.clear_property", clear_property)
    JacktookPLayer._nextep_queue.clear()

    try:
        assert player._queue_elementum_pack_next({"season": 5, "episode": 4}) is True
        assert JacktookPLayer._nextep_queue == [{"data": next_data}]
    finally:
        JacktookPLayer._nextep_queue.clear()

    assert "autoplay" not in next_data
    player.stop.assert_called_once_with()
    clear_property.assert_called_once_with("jacktook_next_dialog_action")


def test_handle_next_dialog_prefers_same_pack_before_cache(monkeypatch):
    from lib.player import JacktookPLayer

    player = object.__new__(JacktookPLayer)
    player.data = _current_pack_data()
    player._check_still_watching_threshold = MagicMock(return_value=False)
    player._authoritative_next_tv_data = MagicMock(
        return_value={"season": 5, "episode": 4}
    )
    player._queue_elementum_pack_next = MagicMock(return_value=True)
    player._queue_from_autoscrape_cache = MagicMock(return_value=True)

    player._handle_next_dialog_action()

    player._queue_elementum_pack_next.assert_called_once_with(
        {"season": 5, "episode": 4}
    )
    player._queue_from_autoscrape_cache.assert_not_called()


def test_forced_search_keeps_manual_source_selection(monkeypatch):
    from lib.utils.player import utils

    source = MagicMock()
    source.title = "Show S05E04 1080p"
    source.quality = "N/A"
    search_client = MagicMock(return_value=[source])
    cache_set = MagicMock()
    resolve = MagicMock()

    def get_setting(key, default=None):
        return {
            "autoscrape_next_episode": False,
            "auto_play": False,
            "autoscrape_ttl": 4,
        }.get(key, default)

    monkeypatch.setattr("lib.search.search_client", search_client)
    monkeypatch.setattr(
        "lib.search._process_search_results",
        lambda results, *_args, **_kwargs: results,
    )
    monkeypatch.setattr("lib.utils.player.utils.get_setting", get_setting)
    monkeypatch.setattr("lib.utils.player.utils.cache.set", cache_set)
    monkeypatch.setattr("lib.utils.player.utils.resolve_playback_url", resolve)

    utils.autoscrape_next_episode(
        {
            "mode": "tv",
            "title": "Show",
            "ids": {"imdb_id": "tt1942683", "tmdb_id": "37606"},
        },
        {"season": 5, "episode": 4},
        force=True,
    )

    search_client.assert_called_once()
    resolve.assert_not_called()
    cache_set.assert_called_once()
    assert cache_set.call_args.args[0] == "as_results:tt1942683_5_4"
    assert cache_set.call_args.args[1] == [source]


def test_manual_cache_path_does_not_require_resolved_autoplay_data(monkeypatch):
    from lib.player import JacktookPLayer

    player = object.__new__(JacktookPLayer)
    player.data = {
        "mode": "tv",
        "title": "Show",
        "media_type": "tv",
        "tv_data": {"season": 5, "episode": 3},
    }
    player.stop = MagicMock()
    results = [MagicMock()]
    clear_property = MagicMock()

    def cache_get(key):
        if key == "as_results:tt1942683_5_4":
            return results
        return None

    monkeypatch.setattr("lib.player.cache.get", cache_get)
    monkeypatch.setattr(
        "lib.utils.kodi.settings.auto_play_enabled", lambda: False
    )
    monkeypatch.setattr("lib.player.clear_property", clear_property)
    JacktookPLayer._nextep_queue.clear()

    try:
        assert player._queue_from_autoscrape_cache(
            {"season": 5, "episode": 4},
            {"imdb_id": "tt1942683"},
        ) is True
        entry = JacktookPLayer._nextep_queue[0]
        assert entry["results"] == results
        assert entry["data"]["tv_data"] == {"season": 5, "episode": 4}
    finally:
        JacktookPLayer._nextep_queue.clear()

    player.stop.assert_called_once_with()
    clear_property.assert_called_once_with("jacktook_next_dialog_action")



def test_season_pack_is_inferred_when_provider_flag_is_missing():
    from lib.gui.base_window import BaseWindow

    class TestWindow(BaseWindow):
        def handle_action(self, action_id, control_id=None):
            pass

    window = object.__new__(TestWindow)
    window.item_information = {
        "mode": "tv",
        "ids": {"tmdb_id": "37606"},
        "tv_data": {"season": 5, "episode": 3},
    }
    source = SimpleNamespace(
        type="torrent",
        indexer="Prowlarr",
        infoHash="PACKHASH",
        title="Le monde incroyable de Gumball s05 vff webrip aac -llam",
        isPack=False,
        streamSubtitles=[],
        stremioMetadata={},
        debridType="",
    )

    data = window.prepare_source_data(
        source,
        url="",
        magnet="magnet:?xt=urn:btih:PACKHASH",
        is_torrent=True,
    )

    assert data["is_pack"] is True
    assert data["pack_type"] == "season"
    assert data["pack_seasons"] == [5]
    assert data["source_title"] == source.title


def test_explicit_multi_season_pack_reuses_uri_across_boundary():
    from lib.utils.player import utils

    current = _current_pack_data()
    current.update(
        {
            "source_title": "Show.S01-S06.Complete.1080p",
            "pack_type": "multi_season",
            "pack_seasons": [1, 2, 3, 4, 5, 6],
            "tv_data": {"season": 5, "episode": 50},
        }
    )

    with patch.object(utils, "is_elementum_addon", return_value=True):
        result = utils.build_elementum_pack_next_playback(
            current, {"season": 6, "episode": 1, "name": "Season premiere"}
        )

    assert result is not None
    query = _query(result["url"])
    assert query["uri"] == [current["magnet"]]
    assert query["season"] == ["6"]
    assert query["episode"] == ["1"]


def test_single_season_pack_does_not_cross_boundary():
    from lib.utils.player import utils

    current = _current_pack_data()
    current.update(
        {
            "source_title": "Show.S05.1080p",
            "pack_type": "season",
            "pack_seasons": [5],
            "tv_data": {"season": 5, "episode": 50},
        }
    )

    with patch.object(utils, "is_elementum_addon", return_value=True):
        result = utils.build_elementum_pack_next_playback(
            current, {"season": 6, "episode": 1}
        )

    assert result is None


def test_complete_series_without_explicit_range_does_not_cross_boundary():
    from lib.utils.player import utils

    current = _current_pack_data()
    current.update(
        {
            "source_title": "Show.Complete.Series.1080p",
            "pack_type": "complete_unknown",
            "pack_seasons": [],
            "tv_data": {"season": 5, "episode": 50},
        }
    )

    with patch.object(utils, "is_elementum_addon", return_value=True):
        result = utils.build_elementum_pack_next_playback(
            current, {"season": 6, "episode": 1}
        )

    assert result is None


def test_forced_manual_search_caches_normal_processed_results(monkeypatch):
    from lib.utils.player import utils

    raw_results = [MagicMock(title="raw")]
    processed_results = [MagicMock(title="processed")]
    search_client = MagicMock(return_value=raw_results)
    process_results = MagicMock(return_value=processed_results)
    cache_set = MagicMock()

    def get_setting(key, default=None):
        return {
            "autoscrape_next_episode": False,
            "auto_play": False,
            "autoscrape_ttl": 4,
        }.get(key, default)

    monkeypatch.setattr("lib.search.search_client", search_client)
    monkeypatch.setattr("lib.search._process_search_results", process_results)
    monkeypatch.setattr("lib.utils.player.utils.get_setting", get_setting)
    monkeypatch.setattr("lib.utils.player.utils.cache.set", cache_set)

    utils.autoscrape_next_episode(
        {
            "mode": "tv",
            "media_type": "tv",
            "title": "Show",
            "ids": {"imdb_id": "tt1942683", "tmdb_id": "37606"},
        },
        {"season": 5, "episode": 4, "name": "Next episode"},
        force=True,
    )

    search_client.assert_called_once()
    process_results.assert_called_once()
    assert process_results.call_args.kwargs == {
        "suppress_debrid_dialog": True,
        "suppress_busy_dialog": True,
    }
    cache_set.assert_called_once()
    assert cache_set.call_args.args[0] == "as_results:tt1942683_5_4"
    assert cache_set.call_args.args[1] == processed_results
