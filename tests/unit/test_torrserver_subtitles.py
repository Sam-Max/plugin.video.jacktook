import importlib
import json
import sys
from unittest.mock import MagicMock, patch


def _load_torrserver_utils():
    if "lib.utils.torrent.torrserver_utils" in sys.modules:
        return importlib.reload(sys.modules["lib.utils.torrent.torrserver_utils"])
    return importlib.import_module("lib.utils.torrent.torrserver_utils")


class TestDownloadTorrentSubtitles:
    def test_calls_subtitle_manager_with_imdb_id(self):
        module = _load_torrserver_utils()
        params = {
            "hash": "abc123",
            "meta": json.dumps({"title": "Test Movie", "ids": {"imdb_id": "tt123"}}),
        }

        with patch.object(module, "SubtitleManager") as MockManager, \
              patch.object(module, "notification") as mock_notification, \
              patch.object(module, "ADDON_PROFILE_PATH", "/addon/profile"), \
              patch.object(module.os.path, "exists", return_value=True), \
              patch.object(module, "get_torrserver_api") as mock_api, \
              patch.object(module.xbmcgui, "ListItem") as MockListItem, \
              patch.object(module.xbmc, "Player") as MockPlayer:
            mock_manager = MagicMock()
            mock_manager.fetch_subtitles.return_value = ["/path/to/sub.srt"]
            mock_manager.last_fetch_status = None
            MockManager.return_value = mock_manager
            mock_api.return_value.get_torrent_info.return_value = {
                "file_stats": [{"path": "movie.mkv", "id": "1"}]
            }
            mock_listitem = MagicMock()
            MockListItem.return_value = mock_listitem
            mock_player = MagicMock()
            MockPlayer.return_value = mock_player

            module.download_torrent_subtitles(params)

            MockManager.assert_called_once_with(
                data={"title": "Test Movie", "mode": "movies", "ids": {"imdb_id": "tt123", "tmdb_id": "", "tvdb_id": "", "original_id": ""}, "tv_data": {}},
                notification=module.notification,
            )
            mock_manager.fetch_subtitles.assert_called_once_with(
                auto_select=False, folder_path="/addon/profile/subtitles/abc123"
            )
            mock_notification.assert_called_once_with("Subtitles downloaded successfully")
            playback_url = "plugin://plugin.video.jacktorr/buffer_and_play?info_hash=abc123&file_id=1&path=movie.mkv"
            MockListItem.assert_called_once_with(label="Test Movie", path=playback_url)
            mock_listitem.setSubtitles.assert_called_once_with(["/path/to/sub.srt"])
            mock_player.play.assert_called_once_with(playback_url, mock_listitem)

    def test_notifies_when_no_subtitles_found(self):
        module = _load_torrserver_utils()
        params = {
            "hash": "abc123",
            "meta": json.dumps({"title": "Test Movie", "ids": {"imdb_id": "tt123"}}),
        }

        with patch.object(module, "SubtitleManager") as MockManager, \
             patch.object(module, "notification") as mock_notification:
            mock_manager = MagicMock()
            mock_manager.fetch_subtitles.return_value = None
            mock_manager.last_fetch_status = "not_found"
            MockManager.return_value = mock_manager

            module.download_torrent_subtitles(params)

            mock_notification.assert_called_once_with(module.translation(90252))

    def test_title_fallback_used_when_no_imdb_id(self):
        module = _load_torrserver_utils()
        params = {
            "hash": "abc123",
            "meta": json.dumps({"title": "Test Movie"}),
        }

        with patch.object(module, "SubtitleManager") as MockManager, \
             patch.object(module, "notification") as mock_notification, \
             patch.object(module, "ADDON_PROFILE_PATH", "/addon/profile"), \
             patch.object(module.os.path, "exists", return_value=True):
            mock_manager = MagicMock()
            mock_manager.fetch_subtitles.return_value = None
            mock_manager.last_fetch_status = "no_imdb"
            MockManager.return_value = mock_manager

            module.download_torrent_subtitles(params)

            MockManager.assert_called_once_with(
                data={"title": "Test Movie", "mode": "movies", "ids": {"tmdb_id": "", "tvdb_id": "", "imdb_id": "", "original_id": ""}, "tv_data": {}},
                notification=module.notification,
            )
            mock_manager.fetch_subtitles.assert_called_once_with(
                auto_select=False, folder_path="/addon/profile/subtitles/abc123"
            )
            mock_notification.assert_called_once_with(module.translation(90299))

    def test_aborts_when_no_imdb_id_and_no_title(self):
        module = _load_torrserver_utils()
        params = {
            "hash": "abc123",
            "meta": json.dumps({}),
        }

        with patch.object(module, "SubtitleManager") as MockManager, \
             patch.object(module, "notification") as mock_notification:
            module.download_torrent_subtitles(params)

            MockManager.assert_not_called()
            mock_notification.assert_called_once_with("Insufficient metadata")


class TestDownloadAndPlaySubtitles:
    def test_plays_video_with_subtitles(self):
        module = _load_torrserver_utils()
        params = {
            "hash": "abc123",
            "file_id": "1",
            "path": "movie.mkv",
            "meta": json.dumps({"title": "Test Movie", "ids": {"imdb_id": "tt123"}}),
        }

        with patch.object(module, "SubtitleManager") as MockManager, \
             patch.object(module, "get_setting", return_value=False), \
             patch.object(module.xbmcgui, "ListItem") as MockListItem, \
             patch.object(module.xbmc, "Player") as MockPlayer, \
             patch.object(module, "notification") as mock_notification:
            mock_manager = MagicMock()
            mock_manager.fetch_subtitles.return_value = ["/path/to/sub.srt"]
            mock_manager.last_fetch_status = None
            MockManager.return_value = mock_manager

            mock_player = MagicMock()
            MockPlayer.return_value = mock_player
            mock_listitem = MagicMock()
            MockListItem.return_value = mock_listitem

            module.download_and_play_subtitles(params)

            playback_url = "plugin://plugin.video.jacktorr/buffer_and_play?info_hash=abc123&file_id=1&path=movie.mkv"
            MockListItem.assert_called_once_with(label="Test Movie", path=playback_url)
            mock_listitem.setSubtitles.assert_called_once_with(["/path/to/sub.srt"])
            mock_player.play.assert_called_once_with(
                playback_url, mock_listitem
            )
            mock_notification.assert_not_called()

    def test_uses_subtitle_paths_returned_by_manager_without_second_translation_prompt(self):
        module = _load_torrserver_utils()
        params = {
            "hash": "abc123",
            "file_id": "1",
            "path": "movie.mkv",
            "meta": json.dumps({"title": "Test Movie", "ids": {"imdb_id": "tt123"}}),
        }

        with patch.object(module, "SubtitleManager") as MockManager, \
             patch.object(module, "DeepLTranslator") as MockTranslator, \
             patch.object(module, "get_setting", return_value=True), \
             patch.object(module.xbmcgui.Dialog, "yesno", return_value=True), \
             patch.object(module.xbmcgui, "ListItem") as MockListItem, \
             patch.object(module.xbmc, "Player") as MockPlayer, \
             patch.object(module, "notification") as mock_notification:
            mock_manager = MagicMock()
            mock_manager.fetch_subtitles.return_value = ["/path/to/translated.srt"]
            MockManager.return_value = mock_manager

            mock_player = MagicMock()
            MockPlayer.return_value = mock_player
            mock_listitem = MagicMock()
            MockListItem.return_value = mock_listitem

            module.download_and_play_subtitles(params)

            mock_manager.fetch_subtitles.assert_called_once_with(auto_select=False)
            MockTranslator.assert_not_called()
            mock_listitem.setSubtitles.assert_called_once_with(["/path/to/translated.srt"])

    def test_deepL_no_uses_original_subtitles(self):
        module = _load_torrserver_utils()
        params = {
            "hash": "abc123",
            "file_id": "1",
            "path": "movie.mkv",
            "meta": json.dumps({"title": "Test Movie", "ids": {"imdb_id": "tt123"}}),
        }

        with patch.object(module, "SubtitleManager") as MockManager, \
             patch.object(module, "DeepLTranslator") as MockTranslator, \
             patch.object(module, "get_setting", return_value=True), \
             patch.object(module.xbmcgui.Dialog, "yesno", return_value=False), \
             patch.object(module.xbmcgui, "ListItem") as MockListItem, \
             patch.object(module.xbmc, "Player") as MockPlayer, \
             patch.object(module, "notification") as mock_notification:
            mock_manager = MagicMock()
            mock_manager.fetch_subtitles.return_value = ["/path/to/sub.srt"]
            MockManager.return_value = mock_manager

            mock_player = MagicMock()
            MockPlayer.return_value = mock_player
            mock_listitem = MagicMock()
            MockListItem.return_value = mock_listitem

            module.download_and_play_subtitles(params)

            MockTranslator.assert_not_called()
            mock_listitem.setSubtitles.assert_called_once_with(["/path/to/sub.srt"])

    def test_no_results_notifies_and_does_not_play(self):
        module = _load_torrserver_utils()
        params = {
            "hash": "abc123",
            "file_id": "1",
            "path": "movie.mkv",
            "meta": json.dumps({"title": "Test Movie", "ids": {"imdb_id": "tt123"}}),
        }

        with patch.object(module, "SubtitleManager") as MockManager, \
             patch.object(module, "get_torrserver_api") as mock_api, \
             patch.object(module.xbmcgui, "ListItem") as MockListItem, \
             patch.object(module.xbmc, "Player") as MockPlayer, \
             patch.object(module, "notification") as mock_notification:
            mock_manager = MagicMock()
            mock_manager.fetch_subtitles.return_value = None
            mock_manager.last_fetch_status = "not_found"
            MockManager.return_value = mock_manager

            module.download_and_play_subtitles(params)

            MockListItem.assert_not_called()
            MockPlayer.assert_not_called()
            mock_notification.assert_called_once_with(module.translation(90252))

    def test_does_not_run_deepl_translation_twice_after_manager_fetch(self):
        module = _load_torrserver_utils()
        params = {
            "hash": "abc123",
            "file_id": "1",
            "path": "movie.mkv",
            "meta": json.dumps({"title": "Test Movie", "ids": {"imdb_id": "tt123"}}),
        }

        with patch.object(module, "SubtitleManager") as MockManager, \
             patch.object(module, "DeepLTranslator") as MockTranslator, \
             patch.object(module, "get_setting", return_value=True), \
             patch.object(module.xbmcgui.Dialog, "yesno", return_value=True) as yesno, \
             patch.object(module.xbmcgui, "ListItem") as MockListItem, \
             patch.object(module.xbmc, "Player") as MockPlayer, \
             patch.object(module, "notification") as mock_notification, \
             patch.object(module, "kodilog"):
            mock_manager = MagicMock()
            mock_manager.fetch_subtitles.return_value = ["/path/to/sub.srt"]
            MockManager.return_value = mock_manager

            mock_player = MagicMock()
            MockPlayer.return_value = mock_player
            mock_listitem = MagicMock()
            MockListItem.return_value = mock_listitem

            module.download_and_play_subtitles(params)

            mock_listitem.setSubtitles.assert_called_once_with(["/path/to/sub.srt"])
            MockTranslator.assert_not_called()
            yesno.assert_not_called()
            mock_notification.assert_not_called()


class TestTorrentMetadataCache:
    def test_save_and_get_torrent_meta_normalizes_hash_case(self):
        module = _load_torrserver_utils()
        meta = {"title": "Test Movie", "ids": {"imdb_id": "tt123"}}

        stored = {}

        def fake_set(key, value, expires=None):
            stored[key] = value

        def fake_get(key):
            return stored.get(key)

        with patch.object(module.cache, "set", side_effect=fake_set), \
             patch.object(module.cache, "get", side_effect=fake_get), \
             patch.object(module, "kodilog"):
            module.save_torrent_meta("ABC123", meta)
            result = module.get_torrent_meta("abc123")

        assert result == meta
        assert stored == {"torrent_meta:abc123": meta}

    def test_get_torrent_meta_strips_hash_whitespace(self):
        module = _load_torrserver_utils()
        meta = {"title": "Test Movie", "ids": {"imdb_id": "tt123"}}

        with patch.object(module.cache, "get", return_value=meta) as mock_get, \
             patch.object(module, "kodilog"):
            result = module.get_torrent_meta("  ABC123  ")

        assert result == meta
        mock_get.assert_called_once_with("torrent_meta:abc123")
