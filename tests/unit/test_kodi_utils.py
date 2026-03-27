from unittest.mock import patch

from lib.utils.kodi import utils


def test_is_youtube_addon_enabled_returns_false_when_addon_is_absent():
    with patch.object(utils.xbmc, "getCondVisibility", return_value=False) as get_cond_visibility, patch.object(
        utils.xbmcaddon,
        "Addon",
    ) as addon_cls:
        assert utils.is_youtube_addon_enabled() is False

    get_cond_visibility.assert_called_once_with(
        f"System.HasAddon({utils.YOUTUBE_ADDON_ID})"
    )
    addon_cls.assert_not_called()


def test_is_youtube_addon_enabled_returns_true_when_addon_is_enabled():
    with patch.object(utils.xbmc, "getCondVisibility", return_value=True) as get_cond_visibility, patch.object(
        utils.xbmcaddon,
        "Addon",
        return_value=object(),
    ) as addon_cls:
        assert utils.is_youtube_addon_enabled() is True

    get_cond_visibility.assert_called_once_with(
        f"System.HasAddon({utils.YOUTUBE_ADDON_ID})"
    )
    addon_cls.assert_called_once_with(utils.YOUTUBE_ADDON_ID)


def test_is_youtube_addon_enabled_returns_false_when_addon_is_disabled():
    with patch.object(utils.xbmc, "getCondVisibility", return_value=True) as get_cond_visibility, patch.object(
        utils.xbmcaddon,
        "Addon",
        side_effect=RuntimeError,
    ) as addon_cls:
        assert utils.is_youtube_addon_enabled() is False

    get_cond_visibility.assert_called_once_with(
        f"System.HasAddon({utils.YOUTUBE_ADDON_ID})"
    )
    addon_cls.assert_called_once_with(utils.YOUTUBE_ADDON_ID)
