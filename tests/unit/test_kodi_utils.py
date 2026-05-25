import pytest
from unittest.mock import patch

from lib.utils.kodi import utils


def test_is_youtube_addon_enabled_returns_false_when_addon_is_absent():
    with patch.object(
        utils.xbmc, "getCondVisibility", return_value=False
    ) as get_cond_visibility, patch.object(
        utils.xbmcaddon,
        "Addon",
    ) as addon_cls:
        assert utils.is_youtube_addon_enabled() is False

    get_cond_visibility.assert_called_once_with(f"System.HasAddon({utils.YOUTUBE_ADDON_ID})")
    addon_cls.assert_not_called()


def test_is_youtube_addon_enabled_returns_true_when_addon_is_enabled():
    with patch.object(
        utils.xbmc, "getCondVisibility", return_value=True
    ) as get_cond_visibility, patch.object(
        utils.xbmcaddon,
        "Addon",
        return_value=object(),
    ) as addon_cls:
        assert utils.is_youtube_addon_enabled() is True

    get_cond_visibility.assert_called_once_with(f"System.HasAddon({utils.YOUTUBE_ADDON_ID})")
    addon_cls.assert_called_once_with(utils.YOUTUBE_ADDON_ID)


def test_is_youtube_addon_enabled_returns_false_when_addon_is_disabled():
    with patch.object(
        utils.xbmc, "getCondVisibility", return_value=True
    ) as get_cond_visibility, patch.object(
        utils.xbmcaddon,
        "Addon",
        side_effect=RuntimeError,
    ) as addon_cls:
        assert utils.is_youtube_addon_enabled() is False

    get_cond_visibility.assert_called_once_with(f"System.HasAddon({utils.YOUTUBE_ADDON_ID})")
    addon_cls.assert_called_once_with(utils.YOUTUBE_ADDON_ID)


@pytest.mark.parametrize(
    ("input_str", "expected"),
    [
        # Standard English units
        ("1 GB", 1 * 1024**3),
        ("2.5 GB", int(2.5 * 1024**3)),
        ("500 MB", 500 * 1024**2),
        ("100 KB", 100 * 1024),
        ("42 B", 42),
        # Case insensitivity
        ("1.5 gb", int(1.5 * 1024**3)),
        ("200 mb", 200 * 1024**2),
        ("50 kb", 50 * 1024),
        # European units (Go = GB, Mo = MB, Ko = KB)
        ("1 Go", 1 * 1024**3),
        ("1.5 Go", int(1.5 * 1024**3)),
        ("500 Mo", 500 * 1024**2),
        ("100 Ko", 100 * 1024),
        # Case insensitivity for European units
        ("2 go", 2 * 1024**3),
        ("300 mo", 300 * 1024**2),
        ("75 ko", 75 * 1024),
        # European decimal comma → normalised to dot
        ("1,5 GB", int(1.5 * 1024**3)),
        ("2,5 Go", int(2.5 * 1024**3)),
        ("500,5 MB", int(500.5 * 1024**2)),
        # Edge cases
        ("0 GB", 0),
        ("0 MB", 0),
        ("0 B", 0),
        # Precision edge case – int truncation, not rounding
        ("1.9 GB", int(1.9 * 1024**3)),
    ],
)
def test_convert_size_to_bytes(input_str, expected):
    assert utils.convert_size_to_bytes(input_str) == expected


@pytest.mark.parametrize(
    ("input_str",),
    [
        ("",),
        ("not a size",),
        ("ABC",),
        ("1.5",),  # missing unit
    ],
)
def test_convert_size_to_bytes_invalid(input_str):
    assert utils.convert_size_to_bytes(input_str) == 0
