from unittest.mock import MagicMock, patch

import pytest

from lib.utils.views import continue_watching as view


@pytest.fixture
def picker_db(monkeypatch):
    stored = {}

    class FakePickleDatabase:
        def get_key(self, key):
            assert key == "jt:lfh"
            return stored

    monkeypatch.setattr(view, "PickleDatabase", FakePickleDatabase)
    monkeypatch.setattr(view, "add_directory_items_batch", lambda items: stored.setdefault("_items", items))
    monkeypatch.setattr(view, "set_pluging_category", MagicMock())
    monkeypatch.setattr(view, "setContent", MagicMock())
    monkeypatch.setattr(view, "end_of_directory", MagicMock())
    monkeypatch.setattr(view, "apply_section_view", MagicMock())
    monkeypatch.setattr(view, "parse_time", lambda data: 0)
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
