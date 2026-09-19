"""``list_stremio_episodes`` must forward the anime marker into the episode context menu.

The Stremio/Kitsu anime catalogs report their episodes under a ``series`` meta
type, so the anime marker in scope there is the catalog type (or the meta type).
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from lib.api.stremio.models import Meta
from lib.clients.stremio import catalog_menus


def _anime_meta(meta_type="series"):
    return Meta.from_dict(
        {
            "id": "kitsu:jigokuraku-2",
            "type": meta_type,
            "name": "Jigokuraku 2nd Season",
            "imdb_id": "tt1234567",
            "videos": [
                {
                    "id": "ep1",
                    "title": "Episode 1",
                    "season": 1,
                    "episode": 1,
                    "overview": "Episode plot",
                }
            ],
        }
    )


def _capture_context_menu_kwargs(monkeypatch, params, meta_data):
    calls = []

    monkeypatch.setattr(
        catalog_menus,
        "catalogs_get_cache",
        lambda *args, **kwargs: {"meta": meta_data},
    )
    monkeypatch.setattr(
        catalog_menus,
        "tmdb_get",
        lambda *args, **kwargs: SimpleNamespace(tv_results=[{"id": 94664}]),
    )
    monkeypatch.setattr(catalog_menus, "get_addon_by_base_url", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "addon_has_stream", lambda *args, **kwargs: False)
    monkeypatch.setattr(catalog_menus, "notification", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "end_of_directory", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "make_list_item", lambda label="", path="": MagicMock())
    monkeypatch.setattr(catalog_menus, "build_url", lambda *args, **kwargs: "plugin://test")
    monkeypatch.setattr(catalog_menus, "add_directory_items_batch", lambda items: None)
    monkeypatch.setattr(
        catalog_menus,
        "add_tmdb_episode_context_menu",
        lambda **kwargs: calls.append(kwargs) or [],
    )

    catalog_menus.list_stremio_episodes(params)

    return calls


def test_stremio_anime_catalog_forwards_anime_flag_to_episode_context_menu(monkeypatch):
    calls = _capture_context_menu_kwargs(
        monkeypatch,
        {
            "addon_url": "https://anime-kitsu.strem.fun",
            "catalog_type": "anime",
            "meta_id": "kitsu:jigokuraku-2",
            "season": "1",
        },
        _anime_meta(meta_type="series"),
    )

    assert len(calls) == 1
    assert calls[0]["anime"] is True


def test_stremio_series_catalog_keeps_anime_flag_false(monkeypatch):
    calls = _capture_context_menu_kwargs(
        monkeypatch,
        {
            "addon_url": "https://example.com/addon",
            "catalog_type": "series",
            "meta_id": "tt1234567",
            "season": "1",
        },
        _anime_meta(meta_type="series"),
    )

    assert len(calls) == 1
    assert calls[0]["anime"] is False


def test_stremio_anime_meta_type_alone_forwards_anime_flag(monkeypatch):
    calls = _capture_context_menu_kwargs(
        monkeypatch,
        {
            "addon_url": "https://example.com/addon",
            "catalog_type": "series",
            "meta_id": "kitsu:jigokuraku-2",
            "season": "1",
        },
        _anime_meta(meta_type="anime"),
    )

    assert len(calls) == 1
    assert calls[0]["anime"] is True
