from unittest.mock import MagicMock

from lib.api.stremio.models import Meta, MetaPreview
from lib.clients.stremio import helpers
from lib.clients.stremio.catalog_menus import CATALOG_PAGE_SIZE
from lib.clients.stremio import catalog_menus


def test_merge_addons_lists_dedupes_account_and_custom_by_manifest_id():
    custom_addon = {
        "manifest": {"id": "org.example.addon", "name": "Example"},
        "transportUrl": "https://example.com/custom/manifest.json",
        "transportName": "custom",
    }
    account_addon = {
        "manifest": {"id": "org.example.addon", "name": "Example"},
        "transportUrl": "https://example.com/account/manifest.json",
        "transportName": "stremio-account",
    }

    merged = helpers.merge_addons_lists([custom_addon], [account_addon])

    assert merged == [custom_addon]


def test_get_addons_uses_cached_account_addons_before_settings_refresh(monkeypatch):
    custom_addon = {
        "manifest": {"id": "custom.one", "name": "Custom One"},
        "transportUrl": "https://custom.example/manifest.json",
        "transportName": "custom",
    }
    account_addon = {
        "manifest": {"id": "account.one", "name": "Account One"},
        "transportUrl": "https://account.example/manifest.json",
        "transportName": "stremio-account",
    }

    fake_cache = MagicMock()
    fake_cache.get.return_value = [custom_addon, account_addon]

    monkeypatch.setattr(helpers, "cache", fake_cache)
    monkeypatch.setattr(helpers, "get_setting", lambda key: False)

    addon_manager = helpers.get_addons()
    addon_ids = [addon.manifest.id for addon in addon_manager.addons]

    assert addon_ids == ["custom.one", "account.one"]


def test_list_catalog_locally_paginates_when_catalog_has_no_skip(monkeypatch):
    metas = [
        MetaPreview(id=f"id-{i}", type="movie", name=f"Movie {i}", poster="")
        for i in range(CATALOG_PAGE_SIZE + 5)
    ]
    added_pages = []
    next_urls = []

    monkeypatch.setattr(
        catalog_menus,
        "catalogs_get_cache",
        lambda *args, **kwargs: {"metas": metas},
    )
    monkeypatch.setattr(
        catalog_menus, "_catalog_supports_extra", lambda *args, **kwargs: False
    )
    monkeypatch.setattr(
        catalog_menus,
        "add_meta_items",
        lambda chunk, params: added_pages.append([meta.id for meta in chunk]),
    )
    monkeypatch.setattr(catalog_menus, "setContent", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "end_of_directory", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "notification", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "ListItem", lambda *args, **kwargs: MagicMock())
    monkeypatch.setattr(
        catalog_menus,
        "addDirectoryItem",
        lambda handle, url, listitem, isFolder=True: next_urls.append(url),
    )
    monkeypatch.setattr(
        catalog_menus,
        "build_url",
        lambda action, **kwargs: f"{action}:{kwargs.get('skip', 0)}",
    )

    params = {
        "addon_url": "https://example.com/addon",
        "menu_type": "movie",
        "catalog_type": "movie",
        "catalog_id": "user-movies",
    }
    catalog_menus.list_catalog(params)

    assert len(added_pages) == 1
    assert len(added_pages[0]) == CATALOG_PAGE_SIZE
    assert added_pages[0][0] == "id-0"
    assert added_pages[0][-1] == f"id-{CATALOG_PAGE_SIZE - 1}"
    assert next_urls == [f"list_catalog:{CATALOG_PAGE_SIZE}"]


def test_list_catalog_uses_server_skip_when_manifest_supports_it(monkeypatch):
    captured_kwargs = {}

    monkeypatch.setattr(
        catalog_menus,
        "catalogs_get_cache",
        lambda path, params, **kwargs: captured_kwargs.update(kwargs) or {"metas": []},
    )
    monkeypatch.setattr(
        catalog_menus, "_catalog_supports_extra", lambda *args, **kwargs: True
    )
    monkeypatch.setattr(catalog_menus, "setContent", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "end_of_directory", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "notification", lambda *args, **kwargs: None)

    params = {
        "addon_url": "https://example.com/addon",
        "menu_type": "movie",
        "catalog_type": "movie",
        "catalog_id": "user-movies",
        "skip": 50,
    }
    catalog_menus.list_catalog(params)

    assert captured_kwargs == {"skip": 50}


def test_list_stremio_episodes_uses_safe_title_fallback(monkeypatch):
    meta_data = Meta.from_dict(
        {
            "id": "tt123",
            "type": "series",
            "name": "Fallback Show",
            "imdb_id": "tt123",
            "videos": [
                {
                    "id": "tt123:1:2",
                    "title": "",
                    "overview": "Overview",
                    "imdbSeason": 1,
                    "imdbEpisode": 2,
                    "season": 1,
                    "episode": 2,
                    "released": "2024-01-01",
                    "thumbnail": "",
                }
            ],
        }
    )
    added = []

    class _InfoTag:
        def setUniqueID(self, *args, **kwargs):
            pass

        def setTitle(self, *args, **kwargs):
            pass

        def setPlot(self, *args, **kwargs):
            pass

        def setRating(self, *args, **kwargs):
            pass

        def setSeason(self, *args, **kwargs):
            pass

        def setEpisode(self, *args, **kwargs):
            pass

        def setTvShowTitle(self, *args, **kwargs):
            pass

        def setMediaType(self, *args, **kwargs):
            pass

        def setPremiered(self, *args, **kwargs):
            pass

        def __getattr__(self, name):
            return lambda *args, **kwargs: None

    class _ListItem:
        def __init__(self, label=""):
            self.label = label

        def getVideoInfoTag(self):
            return _InfoTag()

        def setArt(self, *args, **kwargs):
            pass

        def setProperty(self, *args, **kwargs):
            pass

        def addContextMenuItems(self, *args, **kwargs):
            pass

    monkeypatch.setattr(
        catalog_menus,
        "catalogs_get_cache",
        lambda *args, **kwargs: {"meta": meta_data},
    )
    monkeypatch.setattr(catalog_menus, "tmdb_get", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "addon_has_stream", lambda *args, **kwargs: False)
    monkeypatch.setattr(catalog_menus, "build_url", lambda *args, **kwargs: "plugin://test")
    monkeypatch.setattr(catalog_menus, "ListItem", _ListItem)
    monkeypatch.setattr(catalog_menus, "addDirectoryItem", lambda handle, url, listitem, isFolder=False: added.append(listitem.label))
    monkeypatch.setattr(catalog_menus, "setContent", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "end_of_directory", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "notification", lambda *args, **kwargs: None)

    catalog_menus.list_stremio_episodes(
        {
            "addon_url": "https://example.com/addon",
            "catalog_type": "series",
            "meta_id": "tt123",
            "season": "1",
        }
    )

    assert added == ["1x2. Fallback Show"]
