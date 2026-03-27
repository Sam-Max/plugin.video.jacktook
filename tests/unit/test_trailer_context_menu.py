from urllib.parse import parse_qs, urlparse
from unittest.mock import MagicMock, patch

from lib.clients.trakt.trakt import BaseTraktClient
from lib.clients.tmdb.base import BaseTmdbClient
from lib.clients.tmdb.utils.utils import (
    add_tmdb_movie_context_menu,
    add_tmdb_show_context_menu,
)


TRAILER_LABEL = "Play Trailer"


def _get_trailer_menu_item(menu):
    for label, command in menu:
        if label == TRAILER_LABEL:
            return label, command
    return None


def _parse_playmedia_command(command):
    url = command[len("PlayMedia(") : -1]
    query = parse_qs(urlparse(url).query)
    return {
        "action": query["action"][0],
        "media_type": query["media_type"][0],
        "tmdb_id": query.get("tmdb_id", [None])[0],
        "yt_id": query.get("yt_id", [None])[0],
        "youtube_url": query.get("youtube_url", [None])[0],
        "title": query.get("title", [None])[0],
    }


def test_movie_context_menu_contains_play_trailer_when_tmdb_id_exists():
    with patch("lib.clients.tmdb.utils.utils.translation", side_effect=lambda value: TRAILER_LABEL if value == 90672 else f"t-{value}"):
        menu = add_tmdb_movie_context_menu(
            mode="movies",
            media_type="movie",
            title="Demo Movie",
            ids={"tmdb_id": 550},
        )

    trailer_item = _get_trailer_menu_item(menu)

    assert trailer_item is not None
    assert _parse_playmedia_command(trailer_item[1]) == {
        "action": "play_trailer",
        "media_type": "movie",
        "tmdb_id": "550",
        "yt_id": None,
        "youtube_url": None,
        "title": "Demo Movie",
    }


def test_movie_context_menu_hides_play_trailer_without_tmdb_or_youtube_metadata():
    with patch("lib.clients.tmdb.utils.utils.translation", side_effect=lambda value: TRAILER_LABEL if value == 90672 else f"t-{value}"):
        menu = add_tmdb_movie_context_menu(
            mode="movies",
            media_type="movie",
            title="Demo Movie",
            ids={"imdb_id": "tt00550"},
        )

    assert _get_trailer_menu_item(menu) is None


def test_tv_context_menu_contains_play_trailer_when_tmdb_id_exists():
    with patch("lib.clients.tmdb.utils.utils.translation", side_effect=lambda value: TRAILER_LABEL if value == 90672 else f"t-{value}"):
        menu = add_tmdb_show_context_menu(
            mode="tv",
            title="Demo Show",
            ids={"tmdb_id": 1399},
        )

    trailer_item = _get_trailer_menu_item(menu)

    assert trailer_item is not None
    assert _parse_playmedia_command(trailer_item[1]) == {
        "action": "play_trailer",
        "media_type": "tv",
        "tmdb_id": "1399",
        "yt_id": None,
        "youtube_url": None,
        "title": "Demo Show",
    }


def test_base_tmdb_client_passes_show_title_to_context_menu_builder():
    list_item = MagicMock()

    with patch(
        "lib.clients.tmdb.base.add_tmdb_show_context_menu",
        return_value=[("tmdb-tv", "cmd")],
    ) as add_context_menu, patch(
        "lib.clients.tmdb.base.is_trakt_auth", return_value=False
    ), patch("lib.clients.tmdb.base.add_kodi_dir_item"):
        BaseTmdbClient.add_media_directory_item(
            list_item=list_item,
            mode="tv",
            title="Demo Show",
            ids={"tmdb_id": 1399},
        )

    add_context_menu.assert_called_once_with(
        "tv", ids={"tmdb_id": 1399}, title="Demo Show"
    )


def test_trakt_movie_context_menu_contains_play_trailer_when_tmdb_id_exists():
    list_item = MagicMock()

    with patch(
        "lib.clients.trakt.trakt.is_trakt_auth", return_value=False
    ), patch("lib.clients.trakt.trakt.add_kodi_dir_item"), patch(
        "lib.clients.tmdb.utils.utils.translation",
        side_effect=lambda value: TRAILER_LABEL if value == 90672 else f"t-{value}",
    ):
        BaseTraktClient._add_media_directory_item(
            list_item=list_item,
            mode="movies",
            title="Demo Movie",
            ids={"tmdb_id": 550},
            media_type="movie",
        )

    context_menu = list_item.addContextMenuItems.call_args[0][0]
    trailer_item = _get_trailer_menu_item(context_menu)

    assert trailer_item is not None
    assert _parse_playmedia_command(trailer_item[1]) == {
        "action": "play_trailer",
        "media_type": "movie",
        "tmdb_id": "550",
        "yt_id": None,
        "youtube_url": None,
        "title": "Demo Movie",
    }


def test_trakt_show_context_menu_contains_play_trailer_when_tmdb_id_exists():
    list_item = MagicMock()

    with patch(
        "lib.clients.trakt.trakt.is_trakt_auth", return_value=True
    ), patch(
            "lib.clients.trakt.trakt.BaseTraktClient._trakt_context_menu",
            return_value=[("watched", "cmd")],
    ), patch("lib.clients.trakt.trakt.add_kodi_dir_item"), patch(
        "lib.clients.tmdb.utils.utils.translation",
        side_effect=lambda value: TRAILER_LABEL if value == 90672 else f"t-{value}",
    ):
        BaseTraktClient._add_media_directory_item(
            list_item=list_item,
            mode="tv",
            title="Demo Show",
            ids={"tmdb_id": 1399},
            media_type="tv",
        )

    context_menu = list_item.addContextMenuItems.call_args[0][0]
    trailer_item = _get_trailer_menu_item(context_menu)

    assert trailer_item is not None
    assert _parse_playmedia_command(trailer_item[1]) == {
        "action": "play_trailer",
        "media_type": "tv",
        "tmdb_id": "1399",
        "yt_id": None,
        "youtube_url": None,
        "title": "Demo Show",
    }
