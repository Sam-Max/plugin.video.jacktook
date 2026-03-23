from unittest.mock import patch

from lib.domain.torrent import TorrentStream
from lib.utils.general.utils import pre_process


def test_pre_process_excludes_unknown_sources_when_disabled():
    results = [
        TorrentStream(title="Movie.2024.1080p.WEB-DL", type="Torrent"),
        TorrentStream(title="Movie.2024.1080p.SomeWeirdTag", type="Torrent"),
    ]

    with patch("lib.utils.general.utils.get_setting") as get_setting, patch(
        "lib.utils.general.processors.get_setting"
    ) as processor_get_setting:
        get_setting.side_effect = lambda key, default=None: {
            "unknown_enabled": False,
            "unknown_quality_enabled": True,
            "bluray_hd_enabled": True,
            "web_hd_enabled": True,
            "dvd_tv_enabled": True,
            "cam_screener_enabled": True,
            "filter_size_enabled": False,
        }.get(key, default)
        processor_get_setting.side_effect = get_setting.side_effect

        filtered = pre_process(results, mode="movies", episode_name="", episode=0, season=0)

    assert [item.title for item in filtered] == ["Movie.2024.1080p.WEB-DL"]


def test_pre_process_keeps_known_source_even_with_unknown_quality():
    results = [
        TorrentStream(title="Movie.2024.WEB-DL", type="Torrent"),
        TorrentStream(title="Movie.2024.CustomSource", type="Torrent"),
    ]

    with patch("lib.utils.general.utils.get_setting") as get_setting, patch(
        "lib.utils.general.processors.get_setting"
    ) as processor_get_setting:
        get_setting.side_effect = lambda key, default=None: {
            "unknown_enabled": False,
            "unknown_quality_enabled": True,
            "bluray_hd_enabled": True,
            "web_hd_enabled": True,
            "dvd_tv_enabled": True,
            "cam_screener_enabled": True,
            "filter_size_enabled": False,
        }.get(key, default)
        processor_get_setting.side_effect = get_setting.side_effect

        filtered = pre_process(results, mode="movies", episode_name="", episode=0, season=0)

    assert [item.title for item in filtered] == ["Movie.2024.WEB-DL"]
    assert filtered[0].quality == "[B][COLOR yellow]N/A[/COLOR][/B]"


def test_pre_process_excludes_unknown_quality_when_disabled():
    results = [
        TorrentStream(title="Movie.2024.1080p.WEB-DL", type="Torrent"),
        TorrentStream(title="Movie.2024.WEB-DL", type="Torrent"),
    ]

    with patch("lib.utils.general.utils.get_setting") as get_setting, patch(
        "lib.utils.general.processors.get_setting"
    ) as processor_get_setting:
        get_setting.side_effect = lambda key, default=None: {
            "unknown_enabled": True,
            "unknown_quality_enabled": False,
            "bluray_hd_enabled": True,
            "web_hd_enabled": True,
            "dvd_tv_enabled": True,
            "cam_screener_enabled": True,
            "filter_size_enabled": False,
        }.get(key, default)
        processor_get_setting.side_effect = get_setting.side_effect

        filtered = pre_process(results, mode="movies", episode_name="", episode=0, season=0)

    assert [item.title for item in filtered] == ["Movie.2024.1080p.WEB-DL"]
