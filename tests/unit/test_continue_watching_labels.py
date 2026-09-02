import json
from unittest.mock import MagicMock

import pytest

from lib.utils.general import utils as general_utils
from lib.utils.views import continue_watching as view


@pytest.fixture
def picker_db(monkeypatch):
    stored = {}

    class FakePickleDatabase:
        def get_key(self, key):
            assert key == "jt:lfh"
            return stored

    monkeypatch.setattr(view, "PickleDatabase", FakePickleDatabase)
    monkeypatch.setattr(
        view, "add_directory_items_batch", lambda items: stored.setdefault("_items", items)
    )
    monkeypatch.setattr(view, "set_pluging_category", MagicMock())
    monkeypatch.setattr(view, "setContent", MagicMock())
    monkeypatch.setattr(view, "end_of_directory", MagicMock())
    monkeypatch.setattr(view, "apply_section_view", MagicMock())
    monkeypatch.setattr(view, "parse_time", lambda data: 0)
    monkeypatch.setattr(
        view,
        "translation",
        lambda _id: "Clear Continue Watching" if _id == 90999 else "Remove from history",
    )
    return stored


def _add_item(stored, title, data):
    data = {"progress": 50.0, **data}
    stored[title] = data


def test_label_appends_torrent_source(picker_db, monkeypatch):
    monkeypatch.setattr(view, "make_list_item", lambda label: MagicMock(label=label))
    _add_item(picker_db, "Movie", {"title": "Movie", "type": "Torrent"})

    view.show_continue_watching()

    item = picker_db["_items"][0]
    assert item[1].label.startswith("Movie (Torrent)")


def test_label_appends_debrid_provider(picker_db, monkeypatch):
    monkeypatch.setattr(view, "make_list_item", lambda label: MagicMock(label=label))
    _add_item(picker_db, "Movie", {"title": "Movie", "debrid_type": "RealDebrid"})

    view.show_continue_watching()

    item = picker_db["_items"][0]
    assert item[1].label.startswith("Movie (RealDebrid)")


def test_label_appends_stremio_source(picker_db, monkeypatch):
    monkeypatch.setattr(view, "make_list_item", lambda label: MagicMock(label=label))
    _add_item(picker_db, "Movie", {"title": "Movie", "type": "Stremio"})

    view.show_continue_watching()

    item = picker_db["_items"][0]
    assert item[1].label.startswith("Movie (Stremio)")


def test_label_appends_jackgram_or_telegram_indexer(picker_db, monkeypatch):
    monkeypatch.setattr(view, "make_list_item", lambda label: MagicMock(label=label))
    _add_item(picker_db, "File", {"title": "File", "indexer": "Jackgram"})

    view.show_continue_watching()

    item = picker_db["_items"][0]
    assert item[1].label.startswith("File (Jackgram)")


def test_label_without_known_source_stays_plain(picker_db, monkeypatch):
    monkeypatch.setattr(view, "make_list_item", lambda label: MagicMock(label=label))
    _add_item(picker_db, "Mystery", {"title": "Mystery"})

    view.show_continue_watching()

    item = picker_db["_items"][0]
    assert item[1].label == "Mystery"


def test_encoded_title_is_decoded_for_label_and_playback(picker_db, monkeypatch):
    playback_payloads = []

    def build_url(action, **params):
        if action == "play_media":
            playback_payloads.append(json.loads(params["data"]))
        return "plugin://test"

    monkeypatch.setattr(view, "make_list_item", lambda label: MagicMock(label=label))
    monkeypatch.setattr(view, "build_url", build_url)
    encoded_title = "Burn%20Bright%2C%20Mad%20Dog"
    decoded_title = "Burn Bright, Mad Dog"
    _add_item(picker_db, encoded_title, {"title": encoded_title})

    view.show_continue_watching()

    assert picker_db["_items"][0][1].label == decoded_title
    assert playback_payloads[0]["title"] == decoded_title
    assert picker_db[encoded_title]["title"] == encoded_title


def test_literal_plus_in_title_stays_a_plus(picker_db, monkeypatch):
    monkeypatch.setattr(view, "make_list_item", lambda label: MagicMock(label=label))
    _add_item(picker_db, "C++", {"title": "C++"})

    view.show_continue_watching()

    assert picker_db["_items"][0][1].label == "C++"


def test_episode_label_keeps_source_suffix(picker_db, monkeypatch):
    monkeypatch.setattr(view, "make_list_item", lambda label: MagicMock(label=label))
    _add_item(
        picker_db,
        "Show",
        {
            "title": "Show",
            "type": "Torrent",
            "tv_data": {"name": "Episode title", "season": 1, "episode": 2},
        },
    )

    view.show_continue_watching()

    item = picker_db["_items"][0]
    assert item[1].label.startswith("Episode title S01E02 (Torrent)")


def _add_items(stored, count, offset=0, progress=50.0):
    for i in range(offset, offset + count):
        _add_item(stored, f"Movie {i}", {"title": f"Movie {i}", "progress": progress})


def _next_page_item(items):
    assert len(items) >= 1
    url, list_item, is_folder = items[-1]
    assert is_folder is True
    assert list_item.label.startswith("Next Page")
    return url, list_item


def test_pagination_shows_ten_items_per_page(picker_db, monkeypatch):
    monkeypatch.setattr(view, "make_list_item", lambda label: MagicMock(label=label))
    _add_items(picker_db, 12)

    view.show_continue_watching()

    items = picker_db["_items"]
    assert len(items) == 11  # 10 items + next page
    url, _ = _next_page_item(items)
    assert "action=continue_watching_menu" in url
    assert "page=2" in url


def test_pagination_next_page_shows_remaining_pages(picker_db, monkeypatch):
    monkeypatch.setattr(view, "make_list_item", lambda label: MagicMock(label=label))
    _add_items(picker_db, 25)  # 3 pages: 10 + 10 + 5

    view.show_continue_watching()
    _, next_item = _next_page_item(picker_db["_items"])
    assert next_item.label == "Next Page (2 more)"

    picker_db.pop("_items")
    view.show_continue_watching({"page": 2})
    _, next_item = _next_page_item(picker_db["_items"])
    assert next_item.label == "Next Page (1 more)"

    picker_db.pop("_items")
    view.show_continue_watching({"page": 3})
    items = picker_db["_items"]
    assert len(items) == 5  # last page, no next page item
    assert not any(item[1].label.startswith("Next Page") for item in items)


def test_pagination_filters_progress_before_slicing(picker_db, monkeypatch):
    monkeypatch.setattr(view, "make_list_item", lambda label: MagicMock(label=label))
    _add_items(picker_db, 12, progress=50.0)
    _add_items(picker_db, 3, offset=100, progress=0.0)  # below 5%: filtered out
    _add_items(picker_db, 2, offset=200, progress=95.0)  # above 90%: filtered out

    view.show_continue_watching()

    labels = [
        item[1].label for item in picker_db["_items"] if not item[1].label.startswith("Next Page")
    ]
    assert len(labels) == 10
    assert all(not label.startswith(("Movie 100", "Movie 200")) for label in labels)


def test_pagination_defaults_to_first_page_when_params_missing(picker_db, monkeypatch):
    monkeypatch.setattr(view, "make_list_item", lambda label: MagicMock(label=label))
    _add_items(picker_db, 11)

    view.show_continue_watching(None)

    items = picker_db["_items"]
    assert len(items) == 11  # 10 items + next page
    labels = [item[1].label for item in items[:10]]
    assert all(not label.startswith("Next Page") for label in labels)


def test_clear_continue_watching_in_context_menu_of_every_item(picker_db, monkeypatch):
    monkeypatch.setattr(view, "make_list_item", lambda label: MagicMock(label=label))
    _add_items(picker_db, 12)

    view.show_continue_watching()

    items = picker_db["_items"]
    playable_items = [item for item in items if item[2] is False]
    assert len(playable_items) == 10
    for _url, list_item, _is_folder in playable_items:
        context_menu = list_item.addContextMenuItems.call_args.args[0]
        clear_entries = [e for e in context_menu if e[0] == "Clear Continue Watching"]
        assert len(clear_entries) == 1
        assert "action=remove_continue_watching" in clear_entries[0][1]
        assert "title=__all__" in clear_entries[0][1]
        assert clear_entries[0][1].startswith("RunPlugin(")


def test_remove_continue_watching_item_clears_all(monkeypatch):
    clear_history = MagicMock()
    monkeypatch.setattr(view, "clear_continue_watching_history", clear_history)
    monkeypatch.setattr(view, "notification", MagicMock())
    execute = MagicMock()
    monkeypatch.setattr(view, "executebuiltin", execute)

    view.remove_continue_watching_item({"title": "__all__"})

    clear_history.assert_called_once_with()
    execute.assert_called_once_with("Container.Refresh")
    view.notification.assert_called_once_with(view.translation(91001))


def test_remove_continue_watching_item_deletes_one(monkeypatch):
    pickle_db = MagicMock()
    monkeypatch.setattr(view, "PickleDatabase", lambda: pickle_db)
    monkeypatch.setattr(view, "notification", MagicMock())
    execute = MagicMock()
    monkeypatch.setattr(view, "executebuiltin", execute)

    view.remove_continue_watching_item({"title": "Movie"})

    pickle_db.delete_item.assert_called_once_with(key="jt:lfh", subkey="Movie")
    pickle_db.set_key.assert_not_called()
    view.notification.assert_not_called()
    execute.assert_called_once_with("Container.Refresh")


class FakeContinueWatchingDatabase:
    def __init__(self, entries=None):
        self.database = {"jt:lfh": dict(entries or {})}
        self.calls = []

    def set_key(self, key, value):
        self.calls.append(("set_key", key, dict(value)))
        self.database[key] = value

    def set_item(self, key, subkey, value):
        self.calls.append(("set_item", key, subkey, value))
        self.database[key][subkey] = value


def test_set_watched_file_decodes_title_before_storing(monkeypatch):
    pickle_db = FakeContinueWatchingDatabase()
    monkeypatch.setattr(general_utils, "pickle_db", pickle_db)
    monkeypatch.setattr(general_utils, "get_random_color", lambda *_args, **_kwargs: "white")
    data = {"title": "Burn%20Bright%2C%20Mad%20Dog", "type": "Cached"}

    general_utils.set_watched_file(data)

    _method, _key, history_key, stored_data = pickle_db.calls[0]
    assert history_key == "[B][COLOR white][Cached][/COLOR][/B] - Burn Bright, Mad Dog"
    assert "%20" not in history_key
    assert stored_data["title"] == "Burn Bright, Mad Dog"
    assert "%20" not in stored_data["title"]
    assert data["title"] == "Burn Bright, Mad Dog"


def test_clear_continue_watching_history_uses_watched_file_database(monkeypatch):
    pickle_db = FakeContinueWatchingDatabase({"Stale": {"title": "Stale"}})
    monkeypatch.setattr(general_utils, "pickle_db", pickle_db)
    monkeypatch.setattr(general_utils, "get_random_color", lambda *_args, **_kwargs: "white")

    general_utils.clear_continue_watching_history()
    general_utils.set_watched_file({"title": "New", "type": "Cached"})

    assert pickle_db.calls[0] == ("set_key", "jt:lfh", {})
    assert pickle_db.calls[1][0:3] == (
        "set_item",
        "jt:lfh",
        "[B][COLOR white][Cached][/COLOR][/B] - New",
    )


def test_clear_continue_watching_history_prevents_stale_entries_from_returning(monkeypatch):
    pickle_db = FakeContinueWatchingDatabase({"Stale": {"title": "Stale"}})
    monkeypatch.setattr(general_utils, "pickle_db", pickle_db)
    monkeypatch.setattr(general_utils, "get_random_color", lambda *_args, **_kwargs: "white")

    general_utils.clear_continue_watching_history()
    general_utils.set_watched_file({"title": "New", "type": "Cached"})

    entries = pickle_db.database["jt:lfh"]
    assert list(entries) == ["[B][COLOR white][Cached][/COLOR][/B] - New"]
    assert entries[next(iter(entries))]["title"] == "New"
