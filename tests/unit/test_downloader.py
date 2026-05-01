import importlib
import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch


def _load_downloader_module():
    if "lib.downloader" in sys.modules:
        return importlib.reload(sys.modules["lib.downloader"])
    return importlib.import_module("lib.downloader")


def test_normalize_file_name_preserves_valid_video_extension():
    downloader = _load_downloader_module()

    assert downloader.normalize_file_name("Movie.mp4", "https://example.com/Movie.mkv") == "Movie.mp4"


def test_normalize_file_name_uses_url_extension_when_title_has_none():
    downloader = _load_downloader_module()

    assert (
        downloader.normalize_file_name(
            "Project Hail Mary",
            "https://example.com/files/Project%20Hail%20Mary.mkv",
        )
        == "Project Hail Mary.mkv"
    )


def test_normalize_file_name_ignores_tv_episode_like_suffix():
    downloader = _load_downloader_module()

    assert (
        downloader.normalize_file_name(
            "Game of Thrones.S01E01",
            "https://example.com/files/Game%20of%20Thrones.mkv",
        )
        == "Game of Thrones_S01E01.mkv"
    )


def test_handle_download_file_passes_url_to_normalizer():
    downloader = _load_downloader_module()

    downloader_instance = MagicMock()
    downloader_instance.is_cancelled = False

    with patch.object(downloader.os.path, "exists", return_value=True), patch.object(
        downloader, "normalize_file_name", return_value="Movie.mkv"
    ) as normalize_file_name, patch.object(
        downloader, "Downloader", return_value=downloader_instance
    ) as downloader_cls, patch.object(
        downloader, "DownloadManager"
    ) as mock_manager_cls, patch.object(downloader.cancel_flag_cache, "set") as cache_set:
        mock_manager = MagicMock()
        mock_manager.register.return_value = MagicMock()
        mock_manager_cls.return_value = mock_manager
        downloader.handle_download_file(
            {
                "destination": "/downloads",
                "file_name": "Movie",
                "url": "https://example.com/Movie.mkv",
            }
        )

    normalize_file_name.assert_called_once_with("Movie", "https://example.com/Movie.mkv")
    downloader_cls.assert_called_once_with(
        url="https://example.com/Movie.mkv",
        destination="/downloads",
        name="Movie.mkv",
        registry_id="/downloads/Movie.mkv",
    )
    cache_set.assert_called_once_with("/downloads/Movie.mkv", False)
    downloader_instance.run.assert_called_once_with()


# --- Tests for get_destination_path ---

def test_get_destination_path_flat_when_disabled():
    downloader = _load_downloader_module()

    with patch.object(downloader, "get_setting", side_effect=lambda key, default=False: False if key == "organize_downloads" else default), patch.object(
        downloader, "translatePath", return_value="/downloads"
    ), patch.object(downloader.xbmcvfs, "mkdirs") as mock_mkdirs:
        result = downloader.get_destination_path({"title": "Movie", "mode": "movies"})

    assert result == "/downloads"
    mock_mkdirs.assert_not_called()


def test_get_destination_path_movies_when_enabled():
    downloader = _load_downloader_module()

    with patch.object(
        downloader,
        "get_setting",
        side_effect=lambda key, default="": {
            "organize_downloads": True,
            "download_dir": "/downloads",
            "download_folder_movies": "Movies",
            "download_folder_tvshows": "TV Shows",
        }.get(key, default),
    ), patch.object(downloader, "translatePath", return_value="/downloads"), patch.object(
        downloader.xbmcvfs, "mkdirs"
    ) as mock_mkdirs:
        result = downloader.get_destination_path({"title": "Movie", "mode": "movies"})

    assert result == "/downloads/Movies"
    mock_mkdirs.assert_called_once_with("/downloads/Movies")


def test_get_destination_path_tv_when_enabled():
    downloader = _load_downloader_module()

    with patch.object(
        downloader,
        "get_setting",
        side_effect=lambda key, default="": {
            "organize_downloads": True,
            "download_dir": "/downloads",
            "download_folder_movies": "Movies",
            "download_folder_tvshows": "TV Shows",
        }.get(key, default),
    ), patch.object(downloader, "translatePath", return_value="/downloads"), patch.object(
        downloader.xbmcvfs, "mkdirs"
    ) as mock_mkdirs:
        result = downloader.get_destination_path(
            {
                "title": "Episode",
                "mode": "tv",
                "tv_data": {"name": "Breaking Bad", "season": 2},
            }
        )

    assert result == "/downloads/TV Shows/Breaking Bad/Season 02"
    mock_mkdirs.assert_called_once_with("/downloads/TV Shows/Breaking Bad/Season 02")


def test_get_destination_path_fallback_to_title_for_show_name():
    downloader = _load_downloader_module()

    with patch.object(
        downloader,
        "get_setting",
        side_effect=lambda key, default="": {
            "organize_downloads": True,
            "download_dir": "/downloads",
            "download_folder_movies": "Movies",
            "download_folder_tvshows": "TV Shows",
        }.get(key, default),
    ), patch.object(downloader, "translatePath", return_value="/downloads"), patch.object(
        downloader.xbmcvfs, "mkdirs"
    ):
        result = downloader.get_destination_path(
            {
                "title": "Some Show",
                "mode": "tv",
                "tv_data": {"season": 1},
            }
        )

    assert result == "/downloads/TV Shows/Some Show/Season 01"


# --- Tests for get_download_metadata ---

def test_get_download_metadata_returns_defaults_when_missing():
    downloader = _load_downloader_module()

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "video.mkv")
        result = downloader.get_download_metadata(path)

    assert result == {"status": "unknown", "progress": 0, "title": ""}


def test_get_download_metadata_reads_existing_json():
    downloader = _load_downloader_module()

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "video.mkv")
        meta_path = os.path.join(tmpdir, "video.mkv.jacktook.json")
        with open(meta_path, "w") as f:
            json.dump({"status": "paused", "progress": 42, "title": "Video"}, f)

        with patch.object(downloader.xbmcvfs, "exists", side_effect=lambda p: os.path.exists(p)), \
             patch.object(downloader, "open_file", side_effect=lambda p, m="r": open(p, m)):
            result = downloader.get_download_metadata(path)

    assert result == {"status": "paused", "progress": 42, "title": "Video"}


# --- Tests for handle_pause_download ---

def test_handle_pause_download_sets_cancel_flag_and_metadata():
    downloader = _load_downloader_module()

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "video.mkv")
        meta_path = os.path.join(tmpdir, "video.mkv.jacktook.json")
        with open(meta_path, "w") as f:
            json.dump({"status": "downloading", "progress": 50, "title": "Video"}, f)

        with patch.object(downloader.cancel_flag_cache, "set") as cache_set, \
             patch.object(downloader.xbmcvfs, "exists", side_effect=lambda p: os.path.exists(p)), \
             patch.object(downloader, "open_file", side_effect=lambda p, m="r": open(p, m)):
            downloader.handle_pause_download({"file_path": json.dumps(path)})

        cache_set.assert_called_once_with(path, True)
        with open(meta_path, "r") as f:
            meta = json.load(f)
        assert meta["status"] == "paused"


# --- Tests for resume_download ---

def test_resume_download_clears_flag_and_starts_downloader():
    downloader = _load_downloader_module()

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "video.mkv")
        meta_path = os.path.join(tmpdir, "video.mkv.jacktook.json")
        open(path, "a").close()
        with open(meta_path, "w") as f:
            json.dump(
                {"status": "paused", "progress": 50, "title": "Video", "url": "https://example.com/video.mkv"},
                f,
            )

        downloader_instance = MagicMock()
        with patch.object(downloader.cancel_flag_cache, "set") as cache_set, \
             patch.object(downloader, "Downloader", return_value=downloader_instance) as downloader_cls, \
             patch.object(downloader.xbmcvfs, "exists", side_effect=lambda p: os.path.exists(p)), \
             patch.object(downloader, "open_file", side_effect=lambda p, m="r": open(p, m)):
            downloader.resume_download({"file_path": json.dumps(path)})

        cache_set.assert_called_once_with(path, False)
        downloader_cls.assert_called_once_with(
            url="https://example.com/video.mkv",
            destination=os.path.dirname(path),
            name="video.mkv",
        )
        downloader_instance.run.assert_called_once_with()


# --- Tests for download_video with organization ---

def test_get_destination_path_tv_with_custom_folder_names():
    downloader = _load_downloader_module()

    with patch.object(
        downloader,
        "get_setting",
        side_effect=lambda key, default="": {
            "organize_downloads": True,
            "download_dir": "/downloads",
            "download_folder_movies": "Films",
            "download_folder_tvshows": "Series",
        }.get(key, default),
    ), patch.object(downloader, "translatePath", return_value="/downloads"), patch.object(
        downloader.xbmcvfs, "mkdirs"
    ):
        result = downloader.get_destination_path(
            {
                "title": "Episode",
                "mode": "tv",
                "tv_data": {"name": "Show", "season": 5},
            }
        )

    assert result == "/downloads/Series/Show/Season 05"


def test_get_download_metadata_handles_corrupt_json():
    downloader = _load_downloader_module()

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "video.mkv")
        meta_path = os.path.join(tmpdir, "video.mkv.jacktook.json")
        with open(meta_path, "w") as f:
            f.write("not json")

        result = downloader.get_download_metadata(path)

    assert result == {"status": "unknown", "progress": 0, "title": ""}


def test_download_video_uses_organized_destination():
    downloader = _load_downloader_module()

    with patch.object(
        downloader,
        "get_destination_path",
        return_value="/downloads/Movies",
    ) as mock_get_dest, patch.object(
        downloader, "handle_download_file"
    ) as mock_handle, patch.object(downloader, "normalize_file_name", return_value="Movie.mkv"):
        data = {"title": "Movie", "mode": "movies", "url": "https://example.com/Movie.mkv"}
        downloader.download_video({"data": json.dumps(data)})

    mock_get_dest.assert_called_once_with(data)
    mock_handle.assert_called_once_with(
        {"destination": "/downloads/Movies", "file_name": "Movie", "url": "https://example.com/Movie.mkv"}
    )


# --- Tests for Downloader registry integration ---

def test_downloader_accepts_registry_id():
    downloader = _load_downloader_module()

    dl = downloader.Downloader(
        url="https://example.com/Movie.mkv",
        destination="/downloads",
        name="Movie.mkv",
        registry_id="/downloads/Movie.mkv",
    )
    assert dl.registry_id == "/downloads/Movie.mkv"


def test_downloader_registry_id_defaults_to_none():
    downloader = _load_downloader_module()

    dl = downloader.Downloader(
        url="https://example.com/Movie.mkv",
        destination="/downloads",
        name="Movie.mkv",
    )
    assert dl.registry_id is None


def test_start_download_updates_registry_per_chunk():
    downloader = _load_downloader_module()

    from lib.download_manager import DownloadManager
    manager = DownloadManager()
    manager.clear()
    manager.register(name="Movie.mkv", dest_path="/downloads/Movie.mkv", url="https://example.com/Movie.mkv")

    dl = downloader.Downloader(
        url="https://example.com/Movie.mkv",
        destination="/downloads",
        name="Movie.mkv",
        registry_id="/downloads/Movie.mkv",
    )
    dl.file_size = 3 * 1024 * 1024  # 3 MB

    mock_response = MagicMock()
    mock_response.read.side_effect = [b"x" * (1024 * 1024), b"x" * (1024 * 1024), b"x" * (1024 * 1024), b""]
    mock_response.headers = {"Content-Length": str(3 * 1024 * 1024)}

    with tempfile.TemporaryDirectory() as tmpdir:
        dl.destination = tmpdir
        dl.dest_path = os.path.join(tmpdir, "Movie.mkv")
        dl.temp_path = dl.dest_path + ".part"
        dl.meta_path = dl.dest_path + ".jacktook.json"

        with patch.object(downloader, "KodiProgressHandler") as mock_handler_cls, patch.object(
            downloader, "urlopen", return_value=mock_response
        ), patch.object(downloader.xbmcvfs, "exists", return_value=False), patch.object(
            downloader.xbmcvfs, "rename"
        ):
            mock_handler = MagicMock()
            mock_handler_cls.return_value = mock_handler
            mock_handler.cancelled.return_value = False
            dl.monitor = MagicMock()
            dl.monitor.abortRequested.return_value = False
            dl._start_download()

    entry = manager.get_entry("/downloads/Movie.mkv")
    assert entry is not None
    assert entry.progress == 100
    assert entry.downloaded == 3 * 1024 * 1024
    assert entry.status == "completed"


def test_start_download_sets_registry_status_paused_on_cancel():
    downloader = _load_downloader_module()

    from lib.download_manager import DownloadManager
    manager = DownloadManager()
    manager.clear()
    manager.register(name="Movie.mkv", dest_path="/downloads/Movie.mkv", url="https://example.com/Movie.mkv")

    dl = downloader.Downloader(
        url="https://example.com/Movie.mkv",
        destination="/downloads",
        name="Movie.mkv",
        registry_id="/downloads/Movie.mkv",
    )
    dl.file_size = 10 * 1024 * 1024  # 10 MB

    mock_response = MagicMock()
    mock_response.read.side_effect = [b"x" * (1024 * 1024), b"x" * (1024 * 1024), b""]
    mock_response.headers = {"Content-Length": str(10 * 1024 * 1024)}

    with tempfile.TemporaryDirectory() as tmpdir:
        dl.destination = tmpdir
        dl.dest_path = os.path.join(tmpdir, "Movie.mkv")
        dl.temp_path = dl.dest_path + ".part"
        dl.meta_path = dl.dest_path + ".jacktook.json"

        with patch.object(downloader, "KodiProgressHandler") as mock_handler_cls, patch.object(
            downloader, "urlopen", return_value=mock_response
        ), patch.object(downloader.xbmcvfs, "exists", return_value=False), patch.object(
            downloader.xbmcvfs, "rename"
        ):
            mock_handler = MagicMock()
            mock_handler_cls.return_value = mock_handler
            # Cancel after first chunk
            call_count = [0]

            def cancelled_side_effect():
                call_count[0] += 1
                return call_count[0] > 1

            mock_handler.cancelled.side_effect = cancelled_side_effect
            dl.monitor = MagicMock()
            dl.monitor.abortRequested.return_value = False
            dl._start_download()

    entry = manager.get_entry("/downloads/Movie.mkv")
    assert entry is not None
    assert entry.status == "paused"


def test_start_download_respects_registry_cancel_flag():
    downloader = _load_downloader_module()

    from lib.download_manager import DownloadManager
    manager = DownloadManager()
    manager.clear()
    entry = manager.register(name="Movie.mkv", dest_path="/downloads/Movie.mkv", url="https://example.com/Movie.mkv")
    entry.cancel_flag = True

    dl = downloader.Downloader(
        url="https://example.com/Movie.mkv",
        destination="/downloads",
        name="Movie.mkv",
        registry_id="/downloads/Movie.mkv",
    )
    dl.file_size = 10 * 1024 * 1024

    mock_response = MagicMock()
    mock_response.read.side_effect = [b"x" * (1024 * 1024), b""]
    mock_response.headers = {"Content-Length": str(10 * 1024 * 1024)}

    with tempfile.TemporaryDirectory() as tmpdir:
        dl.destination = tmpdir
        dl.dest_path = os.path.join(tmpdir, "Movie.mkv")
        dl.temp_path = dl.dest_path + ".part"
        dl.meta_path = dl.dest_path + ".jacktook.json"

        with patch.object(downloader, "KodiProgressHandler") as mock_handler_cls, patch.object(
            downloader, "urlopen", return_value=mock_response
        ), patch.object(downloader.xbmcvfs, "exists", return_value=False), patch.object(
            downloader.xbmcvfs, "rename"
        ):
            mock_handler = MagicMock()
            mock_handler_cls.return_value = mock_handler
            mock_handler.cancelled.return_value = False
            dl.monitor = MagicMock()
            dl.monitor.abortRequested.return_value = False
            dl._start_download()

    entry = manager.get_entry("/downloads/Movie.mkv")
    assert entry is not None
    assert entry.status == "paused"


def test_start_download_sets_registry_status_error_on_exception():
    downloader = _load_downloader_module()

    from lib.download_manager import DownloadManager
    manager = DownloadManager()
    manager.clear()
    manager.register(name="Movie.mkv", dest_path="/downloads/Movie.mkv", url="https://example.com/Movie.mkv")

    dl = downloader.Downloader(
        url="https://example.com/Movie.mkv",
        destination="/downloads",
        name="Movie.mkv",
        registry_id="/downloads/Movie.mkv",
    )
    dl.file_size = 10 * 1024 * 1024

    with tempfile.TemporaryDirectory() as tmpdir:
        dl.destination = tmpdir
        dl.dest_path = os.path.join(tmpdir, "Movie.mkv")
        dl.temp_path = dl.dest_path + ".part"
        dl.meta_path = dl.dest_path + ".jacktook.json"

        with patch.object(downloader, "KodiProgressHandler") as mock_handler_cls, patch.object(
            downloader, "urlopen", side_effect=Exception("network error")
        ), patch.object(downloader.xbmcvfs, "exists", return_value=False):
            mock_handler = MagicMock()
            mock_handler_cls.return_value = mock_handler
            dl._start_download()

    entry = manager.get_entry("/downloads/Movie.mkv")
    assert entry is not None
    assert entry.status == "error"


def test_update_registry_calculates_speed_and_eta():
    downloader = _load_downloader_module()

    from lib.download_manager import DownloadManager
    manager = DownloadManager()
    manager.clear()
    manager.register(name="Movie.mkv", dest_path="/downloads/Movie.mkv", url="https://example.com/Movie.mkv")

    dl = downloader.Downloader(
        url="https://example.com/Movie.mkv",
        destination="/downloads",
        name="Movie.mkv",
        registry_id="/downloads/Movie.mkv",
    )
    dl.file_size = 10_000_000
    dl._start_time = 0

    with patch.object(downloader, "time") as mock_time:
        mock_time.time.return_value = 5
        dl._update_registry(downloaded=5_000_000, percent=50)

    entry = manager.get_entry("/downloads/Movie.mkv")
    assert entry.speed == 1_000_000
    assert entry.eta == 5


def test_update_registry_speed_zero_when_no_start_time():
    downloader = _load_downloader_module()

    from lib.download_manager import DownloadManager
    manager = DownloadManager()
    manager.clear()
    manager.register(name="Movie.mkv", dest_path="/downloads/Movie.mkv", url="https://example.com/Movie.mkv")

    dl = downloader.Downloader(
        url="https://example.com/Movie.mkv",
        destination="/downloads",
        name="Movie.mkv",
        registry_id="/downloads/Movie.mkv",
    )
    dl.file_size = 10_000_000
    dl._start_time = None

    dl._update_registry(downloaded=5_000_000, percent=50)

    entry = manager.get_entry("/downloads/Movie.mkv")
    assert entry.speed == 0
    assert entry.eta == 0


def test_update_registry_eta_zero_when_download_complete():
    downloader = _load_downloader_module()

    from lib.download_manager import DownloadManager
    manager = DownloadManager()
    manager.clear()
    manager.register(name="Movie.mkv", dest_path="/downloads/Movie.mkv", url="https://example.com/Movie.mkv")

    dl = downloader.Downloader(
        url="https://example.com/Movie.mkv",
        destination="/downloads",
        name="Movie.mkv",
        registry_id="/downloads/Movie.mkv",
    )
    dl.file_size = 10_000_000
    dl._start_time = 0

    with patch.object(downloader, "time") as mock_time:
        mock_time.time.return_value = 5
        dl._update_registry(downloaded=10_000_000, percent=100)

    entry = manager.get_entry("/downloads/Movie.mkv")
    assert entry.speed == 2_000_000
    assert entry.eta == 0
