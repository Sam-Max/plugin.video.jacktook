import importlib
import sys
from unittest.mock import MagicMock, patch

from lib.domain.torrent import TorrentStream
from lib.utils.general.utils import DebridType, IndexerType


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
        "mode": "movie",
    }

    with patch.object(
        source_select_module.SourceSelect,
        "_ensure_playback_info",
        return_value=playback_info,
    ), patch("lib.downloader.get_destination_path", return_value="/downloads") as mock_get_dest, patch.object(source_select_module, "action_url_run", return_value="builtin") as action_url_run, patch.object(
        source_select_module.xbmc, "executebuiltin"
    ) as executebuiltin:
        source_select._download_file(selected_source)

    mock_get_dest.assert_called_once()
    dest_call_data = mock_get_dest.call_args[0][0]
    assert dest_call_data["title"] == "Game of Thrones"
    assert dest_call_data["mode"] == "movies"
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
        "mode": "movie",
    }

    with patch.object(
        source_select_module.SourceSelect,
        "_ensure_playback_info",
        return_value=playback_info,
    ), patch("lib.downloader.get_destination_path", return_value="/downloads") as mock_get_dest, patch.object(source_select_module, "action_url_run", return_value="builtin") as action_url_run, patch.object(
        source_select_module.xbmc, "executebuiltin"
    ) as executebuiltin:
        source_select._download_file(selected_source)

    mock_get_dest.assert_called_once()
    dest_call_data = mock_get_dest.call_args[0][0]
    assert dest_call_data["title"] == "Project Hail Mary"
    assert dest_call_data["mode"] == "movies"
    action_url_run.assert_called_once_with(
        "handle_download_file",
        file_name="Project Hail Mary (2025)",
        url="https://example.com/files/project.hail.mary.mkv",
        destination="/downloads",
    )
    executebuiltin.assert_called_once_with("builtin")


def test_populate_sources_list_shows_debrid_type_for_stremio_debrid_sources():
    source_select_module = _load_source_select_module()
    source_select = source_select_module.SourceSelect.__new__(source_select_module.SourceSelect)

    class _FakeListItem:
        def __init__(self, label=""):
            self.label = label
            self.properties = {}

        def setProperty(self, key, value):
            self.properties[key] = value

    class _FakeDisplayList:
        def __init__(self):
            self.items = []

        def reset(self):
            self.items = []

        def addItem(self, item):
            self.items.append(item)

    source_select.display_list = _FakeDisplayList()
    source_select.filter_applied = False
    source_select.filtered_sources = None
    source_select.sources = [
        TorrentStream(
            title="Example.Source.1080p",
            type=IndexerType.STREMIO_DEBRID,
            debridType=DebridType.TB,
            subindexer="Torrentio",
            size=1024,
            provider="ProviderX",
            quality="1080p",
        )
    ]

    with patch.object(source_select_module.xbmcgui, "ListItem", _FakeListItem), patch.object(
        source_select_module,
        "parse_title_info",
        return_value={
            "clean_title": "Example Source",
            "codec": "",
            "audio": "",
            "badges": "",
            "release_group": "",
        },
    ), patch.object(source_select_module, "bytes_to_human_readable", return_value="1 KB"), patch.object(
        source_select_module, "get_provider_color", side_effect=lambda value: value
    ), patch.object(source_select_module, "get_random_color", side_effect=lambda value: value), patch.object(
        source_select_module, "get_colored_languages", return_value=""
    ), patch.object(source_select_module, "extract_publish_date", return_value=""), patch.object(
        source_select_module, "get_source_status", return_value="[B]Cached[/B]"
    ):
        source_select.populate_sources_list()

    assert source_select.display_list.items[0].properties["type"] == DebridType.TB


def test_torrent_context_menu_does_not_include_download_video():
    source_select_module = _load_source_select_module()
    source_select = source_select_module.SourceSelect.__new__(source_select_module.SourceSelect)
    source_select.position = 0
    source_select.list_sources = [TorrentStream(type=IndexerType.TORRENT)]

    display_list = MagicMock()
    display_list.getSelectedPosition.return_value = 0
    source_select.display_list = display_list

    labels = {
        90365: "Download to debrid",
        90359: "Add to TorrServer",
        90083: "Download video",
        90082: "Download subtitles",
        90744: "Upload subtitle",
    }
    dialog = MagicMock()
    dialog.contextmenu.return_value = -1

    with patch.object(source_select_module, "translation", side_effect=lambda key: labels.get(key, str(key))), \
         patch.object(source_select_module.xbmcgui, "Dialog", return_value=dialog):
        source_select._handle_context_menu_action()

    shown_items = dialog.contextmenu.call_args.args[0]
    assert "Download video" not in shown_items
    assert shown_items == ["Download to debrid", "Add to TorrServer", "Download subtitles", "Upload subtitle"]


def test_torrent_context_menu_download_subtitles_resolves_for_subtitle_download():
    source_select_module = _load_source_select_module()
    source_select = source_select_module.SourceSelect.__new__(source_select_module.SourceSelect)
    source_select.position = 0
    source_select.item_information = {}
    selected_source = TorrentStream(type=IndexerType.TORRENT)
    source_select.list_sources = [selected_source]

    display_list = MagicMock()
    display_list.getSelectedPosition.return_value = 0
    source_select.display_list = display_list

    dialog = MagicMock()
    dialog.contextmenu.return_value = 2

    with patch.object(source_select_module.xbmcgui, "Dialog", return_value=dialog), \
         patch.object(source_select, "_resolve_item") as resolve_item:
        source_select._handle_context_menu_action()

    resolve_item.assert_called_once_with(selected_source, is_subtitle_download=True)
