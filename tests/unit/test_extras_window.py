from unittest.mock import patch

from lib.gui.extras_window import ExtrasWindow


def test_extras_trailer_button_uses_play_trailer_route():
    window = ExtrasWindow(
        "extras.xml",
        "/tmp",
        item_information={
            "tmdb_id": "4604",
            "media_type": "tv",
            "title": "Smallville",
            "imdb_id": "tt0279600",
        },
    )

    with patch(
        "lib.gui.extras_window.build_url",
        return_value="plugin://plugin.video.jacktook/?action=play_trailer&tmdb_id=4604&media_type=tv&title=Smallville",
    ) as build_url_mock, patch.object(window, "close") as close_mock, patch("lib.gui.extras_window.execute_builtin") as execute_builtin:
        window._handle_click(11)

    build_url_mock.assert_called_once_with(
        "play_trailer",
        tmdb_id="4604",
        media_type="tv",
        title="Smallville",
    )
    close_mock.assert_called_once_with()
    execute_builtin.assert_called_once_with(
        "PlayMedia(plugin://plugin.video.jacktook/?action=play_trailer&tmdb_id=4604&media_type=tv&title=Smallville)"
    )
