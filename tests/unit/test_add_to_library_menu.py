""""Add to Library" context menu entries.

The action only stores an entry: launching it with PlayMedia made Kodi wait for a
playable item that never resolves. The stored entry must carry a title (entries
without one are dropped) and the "movies"/"tv" mode the library lists filter on.
"""

import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest

from lib.clients.stremio import catalog_menus
from lib.clients.tmdb.utils import utils as tmdb_utils
from lib.nav import library_history

ADD_TO_LIBRARY_LABEL = "label-90205"


def _label(string_id):
    return f"label-{string_id}"


def _add_to_library_commands(context_menu):
    return [command for label, command in context_menu if label == ADD_TO_LIBRARY_LABEL]


def _payload(command):
    assert command.startswith("RunPlugin(") and command.endswith(")")
    query = parse_qs(urlsplit(command[len("RunPlugin(") : -1]).query)
    assert query["action"] == ["add_to_library"]
    return json.loads(query["data"][0])


@pytest.mark.parametrize(
    "build_menu,expected_mode",
    [
        # Regular movie lists pass an empty media_type; multi search passes "multi".
        (lambda: tmdb_utils.add_tmdb_movie_context_menu("movies", "", title="Dune", ids={"tmdb_id": "1"}), "movies"),
        (lambda: tmdb_utils.add_tmdb_movie_context_menu("multi", "movie", title="Dune", ids={"tmdb_id": "1"}), "movies"),
        # TMDB ids carry no name, so the title must come from the list item.
        (lambda: tmdb_utils.add_tmdb_show_context_menu("tv", ids={"tmdb_id": "2"}, title="Dune"), "tv"),
        (lambda: tmdb_utils.add_tmdb_show_context_menu("multi", ids={"tmdb_id": "2"}, title="Dune"), "tv"),
    ],
)
def test_tmdb_add_to_library_stores_title_and_library_mode(build_menu, expected_mode):
    with patch.object(tmdb_utils, "translation", side_effect=_label):
        commands = _add_to_library_commands(build_menu())

    assert len(commands) == 1
    payload = _payload(commands[0])
    assert payload["title"] == "Dune"
    assert payload["mode"] == expected_mode


def test_show_add_to_library_falls_back_to_name_in_ids():
    with patch.object(tmdb_utils, "translation", side_effect=_label):
        commands = _add_to_library_commands(
            tmdb_utils.add_tmdb_show_context_menu("tv", ids={"tmdb_id": "2", "name": "Show"})
        )

    assert _payload(commands[0])["title"] == "Show"


def test_stremio_add_to_library_runs_plugin_instead_of_playing():
    with patch.object(catalog_menus, "translation", side_effect=_label):
        label, command = catalog_menus._build_stremio_library_menu_item({"title": "Dune"})

    assert label == ADD_TO_LIBRARY_LABEL
    assert _payload(command)["title"] == "Dune"


@pytest.mark.parametrize("stored,notified", [(True, True), (False, False)])
def test_add_to_library_notifies_only_when_stored(stored, notified):
    with (
        patch("lib.utils.general.utils.add_to_library", return_value=stored),
        patch.object(library_history, "Dialog") as dialog,
    ):
        library_history.add_to_library({"data": json.dumps({"title": "Dune"})})

    assert dialog.return_value.notification.called is notified
