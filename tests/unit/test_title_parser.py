import pytest
from lib.utils.parsers.title_parser import parse_title_info

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
