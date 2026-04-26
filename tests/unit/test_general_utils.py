import pytest
from unittest.mock import MagicMock, patch
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
    format_season_episode,
    get_image_size,
    set_listitem_artwork,
    TMDB_IMAGE_SIZES,
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


@pytest.mark.parametrize(
    "season, episode, expected",
    [
        (1, 2, "S01E02"),
        ("1", "2", "S01E02"),
        ("01", "02", "S01E02"),
        ("special", "finale", "SspecialEfinale"),
        (None, "2", "E02"),
        ("3", None, "S03"),
        ("", "", ""),
    ],
)
def test_format_season_episode(season, episode, expected):
    assert format_season_episode(season, episode) == expected


class TestGetImageSize:
    @pytest.mark.parametrize(
        "setting_value, expected_sizes",
        [
            ("0", TMDB_IMAGE_SIZES["low"]),
            ("1", TMDB_IMAGE_SIZES["medium"]),
            ("2", TMDB_IMAGE_SIZES["high"]),
            ("3", TMDB_IMAGE_SIZES["original"]),
        ],
    )
    def test_maps_setting_to_tier(self, setting_value, expected_sizes):
        with patch(
            "lib.utils.general.utils.get_setting_fresh", return_value=setting_value
        ):
            for image_type in ("poster", "thumb", "profile", "fanart"):
                assert get_image_size(image_type) == expected_sizes[image_type]

    def test_invalid_setting_defaults_to_high(self):
        with patch(
            "lib.utils.general.utils.get_setting_fresh", return_value="99"
        ):
            assert get_image_size("poster") == TMDB_IMAGE_SIZES["high"]["poster"]
            assert get_image_size("fanart") == TMDB_IMAGE_SIZES["high"]["fanart"]

    def test_unknown_image_type_returns_empty_string(self):
        with patch(
            "lib.utils.general.utils.get_setting_fresh", return_value="2"
        ):
            assert get_image_size("unknown_type") == ""


class TestSetListitemArtwork:
    def _make_mock_item(self):
        item = MagicMock()
        item.setArt = MagicMock()
        return item

    def _extract_url(self, call_args, key):
        art_dict = call_args[0][0]
        return art_dict.get(key, "")

    @pytest.mark.parametrize(
        "setting_value, poster_size, fanart_size",
        [
            ("0", "w185", "w300"),
            ("1", "w342", "w780"),
            ("2", "w780", "w1280"),
            ("3", "original", "original"),
        ],
    )
    def test_uses_resolution_tier(self, setting_value, poster_size, fanart_size):
        item = self._make_mock_item()
        data = {
            "poster_path": "/poster.jpg",
            "backdrop_path": "/backdrop.jpg",
        }
        with patch(
            "lib.utils.general.utils.get_setting_fresh", return_value=setting_value
        ):
            set_listitem_artwork(item, data, {})

        assert item.setArt.called
        art_call = item.setArt.call_args
        assert poster_size in self._extract_url(art_call, "poster")
        assert fanart_size in self._extract_url(art_call, "fanart")
        assert poster_size in self._extract_url(art_call, "thumb")

    def test_falls_back_when_no_paths(self):
        item = self._make_mock_item()
        data = {}
        with patch(
            "lib.utils.general.utils.get_setting_fresh", return_value="2"
        ):
            set_listitem_artwork(item, data, {})

        assert item.setArt.called
        art_call = item.setArt.call_args
        assert self._extract_url(art_call, "poster") == ""
        assert self._extract_url(art_call, "fanart") == ""
