from unittest.mock import patch

from lib.domain.torrent import TorrentStream
from lib.utils.general.processors import PreProcessBuilder


def test_extract_codec_hdr_sets_fields():
    results = [
        TorrentStream(title="Movie.2024.HEVC.DV-GROUP"),
        TorrentStream(title="Show.S01E01.H264-GROUP"),
        TorrentStream(title="Movie.2024.AV1-GROUP"),
    ]
    builder = PreProcessBuilder(results)
    builder.extract_codec_hdr()
    assert builder.results[0].codec == "HEVC"
    assert builder.results[0].hdr == "DV"
    assert builder.results[1].codec == "H.264"
    assert builder.results[1].hdr == ""
    assert builder.results[2].codec == "AV1"
    assert builder.results[2].hdr == ""


def test_filter_by_codec_all_enabled_keeps_everything():
    results = [
        TorrentStream(title="Movie.HEVC", codec="HEVC"),
        TorrentStream(title="Movie.H264", codec="H.264"),
        TorrentStream(title="Movie.AV1", codec="AV1"),
        TorrentStream(title="Movie.Unknown", codec=""),
    ]
    builder = PreProcessBuilder(results)

    with patch("lib.utils.general.processors.get_setting") as get_setting:
        get_setting.side_effect = lambda key, default=None: {
            "codec_hevc_enabled": True,
            "codec_av1_enabled": True,
            "codec_h264_enabled": True,
        }.get(key, default)
        builder.filter_by_codec()

    assert [r.title for r in builder.results] == [
        "Movie.HEVC",
        "Movie.H264",
        "Movie.AV1",
        "Movie.Unknown",
    ]


def test_filter_by_codec_disables_hevc():
    results = [
        TorrentStream(title="Movie.HEVC", codec="HEVC"),
        TorrentStream(title="Movie.H264", codec="H.264"),
        TorrentStream(title="Movie.AV1", codec="AV1"),
        TorrentStream(title="Movie.Unknown", codec=""),
    ]
    builder = PreProcessBuilder(results)

    with patch("lib.utils.general.processors.get_setting") as get_setting:
        get_setting.side_effect = lambda key, default=None: {
            "codec_hevc_enabled": False,
            "codec_av1_enabled": True,
            "codec_h264_enabled": True,
        }.get(key, default)
        builder.filter_by_codec()

    assert [r.title for r in builder.results] == [
        "Movie.H264",
        "Movie.AV1",
        "Movie.Unknown",
    ]


def test_filter_by_codec_disables_av1():
    results = [
        TorrentStream(title="Movie.HEVC", codec="HEVC"),
        TorrentStream(title="Movie.H264", codec="H.264"),
        TorrentStream(title="Movie.AV1", codec="AV1"),
        TorrentStream(title="Movie.Unknown", codec=""),
    ]
    builder = PreProcessBuilder(results)

    with patch("lib.utils.general.processors.get_setting") as get_setting:
        get_setting.side_effect = lambda key, default=None: {
            "codec_hevc_enabled": True,
            "codec_av1_enabled": False,
            "codec_h264_enabled": True,
        }.get(key, default)
        builder.filter_by_codec()

    assert [r.title for r in builder.results] == [
        "Movie.HEVC",
        "Movie.H264",
        "Movie.Unknown",
    ]


def test_filter_by_codec_disables_h264():
    results = [
        TorrentStream(title="Movie.HEVC", codec="HEVC"),
        TorrentStream(title="Movie.H264", codec="H.264"),
        TorrentStream(title="Movie.AV1", codec="AV1"),
        TorrentStream(title="Movie.Unknown", codec=""),
    ]
    builder = PreProcessBuilder(results)

    with patch("lib.utils.general.processors.get_setting") as get_setting:
        get_setting.side_effect = lambda key, default=None: {
            "codec_hevc_enabled": True,
            "codec_av1_enabled": True,
            "codec_h264_enabled": False,
        }.get(key, default)
        builder.filter_by_codec()

    assert [r.title for r in builder.results] == [
        "Movie.HEVC",
        "Movie.AV1",
        "Movie.Unknown",
    ]


def test_filter_by_hdr_all_enabled_keeps_everything():
    results = [
        TorrentStream(title="Movie.DV", hdr="DV"),
        TorrentStream(title="Movie.HDR10", hdr="HDR10"),
        TorrentStream(title="Movie.HDR", hdr="HDR"),
        TorrentStream(title="Movie.SDR", hdr=""),
    ]
    builder = PreProcessBuilder(results)

    with patch("lib.utils.general.processors.get_setting") as get_setting:
        get_setting.side_effect = lambda key, default=None: {
            "dolby_vision_enabled": True,
            "hdr10_enabled": True,
            "hdr_enabled": True,
        }.get(key, default)
        builder.filter_by_hdr()

    assert [r.title for r in builder.results] == [
        "Movie.DV",
        "Movie.HDR10",
        "Movie.HDR",
        "Movie.SDR",
    ]


def test_filter_by_hdr_disables_dolby_vision():
    results = [
        TorrentStream(title="Movie.DV", hdr="DV"),
        TorrentStream(title="Movie.HDR10", hdr="HDR10"),
        TorrentStream(title="Movie.HDR", hdr="HDR"),
        TorrentStream(title="Movie.SDR", hdr=""),
    ]
    builder = PreProcessBuilder(results)

    with patch("lib.utils.general.processors.get_setting") as get_setting:
        get_setting.side_effect = lambda key, default=None: {
            "dolby_vision_enabled": False,
            "hdr10_enabled": True,
            "hdr_enabled": True,
        }.get(key, default)
        builder.filter_by_hdr()

    assert [r.title for r in builder.results] == [
        "Movie.HDR10",
        "Movie.HDR",
        "Movie.SDR",
    ]


def test_filter_by_hdr_disables_hdr10():
    results = [
        TorrentStream(title="Movie.DV", hdr="DV"),
        TorrentStream(title="Movie.HDR10", hdr="HDR10"),
        TorrentStream(title="Movie.HDR", hdr="HDR"),
        TorrentStream(title="Movie.SDR", hdr=""),
    ]
    builder = PreProcessBuilder(results)

    with patch("lib.utils.general.processors.get_setting") as get_setting:
        get_setting.side_effect = lambda key, default=None: {
            "dolby_vision_enabled": True,
            "hdr10_enabled": False,
            "hdr_enabled": True,
        }.get(key, default)
        builder.filter_by_hdr()

    assert [r.title for r in builder.results] == [
        "Movie.DV",
        "Movie.HDR",
        "Movie.SDR",
    ]


def test_filter_by_hdr_disables_generic_hdr():
    results = [
        TorrentStream(title="Movie.DV", hdr="DV"),
        TorrentStream(title="Movie.HDR10", hdr="HDR10"),
        TorrentStream(title="Movie.HDR", hdr="HDR"),
        TorrentStream(title="Movie.SDR", hdr=""),
    ]
    builder = PreProcessBuilder(results)

    with patch("lib.utils.general.processors.get_setting") as get_setting:
        get_setting.side_effect = lambda key, default=None: {
            "dolby_vision_enabled": True,
            "hdr10_enabled": True,
            "hdr_enabled": False,
        }.get(key, default)
        builder.filter_by_hdr()

    assert [r.title for r in builder.results] == [
        "Movie.DV",
        "Movie.HDR10",
        "Movie.SDR",
    ]
