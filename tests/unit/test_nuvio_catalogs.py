from pathlib import Path

from lib.api.stremio.addon_manager import AddonManager
from lib.api.stremio.models import MetaPreview
from lib.clients import catalog_hub
from lib.clients.catalog_hub import catalog_addon_resolver, list_merged_catalogs
from lib.clients.nuvio.constants import NUVIO_ADDONS_KEY, NUVIO_USER_ADDONS
from lib.clients.nuvio.helpers import (
    get_selected_catalogs_addons,
    get_selected_stream_addons,
    get_selected_tv_addons,
)
from lib.clients.stremio import catalog_menus


def _nuvio_record(manifest_id, name, types, resources, catalogs, url):
    return {
        "manifest": {
            "id": manifest_id,
            "name": name,
            "types": types,
            "resources": resources,
            "catalogs": catalogs,
        },
        "transportUrl": url,
        "transportName": "nuvio",
    }


def _cinemeta_like_record():
    return _nuvio_record(
        "nuvio.cinemeta",
        "Nuvio Cinemeta",
        ["movie", "series"],
        [
            {"name": "catalog", "types": ["movie", "series"]},
            {"name": "meta", "types": ["movie", "series"]},
        ],
        [{"type": "movie", "id": "top", "name": "Top Movies"}],
        "https://nuvio.example/cinemeta/manifest.json",
    )


def _stream_only_record():
    return _nuvio_record(
        "nuvio.streamonly",
        "Nuvio Stream",
        ["movie"],
        ["stream"],
        [],
        "https://nuvio.example/stream/manifest.json",
    )


def _tv_record():
    return _nuvio_record(
        "nuvio.tv",
        "Nuvio TV",
        ["tv", "channel"],
        [{"name": "stream", "types": ["tv", "channel"]}],
        [],
        "https://nuvio.example/tv/manifest.json",
    )


def _patch_nuvio_cache(monkeypatch, records):
    keys = [AddonManager([record]).addons[0].key() for record in records]
    monkeypatch.setattr(
        "lib.clients.nuvio.helpers.cache.get",
        lambda key: {NUVIO_USER_ADDONS: records, NUVIO_ADDONS_KEY: keys}.get(key),
    )
    return keys


def test_cinemeta_like_nuvio_is_catalog_only(monkeypatch):
    _patch_nuvio_cache(monkeypatch, [_cinemeta_like_record()])

    catalog_addons = get_selected_catalogs_addons()
    stream_addons = get_selected_stream_addons()

    assert [addon.manifest.id for addon in catalog_addons] == ["nuvio.cinemeta"]
    assert stream_addons == []


def test_stream_only_nuvio_is_stream_only(monkeypatch):
    _patch_nuvio_cache(monkeypatch, [_stream_only_record()])

    assert [addon.manifest.id for addon in get_selected_stream_addons()] == ["nuvio.streamonly"]
    assert get_selected_catalogs_addons() == []


def test_tv_stream_nuvio_is_tv_addon(monkeypatch):
    _patch_nuvio_cache(monkeypatch, [_tv_record()])

    assert [addon.manifest.id for addon in get_selected_tv_addons()] == ["nuvio.tv"]


def test_get_stremio_catalogs_includes_nuvio_only_catalog(monkeypatch):
    record = _cinemeta_like_record()
    _patch_nuvio_cache(monkeypatch, [record])
    monkeypatch.setattr(catalog_menus, "get_selected_catalogs_addons", lambda: [])

    catalogs = catalog_menus._get_stremio_catalogs(
        "movie",
        "movie",
        extra_addons=catalog_hub.get_extra_catalog_addons("movie"),
    )

    assert [(addon.manifest.id, catalog.id) for addon, catalog in catalogs] == [
        ("nuvio.cinemeta", "top")
    ]


def test_list_merged_catalogs_includes_nuvio_only_catalog(monkeypatch):
    record = _cinemeta_like_record()
    _patch_nuvio_cache(monkeypatch, [record])
    monkeypatch.setattr(catalog_menus, "get_selected_catalogs_addons", lambda: [])
    monkeypatch.setattr(catalog_menus, "add_directory_items_batch", lambda items: None)

    list_merged_catalogs(menu_type="movie", sub_menu_type="movie")


def test_list_catalog_with_resolver_reaches_cache(monkeypatch):
    record = _cinemeta_like_record()
    _patch_nuvio_cache(monkeypatch, [record])
    captured = {}

    monkeypatch.setattr(catalog_menus, "get_addon_by_key", lambda _key: None)
    monkeypatch.setattr(catalog_menus, "setContent", lambda *_args: None)
    monkeypatch.setattr(catalog_menus, "end_of_directory", lambda: None)
    monkeypatch.setattr(catalog_menus, "notification", lambda *_args: None)

    class _ListItem:
        def __init__(self, label=""):
            self.label = label

        def setArt(self, *args, **kwargs):
            pass

        def setProperty(self, *args, **kwargs):
            pass

        def addContextMenuItems(self, *args, **kwargs):
            pass

        def getVideoInfoTag(self):
            from unittest.mock import MagicMock

            return MagicMock()

    monkeypatch.setattr(catalog_menus, "make_list_item", lambda label="", path="": _ListItem(label))
    monkeypatch.setattr(catalog_menus, "build_url", lambda action, **kwargs: (action, kwargs))
    monkeypatch.setattr(
        catalog_menus,
        "addDirectoryItem",
        lambda handle, url, listitem, isFolder=False: captured_batches.append(listitem),
    )
    monkeypatch.setattr(catalog_menus, "addon_has_meta", lambda *args, **kwargs: False)
    monkeypatch.setattr(catalog_menus, "addon_has_stream", lambda *args, **kwargs: False)

    captured_batches = []

    monkeypatch.setattr(
        catalog_menus,
        "add_tmdb_movie_context_menu",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(catalog_menus, "_resolve_tmdb_ids_for_context_menu", lambda ids, _t: ids)

    def _fake_cache(_path, params, **kwargs):
        captured.update(kwargs)
        return {
            "metas": [
                MetaPreview(
                    id="tt0111161",
                    type="movie",
                    name="The Shawshank Redemption",
                    poster="",
                    description="",
                )
            ]
        }

    monkeypatch.setattr(catalog_menus, "catalogs_get_cache", _fake_cache)

    catalog_hub.list_catalog(
        {
            "addon_url": record["transportUrl"],
            "menu_type": "movie",
            "catalog_type": "movie",
            "catalog_id": "top",
        }
    )

    assert captured == {}
    assert len(captured_batches) == 1


def test_get_manifest_catalog_resolves_nuvio_addon_key(monkeypatch):
    record = _cinemeta_like_record()
    (addon_key,) = _patch_nuvio_cache(monkeypatch, [record])
    monkeypatch.setattr(catalog_menus, "get_addon_by_key", lambda _key: None)

    catalog = catalog_menus._get_manifest_catalog(
        "", "movie", "top", addon_key=addon_key, resolver=catalog_addon_resolver
    )

    assert catalog is not None
    assert catalog.id == "top"
    assert catalog.type == "movie"


def test_catalog_menus_does_not_reference_nuvio():
    source = Path(catalog_menus.__file__).read_text(encoding="utf-8").lower()
    assert "nuvio" not in source
