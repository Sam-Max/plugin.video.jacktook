import importlib
import sys
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
    ) as downloader_cls, patch.object(downloader.cancel_flag_cache, "set") as cache_set:
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
    )
    cache_set.assert_called_once_with("/downloads/Movie.mkv", False)
    downloader_instance.run.assert_called_once_with()
