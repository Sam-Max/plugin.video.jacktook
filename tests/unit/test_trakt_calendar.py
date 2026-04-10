from unittest.mock import MagicMock, patch

from lib.clients.trakt.trakt import TraktPresentation


def test_show_calendar_items_resolves_tmdb_id_from_tvdb_and_formats_title():
    fake_item = MagicMock()
    fake_info_tag = MagicMock()
    fake_item.getVideoInfoTag.return_value = fake_info_tag

    with patch("lib.clients.trakt.trakt.make_list_item", return_value=fake_item), patch(
        "lib.clients.trakt.trakt.TraktPresentation._resolve_media_ids",
        return_value={"tmdb_id": "123", "tvdb_id": "456", "imdb_id": "tt789"},
    ), patch("lib.clients.trakt.trakt.tmdb_get", return_value={}), patch(
        "lib.clients.trakt.trakt.set_media_infoTag"
    ), patch("lib.clients.trakt.trakt.add_kodi_dir_item") as add_dir_item:
        TraktPresentation.show_calendar_items(
            {
                "show": {"title": "Demo Show", "ids": {"tvdb": 456}},
                "episode": {"title": "Pilot", "season": 1, "number": 2},
                "first_aired": "2026-03-13T20:00:00.000Z",
            }
        )

    assert fake_item.setLabel.call_args.args[0] == "2026-03-13 | Demo Show - S01E02 - Pilot"
    assert "show_seasons_details" not in add_dir_item.call_args.kwargs["url"]
    assert add_dir_item.call_args.kwargs["is_folder"] is True


def test_show_calendar_items_skips_incomplete_entries():
    with patch("lib.clients.trakt.trakt.make_list_item") as list_item, patch(
        "lib.clients.trakt.trakt.add_kodi_dir_item"
    ) as add_dir_item:
        TraktPresentation.show_calendar_items(
            {
                "show": {"title": "Demo Show", "ids": {"tmdb": 123}},
                "episode": {"title": "Pilot", "season": None, "number": 2},
            }
        )

    list_item.assert_not_called()
    add_dir_item.assert_not_called()
