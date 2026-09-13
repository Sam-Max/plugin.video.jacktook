from lib.anime import display
from lib.anime.normalize import AnimeRecord


def test_resolve_menu_title_prefers_english_for_language_zero(monkeypatch):
    record = AnimeRecord(title_en="English Title", title_romaji="Romaji Title")
    monkeypatch.setattr(display, "resolve_identity", lambda ids: record)

    assert display.resolve_menu_title({"tmdb_id": 1}, 0) == "English Title"


def test_resolve_menu_title_prefers_romaji_for_language_one(monkeypatch):
    record = AnimeRecord(title_en="English Title", title_romaji="Romaji Title")
    monkeypatch.setattr(display, "resolve_identity", lambda ids: record)

    assert display.resolve_menu_title({"tmdb_id": 1}, 1) == "Romaji Title"


def test_resolve_menu_title_coerces_string_language(monkeypatch):
    record = AnimeRecord(title_en="English Title", title_romaji="Romaji Title")
    monkeypatch.setattr(display, "resolve_identity", lambda ids: record)

    assert display.resolve_menu_title({"tmdb_id": 1}, "1") == "Romaji Title"


def test_resolve_menu_title_returns_none_when_provider_fails(monkeypatch):
    monkeypatch.setattr(display, "resolve_identity", lambda ids: None)

    assert display.resolve_menu_title({"tmdb_id": 1}, 0) is None


def test_resolve_menu_title_returns_none_without_titles(monkeypatch):
    monkeypatch.setattr(display, "resolve_identity", lambda ids: AnimeRecord(tmdb_id=1))

    assert display.resolve_menu_title({"tmdb_id": 1}, 0) is None


def test_resolve_menu_title_swallows_identity_exceptions(monkeypatch):
    def boom(ids):
        raise RuntimeError("boom")

    monkeypatch.setattr(display, "resolve_identity", boom)

    assert display.resolve_menu_title({"tmdb_id": 1}, 0) is None


def test_resolve_menu_record_swallows_identity_exceptions(monkeypatch):
    def boom(ids):
        raise RuntimeError("boom")

    monkeypatch.setattr(display, "resolve_identity", boom)

    assert display.resolve_menu_record({"tmdb_id": 1}) is None


def test_pick_original_title_returns_the_other_language():
    record = AnimeRecord(title_en="English Title", title_romaji="Romaji Title")

    assert display.pick_original_title(record, 0) == "Romaji Title"
    assert display.pick_original_title(record, 1) == "English Title"


def test_pick_original_title_returns_none_without_alternate():
    record = AnimeRecord(title_en="English Title")

    assert display.pick_original_title(record, 0) is None
    assert display.pick_original_title(None, 0) is None
