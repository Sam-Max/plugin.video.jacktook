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
    get_rpdb_poster,
    build_media_metadata,
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


class TestGetRpdbPoster:
    def test_cache_hit_returns_cached_value(self):
        cached_url = "https://cdn.ratingposterdb.com/poster.jpg"
        with patch("lib.utils.general.utils.cache") as mock_cache:
            mock_cache.get.return_value = cached_url
            result = get_rpdb_poster("tt1234567", "test_key")
            assert result == cached_url
            mock_cache.get.assert_called_once_with("rpdb_poster|tt1234567")
            mock_cache.set.assert_not_called()

    def test_cache_miss_success_with_poster_field(self):
        rpdb_url = "https://cdn.ratingposterdb.com/poster.jpg"
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"poster": rpdb_url}

        with patch("lib.utils.general.utils.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch("requests.get", return_value=response) as mock_get:
                result = get_rpdb_poster("tt1234567", "test_key")
                assert result == rpdb_url
                mock_get.assert_called_once_with(
                    "https://api.ratingposterdb.com/test_key/imdb/tt1234567?lang=en",
                    timeout=10,
                )
                mock_cache.set.assert_called_once()
                call_args = mock_cache.set.call_args
                assert call_args[0][0] == "rpdb_poster|tt1234567"
                assert call_args[0][1] == rpdb_url

    def test_cache_miss_success_with_poster_large_field(self):
        rpdb_url = "https://cdn.ratingposterdb.com/poster_large.jpg"
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"poster_large": rpdb_url}

        with patch("lib.utils.general.utils.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch("requests.get", return_value=response):
                result = get_rpdb_poster("tt1234567", "test_key")
                assert result == rpdb_url

    def test_cache_miss_api_error_returns_none(self):
        import requests as req_mod

        with patch("lib.utils.general.utils.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch(
                "requests.get", side_effect=req_mod.exceptions.RequestException("timeout")
            ):
                result = get_rpdb_poster("tt1234567", "test_key")
                assert result is None
                mock_cache.set.assert_not_called()

    def test_cache_miss_non_200_status_returns_none(self):
        response = MagicMock()
        response.status_code = 403

        with patch("lib.utils.general.utils.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch("requests.get", return_value=response):
                result = get_rpdb_poster("tt1234567", "test_key")
                assert result is None
                mock_cache.set.assert_not_called()

    def test_cache_miss_empty_response_returns_none(self):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {}

        with patch("lib.utils.general.utils.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch("requests.get", return_value=response):
                result = get_rpdb_poster("tt1234567", "test_key")
                assert result is None


class TestBuildMediaMetadataRpdb:
    @staticmethod
    def _make_tmdb_details(poster_path="/tmdb_poster.jpg"):
        details = MagicMock()
        details.poster_path = poster_path
        details.overview = "Overview"
        details.title = "Title"
        details.name = ""
        details.original_title = "Original Title"
        details.original_name = ""
        details.release_date = "2023-01-01"
        details.runtime = 120
        details.vote_average = 7.5
        details.vote_count = 100
        details.popularity = 50
        details.backdrop_path = "/backdrop.jpg"
        return details

    def test_rpdb_enabled_overrides_poster(self):
        ids = {"tmdb_id": "123", "imdb_id": "tt1234567"}
        rpdb_url = "https://cdn.ratingposterdb.com/poster.jpg"

        with patch(
            "lib.utils.general.utils.get_setting_fresh",
            side_effect=lambda key, default=None: {
                "rpdb_enabled": True,
                "rpdb_api_key": "test_key",
            }.get(key, default),
        ):
            with patch(
                "lib.utils.general.utils.get_rpdb_poster", return_value=rpdb_url
            ):
                with patch(
                    "lib.clients.tmdb.utils.utils.get_tmdb_media_details",
                    return_value=self._make_tmdb_details(),
                ):
                    with patch(
                        "lib.utils.general.utils.get_fanart_details",
                        return_value={},
                    ):
                        metadata = build_media_metadata(ids, "movies")
                        assert metadata["poster"] == rpdb_url

    def test_rpdb_enabled_fallback_to_tmdb_when_rpdb_none(self):
        ids = {"tmdb_id": "123", "imdb_id": "tt1234567"}

        with patch(
            "lib.utils.general.utils.get_setting_fresh",
            side_effect=lambda key, default=None: {
                "rpdb_enabled": True,
                "rpdb_api_key": "test_key",
            }.get(key, default),
        ):
            with patch(
                "lib.utils.general.utils.get_rpdb_poster", return_value=None
            ):
                with patch(
                    "lib.clients.tmdb.utils.utils.get_tmdb_media_details",
                    return_value=self._make_tmdb_details(),
                ):
                    with patch(
                        "lib.utils.general.utils.get_fanart_details",
                        return_value={},
                    ):
                        metadata = build_media_metadata(ids, "movies")
                        assert "w780" in metadata["poster"]

    def test_rpdb_disabled_uses_tmdb_poster(self):
        ids = {"tmdb_id": "123", "imdb_id": "tt1234567"}

        with patch(
            "lib.utils.general.utils.get_setting_fresh",
            side_effect=lambda key, default=None: {
                "rpdb_enabled": False,
                "rpdb_api_key": "",
            }.get(key, default),
        ):
            with patch(
                "lib.utils.general.utils.get_rpdb_poster"
            ) as mock_get_rpdb:
                with patch(
                    "lib.clients.tmdb.utils.utils.get_tmdb_media_details",
                    return_value=self._make_tmdb_details(),
                ):
                    with patch(
                        "lib.utils.general.utils.get_fanart_details",
                        return_value={},
                    ):
                        metadata = build_media_metadata(ids, "movies")
                        mock_get_rpdb.assert_not_called()
                        assert "w780" in metadata["poster"]

    def test_rpdb_enabled_no_imdb_id_uses_tmdb_poster(self):
        ids = {"tmdb_id": "123"}

        with patch(
            "lib.utils.general.utils.get_setting_fresh",
            side_effect=lambda key, default=None: {
                "rpdb_enabled": True,
                "rpdb_api_key": "test_key",
            }.get(key, default),
        ):
            with patch(
                "lib.utils.general.utils.get_rpdb_poster"
            ) as mock_get_rpdb:
                with patch(
                    "lib.clients.tmdb.utils.utils.get_tmdb_media_details",
                    return_value=self._make_tmdb_details(),
                ):
                    with patch(
                        "lib.utils.general.utils.get_fanart_details",
                        return_value={},
                    ):
                        metadata = build_media_metadata(ids, "movies")
                        mock_get_rpdb.assert_not_called()
                        assert "w780" in metadata["poster"]
