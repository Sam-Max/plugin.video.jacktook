from lib.utils.parsers.title_parser import extract_codec_hdr, parse_title_info


def test_parse_title_info_complex():
    title = "Movie.Name.2024.2160p.REPACK.HEVC.DV.HDR10.Atmos.TrueHD.7.1-GROUP"
    info = parse_title_info(title)
    assert "HEVC" in info["codec"]
    assert "ATMOS" in info["audio"]
    assert "DV" in info["hdr"]
    assert "GROUP" in info["release_group"]


def test_parse_title_info_simple():
    title = "Show.S01E01.1080p.H264-EVO"
    info = parse_title_info(title)
    assert "H.264" in info["codec"]
    assert info["release_group"] == "EVO"


def test_parse_title_info_av1():
    title = "Movie.2024.2160p.AV1.DDP5.1-GROUP"
    info = parse_title_info(title)
    assert "AV1" in info["codec"]


def test_parse_title_info_release_group_from_leading_brackets():
    assert parse_title_info("[Judas] Show - 01 [1080p].mkv")["release_group"] == "Judas"
    assert parse_title_info("[Erai-Raws] Show - 01 [1080p]")["release_group"] == "Erai-Raws"


def test_parse_title_info_release_group_from_suffix_with_extension():
    assert parse_title_info("Show.S01E01.1080p-ERai-Raws.mkv")["release_group"] == "ERai-Raws"


def test_parse_title_info_release_group_rejects_ambiguous_or_technical_tags():
    assert parse_title_info("[Judas][Erai-Raws] Show - 01")["release_group"] == ""
    assert parse_title_info("Show.S01E01.1080p.WEB-DL.mkv")["release_group"] == ""
    assert parse_title_info("Show.S01E01.1080p")["release_group"] == ""


def test_extract_codec_hdr_hevc():
    codec, hdr = extract_codec_hdr("Movie.2024.2160p.HEVC.DV-GROUP")
    assert codec == "HEVC"
    assert hdr == "DV"


def test_extract_codec_hdr_av1():
    codec, hdr = extract_codec_hdr("Movie.2024.2160p.AV1-GROUP")
    assert codec == "AV1"
    assert hdr == ""


def test_extract_codec_hdr_h264():
    codec, hdr = extract_codec_hdr("Show.S01E01.1080p.H264-GROUP")
    assert codec == "H.264"
    assert hdr == ""


def test_extract_codec_hdr_hdr10_plus():
    codec, hdr = extract_codec_hdr("Movie.2024.HDR10+.HEVC-GROUP")
    assert codec == "HEVC"
    assert hdr == "HDR10+"


def test_extract_codec_hdr_hdr10():
    codec, hdr = extract_codec_hdr("Movie.2024.HDR10.HEVC-GROUP")
    assert codec == "HEVC"
    assert hdr == "HDR10"


def test_extract_codec_hdr_generic_hdr():
    codec, hdr = extract_codec_hdr("Movie.2024.HDR.H264-GROUP")
    assert codec == "H.264"
    assert hdr == "HDR"


def test_extract_codec_hdr_empty():
    codec, hdr = extract_codec_hdr("Movie.2024.WEB-DL-GROUP")
    assert codec == ""
    assert hdr == ""


def test_extract_codec_hdr_none():
    codec, hdr = extract_codec_hdr("")
    assert codec == ""
    assert hdr == ""
