import pytest
from lib.utils.general.utils import (
    is_url,
    is_magnet_link,
    info_hash_to_magnet,
    supported_video_extensions,
    extract_publish_date,
    extract_release_group,
    unicode_flag_to_country_code,
    is_video,
    get_random_color,
)


def test_is_url():
    assert is_url("http://example.com") is not None
    assert is_url("https://example.com/path?query=1") is not None
    assert is_url("ftp://example.com") is not None
    assert not is_url("not a url")
    assert not is_url("")


def test_is_magnet_link():
    magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678"
    assert is_magnet_link(magnet) == magnet
    assert is_magnet_link("http://example.com") is None
    assert is_magnet_link("not a magnet") is None


def test_info_hash_to_magnet():
    info_hash = "1234567890abcdef1234567890abcdef12345678"
    magnet = info_hash_to_magnet(info_hash)
    assert info_hash in magnet
    assert magnet.startswith("magnet:?xt=urn:btih:")


def test_supported_video_extensions():
    exts = supported_video_extensions()
    assert isinstance(exts, (list, tuple))
    assert ".mp4" in exts
    assert ".mkv" in exts
    assert ".avi" in exts


def test_extract_publish_date():
    assert extract_publish_date("2023-10-27") == "2023-10-27"
    assert extract_publish_date("Released on 2022-01-01") == "2022-01-01"
    assert extract_publish_date("NoDate") == ""


def test_extract_release_group():
    assert extract_release_group("Movie.Title.2023.1080p-Groupname") == "Groupname"
    assert extract_release_group("[Groupname] Movie Title") == "Groupname"
    assert extract_release_group("Movie.Title.mkv") == ""
    assert extract_release_group(None) == ""


def test_unicode_flag_to_country_code():
    # US Flag 🇺🇸 -> us
    assert unicode_flag_to_country_code("🇺🇸") == "us"
    # GB Flag 🇬🇧 -> gb
    assert unicode_flag_to_country_code("🇬🇧") == "gb"
    # Invalid length
    assert unicode_flag_to_country_code("ABC") == "Invalid flag Unicode"


def test_is_video():
    assert is_video("movie.mp4") is True
    assert is_video("show.mkv") is True
    assert is_video("document.txt") is False
    assert is_video("archive.zip") is False


def test_get_random_color():
    color = get_random_color("Netflix")
    # Expected format: [B][COLOR FFRRGGBB]Netflix[/COLOR][/B]
    assert color.startswith("[B][COLOR FF")
    assert color.endswith("]Netflix[/COLOR][/B]")
