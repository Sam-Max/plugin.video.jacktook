import importlib
import json
import sys
from unittest.mock import MagicMock, patch


def _load_navigation_module():
    if "lib.navigation" in sys.modules:
        return importlib.reload(sys.modules["lib.navigation"])
    return importlib.import_module("lib.navigation")


def _load_torrserver_utils():
    if "lib.utils.torrent.torrserver_utils" in sys.modules:
        return importlib.reload(sys.modules["lib.utils.torrent.torrserver_utils"])
    return importlib.import_module("lib.utils.torrent.torrserver_utils")


class TestTorrentsContextMenu:
    def test_adds_download_subtitles_context_menu(self):
        nav = _load_navigation_module()

        mock_torrent = {
            "hash": "abc123",
            "title": "Test Movie",
            "stat": 1,
        }

        mock_meta = {
            "title": "Test Movie",
            "mode": "tv",
            "ids": {"imdb_id": "tt123"},
            "tv_data": {"season": 1, "episode": 2},
        }

        with patch.object(nav, "get_torrserver_api") as mock_api, patch.object(
            nav, "JACKTORR_ADDON", True
        ), patch.object(nav, "end_of_directory"), patch.object(
            nav, "apply_section_view"
        ), patch.object(nav, "set_pluging_category"), patch.object(
            nav, "action_url_run"
        ) as mock_action_url, patch.object(nav, "addDirectoryItem"), patch(
            "lib.utils.torrent.torrserver_utils.get_torrent_meta",
            return_value=mock_meta,
        ):
            mock_api.return_value.torrents.return_value = [mock_torrent]
            mock_action_url.side_effect = lambda name, **kwargs: (
                f"RunPlugin({nav.build_url(name, **kwargs)})"
            )

            nav.torrents({})

            # Find the call for download_torrent_subtitles
            subtitle_calls = [
                call
                for call in mock_action_url.call_args_list
                if call.args[0] == "download_torrent_subtitles"
            ]
            assert len(subtitle_calls) == 1
            call_kwargs = subtitle_calls[0].kwargs
            assert call_kwargs["hash"] == "abc123"
            meta = json.loads(call_kwargs["meta"])
            assert meta["title"] == "Test Movie"
            assert meta["ids"]["imdb_id"] == "tt123"

    def test_uses_torrent_title_when_data_missing(self):
        nav = _load_navigation_module()

        mock_torrent = {
            "hash": "abc123",
            "title": "Fallback Title",
            "stat": 1,
        }

        with patch.object(nav, "get_torrserver_api") as mock_api, patch.object(
            nav, "JACKTORR_ADDON", True
        ), patch.object(nav, "end_of_directory"), patch.object(
            nav, "apply_section_view"
        ), patch.object(nav, "set_pluging_category"), patch.object(
            nav, "action_url_run"
        ) as mock_action_url, patch.object(nav, "addDirectoryItem"), patch(
            "lib.utils.torrent.torrserver_utils.get_torrent_meta", return_value={}
        ):
            mock_api.return_value.torrents.return_value = [mock_torrent]
            mock_action_url.side_effect = lambda name, **kwargs: (
                f"RunPlugin({nav.build_url(name, **kwargs)})"
            )

            nav.torrents({})

            subtitle_calls = [
                call
                for call in mock_action_url.call_args_list
                if call.args[0] == "download_torrent_subtitles"
            ]
            assert len(subtitle_calls) == 1
            meta = json.loads(subtitle_calls[0].kwargs["meta"])
            assert meta["title"] == "Fallback Title"
            assert meta["ids"]["imdb_id"] is None

    def test_forwards_torrent_poster_to_list_item(self):
        nav = _load_navigation_module()

        poster = "http://image.tmdb.org/t/p/w780/abc.jpg"
        mock_torrent = {
            "hash": "abc123",
            "title": "Test Movie",
            "stat": 1,
            "poster": poster,
        }

        with patch.object(nav, "get_torrserver_api") as mock_api, patch.object(
            nav, "JACKTORR_ADDON", True
        ), patch.object(nav, "end_of_directory"), patch.object(
            nav, "apply_section_view"
        ), patch.object(nav, "set_pluging_category"), patch.object(
            nav, "action_url_run"
        ), patch.object(nav, "addDirectoryItem"), patch.object(
            nav, "build_list_item"
        ) as mock_build, patch(
            "lib.utils.torrent.torrserver_utils.get_torrent_meta", return_value={}
        ):
            mock_api.return_value.torrents.return_value = [mock_torrent]

            nav.torrents({})

            mock_build.assert_called_once()
            assert mock_build.call_args.kwargs["poster_path"] == poster


class TestTorrentFilesContextMenu:
    def test_adds_download_subtitles_for_video_files(self):
        utils = _load_torrserver_utils()

        mock_video_tag = MagicMock()
        mock_list_item = MagicMock()
        mock_list_item.getVideoInfoTag.return_value = mock_video_tag

        mock_meta = {
            "title": "Test Movie",
            "mode": "movies",
            "ids": {"imdb_id": "tt123"},
            "tv_data": {},
        }

        with patch.object(utils, "get_torrserver_api") as mock_api, patch.object(
            utils, "is_video", return_value=True
        ), patch.object(utils, "is_picture", return_value=False), patch.object(
            utils, "is_text", return_value=False
        ), patch.object(utils, "is_music", return_value=False), patch.object(
            utils, "set_pluging_category"
        ), patch.object(utils, "end_of_directory"), patch.object(
            utils, "action_url_run"
        ) as mock_action_url, patch.object(utils, "addDirectoryItem") as mock_add_dir, patch.object(
            utils, "build_list_item", return_value=mock_list_item
        ), patch.object(utils, "get_torrent_meta", return_value=mock_meta):
            mock_api.return_value.get_torrent_info.return_value = {
                "title": "Test Movie",
                "hash": "abc123",
                "file_stats": [{"path": "movie.mkv", "id": "1"}],
            }
            mock_api.return_value.get_stream_url.return_value = "http://serve/url"
            mock_action_url.side_effect = lambda name, **kwargs: (
                f"RunPlugin({utils.build_url(name, **kwargs)})"
            )

            utils.torrent_files({"info_hash": "abc123"})

            subtitle_calls = [
                call
                for call in mock_action_url.call_args_list
                if call.args[0] == "download_and_play_subtitles"
            ]
            assert len(subtitle_calls) == 1
            call_kwargs = subtitle_calls[0].kwargs
            assert call_kwargs["hash"] == "abc123"
            assert call_kwargs["file_id"] == "1"
            assert call_kwargs["path"] == "movie.mkv"
            meta = json.loads(call_kwargs["meta"])
            assert meta["title"] == "Test Movie"
            assert meta["ids"]["imdb_id"] == "tt123"
            mock_list_item.getVideoInfoTag.assert_called_once()
            mock_video_tag.setTitle.assert_called_once_with("Test Movie")
            jacktorr_url = "plugin://plugin.video.jacktorr/buffer_and_play?info_hash=abc123&file_id=1&path=movie.mkv"
            mock_list_item.setPath.assert_any_call(jacktorr_url)
            mock_add_dir.assert_called_once_with(utils.ADDON_HANDLE, jacktorr_url, mock_list_item)

    def test_uses_torrent_title_when_data_missing(self):
        utils = _load_torrserver_utils()

        mock_video_tag = MagicMock()
        mock_list_item = MagicMock()
        mock_list_item.getVideoInfoTag.return_value = mock_video_tag

        with patch.object(utils, "get_torrserver_api") as mock_api, patch.object(
            utils, "is_video", return_value=True
        ), patch.object(utils, "is_picture", return_value=False), patch.object(
            utils, "is_text", return_value=False
        ), patch.object(utils, "is_music", return_value=False), patch.object(
            utils, "set_pluging_category"
        ), patch.object(utils, "end_of_directory"), patch.object(
            utils, "action_url_run"
        ) as mock_action_url, patch.object(utils, "addDirectoryItem"), patch.object(
            utils, "build_list_item", return_value=mock_list_item
        ), patch.object(utils, "get_torrent_meta", return_value={}):
            mock_api.return_value.get_torrent_info.return_value = {
                "title": "Fallback Title",
                "hash": "abc123",
                "file_stats": [{"path": "movie.mkv", "id": "1"}],
            }
            mock_api.return_value.get_stream_url.return_value = "http://serve/url"
            mock_action_url.side_effect = lambda name, **kwargs: (
                f"RunPlugin({utils.build_url(name, **kwargs)})"
            )

            utils.torrent_files({"info_hash": "abc123"})

            subtitle_calls = [
                call
                for call in mock_action_url.call_args_list
                if call.args[0] == "download_and_play_subtitles"
            ]
            assert len(subtitle_calls) == 1
            meta = json.loads(subtitle_calls[0].kwargs["meta"])
            assert meta["title"] == "Fallback Title"
            assert meta["ids"]["imdb_id"] is None
            mock_video_tag.setTitle.assert_called_once_with("Fallback Title")

    def test_forwards_torrent_poster_to_file_list_item(self):
        utils = _load_torrserver_utils()

        poster = "http://image.tmdb.org/t/p/w780/abc.jpg"
        mock_list_item = MagicMock()
        mock_video_tag = MagicMock()
        mock_list_item.getVideoInfoTag.return_value = mock_video_tag

        with patch.object(utils, "get_torrserver_api") as mock_api, patch.object(
            utils, "is_video", return_value=True
        ), patch.object(utils, "is_picture", return_value=False), patch.object(
            utils, "is_text", return_value=False
        ), patch.object(utils, "is_music", return_value=False), patch.object(
            utils, "set_pluging_category"
        ), patch.object(utils, "end_of_directory"), patch.object(
            utils, "action_url_run"
        ), patch.object(utils, "addDirectoryItem"), patch.object(
            utils, "build_list_item", return_value=mock_list_item
        ) as mock_build, patch.object(utils, "get_torrent_meta", return_value={}):
            mock_api.return_value.get_torrent_info.return_value = {
                "title": "Test Movie",
                "hash": "abc123",
                "poster": poster,
                "file_stats": [{"path": "movie.mkv", "id": "1"}],
            }
            mock_api.return_value.get_stream_url.return_value = "http://serve/url"

            utils.torrent_files({"info_hash": "abc123"})

            mock_build.assert_called_once()
            assert mock_build.call_args.kwargs["poster_path"] == poster

    def test_strips_common_folder_prefix_from_display_name(self):
        utils = _load_torrserver_utils()

        mock_list_item = MagicMock()
        mock_video_tag = MagicMock()
        mock_list_item.getVideoInfoTag.return_value = mock_video_tag

        full_path = "Show.Name.720p/Season.1/ep01.mkv"

        with patch.object(utils, "get_torrserver_api") as mock_api, patch.object(
            utils, "is_video", return_value=True
        ), patch.object(utils, "is_picture", return_value=False), patch.object(
            utils, "is_text", return_value=False
        ), patch.object(utils, "is_music", return_value=False), patch.object(
            utils, "set_pluging_category"
        ), patch.object(utils, "end_of_directory"), patch.object(
            utils, "action_url_run"
        ), patch.object(utils, "addDirectoryItem"), patch.object(
            utils, "build_list_item", return_value=mock_list_item
        ) as mock_build, patch.object(utils, "get_torrent_meta", return_value={}):
            mock_api.return_value.get_torrent_info.return_value = {
                "title": "Test Show",
                "hash": "abc123",
                "file_stats": [
                    {"path": "Show.Name.720p/Season.1/ep01.mkv", "id": "1"},
                    {"path": "Show.Name.720p/Season.1/ep02.mkv", "id": "2"},
                ],
            }
            mock_api.return_value.get_stream_url.return_value = "http://serve/url"

            utils.torrent_files({"info_hash": "abc123"})

            # build_list_item should receive the stripped display name (label arg)
            labels = [call.args[0] for call in mock_build.call_args_list]
            assert labels == ["ep01.mkv", "ep02.mkv"]

            # _buffer_and_play_url should have received the FULL path (in setPath)
            # setPath is called twice: once with serve_url, once with jacktorr_url
            jacktorr_calls = [
                call
                for call in mock_list_item.setPath.call_args_list
                if "buffer_and_play" in str(call)
            ]
            assert len(jacktorr_calls) == 2
            assert f"path={full_path}" in str(jacktorr_calls[0])

    def test_filters_out_pad_files_from_listing(self):
        utils = _load_torrserver_utils()

        mock_list_item = MagicMock()
        mock_video_tag = MagicMock()
        mock_list_item.getVideoInfoTag.return_value = mock_video_tag

        with patch.object(utils, "get_torrserver_api") as mock_api, patch.object(
            utils, "is_video", return_value=True
        ), patch.object(utils, "is_picture", return_value=False), patch.object(
            utils, "is_text", return_value=False
        ), patch.object(utils, "is_music", return_value=False), patch.object(
            utils, "set_pluging_category"
        ), patch.object(utils, "end_of_directory"), patch.object(
            utils, "action_url_run"
        ), patch.object(utils, "addDirectoryItem"), patch.object(
            utils, "build_list_item", return_value=mock_list_item
        ) as mock_build, patch.object(utils, "get_torrent_meta", return_value={}):
            mock_api.return_value.get_torrent_info.return_value = {
                "title": "Mega Pack",
                "hash": "abc123",
                "file_stats": [
                    {"path": "10 Lives.mkv", "id": "0"},
                    {"path": ".pad/79716223", "id": "1"},
                    {"path": "100% Wolf.mkv", "id": "2"},
                    {"path": ".pad/51356901", "id": "3"},
                ],
            }
            mock_api.return_value.get_stream_url.return_value = "http://serve/url"

            utils.torrent_files({"info_hash": "abc123"})

            # Only the 2 .mkv files should produce list items, not the .pad files
            assert mock_build.call_count == 2
            labels = [call.args[0] for call in mock_build.call_args_list]
            assert labels == ["10 Lives.mkv", "100% Wolf.mkv"]
