import importlib
import sys
from unittest.mock import MagicMock, patch


def _load_source_select_module():
    if "lib.gui.source_select" in sys.modules:
        return importlib.reload(sys.modules["lib.gui.source_select"])
    return importlib.import_module("lib.gui.source_select")


def test_download_file_uses_episode_filename_when_tv_data_is_present():
    source_select_module = _load_source_select_module()
    source_select = source_select_module.SourceSelect.__new__(source_select_module.SourceSelect)
    source_select.item_information = {
        "title": "Game of Thrones",
        "tv_data": {"season": "1", "episode": "1"},
    }
    source_select.playback_info = None

    selected_source = MagicMock()
    playback_info = {
        "title": "Game of Thrones",
        "url": "https://example.com/files/game.of.thrones.mkv",
        "tv_data": {"season": "1", "episode": "1"},
    }

    with patch.object(
        source_select_module.SourceSelect,
        "_ensure_playback_info",
        return_value=playback_info,
    ), patch.object(source_select_module, "get_setting", return_value="/downloads"), patch.object(
        source_select_module, "translatePath", return_value="/downloads"
    ), patch.object(source_select_module, "action_url_run", return_value="builtin") as action_url_run, patch.object(
        source_select_module.xbmc, "executebuiltin"
    ) as executebuiltin:
        source_select._download_file(selected_source)

    action_url_run.assert_called_once_with(
        "handle_download_file",
        file_name="Game of Thrones - S01E01",
        url="https://example.com/files/game.of.thrones.mkv",
        destination="/downloads",
    )
    executebuiltin.assert_called_once_with("builtin")


def test_download_file_uses_year_for_movie_filename():
    source_select_module = _load_source_select_module()
    source_select = source_select_module.SourceSelect.__new__(source_select_module.SourceSelect)
    source_select.item_information = {
        "title": "Project Hail Mary",
        "year": 2025,
    }
    source_select.playback_info = None

    selected_source = MagicMock()
    playback_info = {
        "title": "Project Hail Mary",
        "url": "https://example.com/files/project.hail.mary.mkv",
    }

    with patch.object(
        source_select_module.SourceSelect,
        "_ensure_playback_info",
        return_value=playback_info,
    ), patch.object(source_select_module, "get_setting", return_value="/downloads"), patch.object(
        source_select_module, "translatePath", return_value="/downloads"
    ), patch.object(source_select_module, "action_url_run", return_value="builtin") as action_url_run, patch.object(
        source_select_module.xbmc, "executebuiltin"
    ) as executebuiltin:
        source_select._download_file(selected_source)

    action_url_run.assert_called_once_with(
        "handle_download_file",
        file_name="Project Hail Mary (2025)",
        url="https://example.com/files/project.hail.mary.mkv",
        destination="/downloads",
    )
    executebuiltin.assert_called_once_with("builtin")
