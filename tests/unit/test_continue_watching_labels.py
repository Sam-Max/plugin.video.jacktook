from unittest.mock import MagicMock

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
    monkeypatch.setattr(
        view, "add_directory_items_batch", lambda items: stored.setdefault("_items", items)
    )
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

    items = picker_db["_items"]
    labels = [item[1].label for item in items if not item[1].label.startswith("Next Page")]
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
