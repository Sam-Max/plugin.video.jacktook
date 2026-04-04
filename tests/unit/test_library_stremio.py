from unittest.mock import MagicMock

from lib.utils.views import library


def test_get_library_entries_prioritizes_stremio_metadata(monkeypatch):
    monkeypatch.setattr(library.cache, "get", lambda key: None)
    monkeypatch.setattr(library.cache, "set", lambda *args, **kwargs: None)

    tmdb_calls = []
    monkeypatch.setattr(library, "tmdb_get", lambda *args, **kwargs: tmdb_calls.append((args, kwargs)))

    entries = library._get_library_entries(
        [
            (
                "Kitsu Show",
                {
                    "source": "stremio_catalog",
                    "title": "Kitsu Show",
                    "overview": "Catalog plot",
                    "poster": "poster.jpg",
                    "fanart": "fanart.jpg",
                    "genres": ["Anime"],
                    "mode": "tv",
                    "ids": {"imdb_id": "tt123", "original_id": "kitsu:show"},
                },
            )
        ],
        "tv",
    )

    assert tmdb_calls == []
    assert entries[0]["is_stremio"] is True
    assert entries[0]["details"]["title"] == "Kitsu Show"
    assert entries[0]["details"]["overview"] == "Catalog plot"
    assert entries[0]["details"]["poster"] == "poster.jpg"


def test_get_library_item_url_uses_stremio_seasons_route_for_shows():
    entry = {
        "title": "Kitsu Show",
        "is_stremio": True,
        "data": {
            "title": "Kitsu Show",
            "addon_url": "https://anime-kitsu.strem.fun",
            "catalog_type": "anime",
            "meta_id": "kitsu:123",
            "ids": {"original_id": "kitsu:123"},
        },
    }

    url = library._get_library_item_url(entry, "tv")

    assert url.startswith("plugin://")
    assert "action=list_stremio_seasons" in url
    assert "meta_id=kitsu%3A123" in url


def test_get_library_item_url_uses_stremio_movie_route_for_movies():
    entry = {
        "title": "Kitsu Movie",
        "is_stremio": True,
        "data": {
            "title": "Kitsu Movie",
            "overview": "Catalog plot",
            "poster": "poster.jpg",
            "fanart": "fanart.jpg",
            "genres": ["Anime"],
            "addon_url": "https://anime-kitsu.strem.fun",
            "catalog_type": "anime",
            "meta_id": "kitsu:456",
            "ids": {"original_id": "kitsu:456"},
        },
    }

    url = library._get_library_item_url(entry, "movies")

    assert url.startswith("plugin://")
    assert "action=list_stremio_movie" in url
    assert "meta_id=kitsu%3A456" in url


def test_show_library_items_renders_stremio_entry_without_tmdb(monkeypatch):
    added = []

    class _ListItem:
        def __init__(self, label=""):
            self.label = label
            self.context_menu = []
            self.properties = {}

        def getVideoInfoTag(self):
            return MagicMock()

        def addContextMenuItems(self, items):
            self.context_menu.extend(items)

        def setArt(self, *args, **kwargs):
            pass

        def setProperty(self, key, value):
            self.properties[key] = value

    monkeypatch.setattr(library, "ListItem", _ListItem)
    monkeypatch.setattr(library, "set_pluging_category", lambda *args, **kwargs: None)
    monkeypatch.setattr(library, "setContent", lambda *args, **kwargs: None)
    monkeypatch.setattr(library, "end_of_directory", lambda *args, **kwargs: None)
    monkeypatch.setattr(library, "translation", lambda value: {90202: "My Shows", 90204: "Remove from Library"}.get(value, str(value)))
    monkeypatch.setattr(library, "set_media_infoTag", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        library,
        "addDirectoryItem",
        lambda handle, url, listitem, isFolder=True: added.append((url, listitem.label, isFolder)),
    )
    monkeypatch.setattr(
        library.PickleDatabase,
        "get_key",
        lambda self, key: {
            "Kitsu Show": {
                "source": "stremio_catalog",
                "title": "Kitsu Show",
                "overview": "Catalog plot",
                "poster": "poster.jpg",
                "fanart": "fanart.jpg",
                "mode": "tv",
                "addon_url": "https://anime-kitsu.strem.fun",
                "catalog_type": "anime",
                "meta_id": "kitsu:123",
                "ids": {"original_id": "kitsu:123"},
                "timestamp": "Sun, 05 Apr 2026 12:00 AM",
            }
        },
    )
    monkeypatch.setattr(library.cache, "get", lambda key: None)
    monkeypatch.setattr(library.cache, "set", lambda *args, **kwargs: None)
    monkeypatch.setattr(library, "tmdb_get", lambda *args, **kwargs: None)

    library.show_library_items(mode="tv")

    assert added == [(added[0][0], "Kitsu Show", True)]
    assert "action=list_stremio_seasons" in added[0][0]
