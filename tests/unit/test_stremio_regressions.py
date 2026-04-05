import json
from unittest.mock import MagicMock

from lib.api.stremio.addon_manager import AddonManager
from lib.api.stremio.models import Meta, MetaPreview
from lib.clients.stremio import helpers
from lib.clients.stremio.catalog_menus import CATALOG_PAGE_SIZE
from lib.clients.stremio import catalog_menus
from lib.domain.torrent import TorrentStream
from lib import search


def test_merge_addons_lists_keeps_same_manifest_id_with_different_urls():
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

    assert merged == [custom_addon, account_addon]


def test_get_selected_stream_addons_skips_ambiguous_legacy_ids(monkeypatch):
    addon_manager = AddonManager(
        [
            {
                "manifest": {
                    "id": "org.example.addon",
                    "name": "Example",
                    "resources": [{"name": "stream", "types": ["movie"], "idPrefixes": ["tt"]}],
                    "types": ["movie"],
                },
                "transportUrl": "https://example.com/one/manifest.json",
                "transportName": "custom",
            },
            {
                "manifest": {
                    "id": "org.example.addon",
                    "name": "Example",
                    "resources": [{"name": "stream", "types": ["movie"], "idPrefixes": ["tt"]}],
                    "types": ["movie"],
                },
                "transportUrl": "https://example.com/two/manifest.json",
                "transportName": "stremio-account",
            },
        ]
    )

    fake_cache = MagicMock()
    fake_cache.get.return_value = "org.example.addon"

    monkeypatch.setattr(helpers, "get_addons", lambda: addon_manager)
    monkeypatch.setattr(helpers, "cache", fake_cache)

    selected = helpers.get_selected_stream_addons()

    assert selected == []


def test_process_search_results_bypasses_exact_addon_instance(monkeypatch):
    bypass_result = TorrentStream(
        title="Bypassed",
        indexer="Torrentio",
        addonKey="org.example.addon|https://example.com/one",
        addonName="Torrentio",
    )
    native_result = TorrentStream(
        title="Native",
        indexer="Torrentio",
        addonKey="org.example.addon|https://example.com/two",
        addonName="Torrentio",
    )

    processed_batches = []

    monkeypatch.setattr(search, "get_setting", lambda key, default=None: {
        "stremio_bypass_addons": True,
        "stremio_bypass_addon_list": "org.example.addon|https://example.com/one",
    }.get(key, default))
    monkeypatch.setattr(search, "pre_process_results", lambda results, *args, **kwargs: results)
    monkeypatch.setattr(
        search,
        "process_results",
        lambda results, *args, **kwargs: processed_batches.append(results) or results,
    )

    results = search._process_search_results(
        [bypass_result, native_result],
        "movies",
        "",
        1,
        1,
        "",
        "query",
        "movies",
        False,
    )

    assert results == [bypass_result, native_result]
    assert processed_batches == [[native_result]]


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


def test_search_catalog_cancel_shows_previous_search_terms(monkeypatch):
    added_items = []

    class _ListItem:
        def __init__(self, label=""):
            self.label = label

        def setArt(self, *args, **kwargs):
            pass

    monkeypatch.setattr(catalog_menus, "show_keyboard", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus.cache, "get_list", lambda key: [("Naruto",), ("Bleach",)])
    monkeypatch.setattr(catalog_menus, "translation", lambda value: {90006: "Search", 90210: "Clear All Search History"}.get(value, str(value)))
    monkeypatch.setattr(catalog_menus, "ListItem", _ListItem)
    monkeypatch.setattr(
        catalog_menus,
        "addDirectoryItem",
        lambda handle, url, listitem, isFolder=True: added_items.append((listitem.label, url, isFolder)),
    )
    monkeypatch.setattr(catalog_menus, "end_of_directory", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        catalog_menus,
        "build_url",
        lambda action, **kwargs: "{}:{}:{}".format(action, kwargs.get("query", ""), kwargs.get("is_keyboard", True)),
    )

    catalog_menus.search_catalog(
        {
            "page": 1,
            "addon_url": "https://anime-kitsu.strem.fun",
            "catalog_type": "anime",
            "catalog_id": "kitsu-search",
        }
    )

    assert added_items == [
        ("Search", "search_catalog::True", True),
        ("[I]Naruto[/I]", "search_catalog:Naruto:False", True),
        ("[I]Bleach[/I]", "search_catalog:Bleach:False", True),
        ("Clear All Search History", "clear_stremio_search_history::True", True),
    ]


def test_search_catalog_uses_stremio_routes_when_catalog_has_meta(monkeypatch):
    added_urls = []

    monkeypatch.setattr(
        catalog_menus,
        "catalogs_get_cache",
        lambda *args, **kwargs: {
            "metas": [
                MetaPreview(
                    id="kitsu:hell-paradise-2",
                    type="series",
                    name="Jigokuraku 2nd Season",
                    poster="",
                    description="desc",
                    imdb_id="tt123",
                )
            ]
        },
    )
    monkeypatch.setattr(catalog_menus, "setContent", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "end_of_directory", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "notification", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "add_next_button", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "show_keyboard", lambda *args, **kwargs: "paradise")
    monkeypatch.setattr(catalog_menus.cache, "add_to_list", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus.PickleDatabase, "set_key", lambda self, key, value: None)
    monkeypatch.setattr(catalog_menus, "ListItem", lambda *args, **kwargs: MagicMock())
    monkeypatch.setattr(
        catalog_menus,
        "build_url",
        lambda action, **kwargs: f"plugin://{action}",
    )
    monkeypatch.setattr(
        catalog_menus,
        "addDirectoryItem",
        lambda handle, url, listitem, isFolder=True: added_urls.append(url),
    )
    monkeypatch.setattr(catalog_menus.cache, "get", lambda key: None)
    monkeypatch.setattr(catalog_menus, "get_addon_by_base_url", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "add_tmdb_show_context_menu", lambda *args, **kwargs: [])

    catalog_menus.search_catalog(
        {
            "page": 1,
            "addon_url": "https://anime-kitsu.strem.fun",
            "catalog_type": "anime",
            "catalog_id": "kitsu-anime-list",
            "menu_type": "anime",
            "sub_menu_type": "series",
            "has_meta_resource": True,
        }
    )

    assert added_urls == ["plugin://list_stremio_seasons"]


def test_run_search_entry_preserves_stremio_route_in_library_payload(monkeypatch):
    captured = {}

    monkeypatch.setattr(search, "_handle_super_quick_play", lambda params: False)
    monkeypatch.setattr(search, "set_content_type", lambda *args, **kwargs: None)
    monkeypatch.setattr(search, "search_client", lambda *args, **kwargs: [object()])
    monkeypatch.setattr(search, "_process_search_results", lambda *args, **kwargs: [object()])
    monkeypatch.setattr(search, "auto_play_enabled", lambda: False)
    monkeypatch.setattr(search, "show_source_select", lambda *args, **kwargs: True)

    def _set_watched_title(title, ids, mode, tg_data="", media_type="", library_data=None):
        captured["title"] = title
        captured["ids"] = ids
        captured["mode"] = mode
        captured["media_type"] = media_type
        captured["library_data"] = library_data

    monkeypatch.setattr(search, "set_watched_title", _set_watched_title)

    search.run_search_entry(
        {
            "query": "Jigokuraku",
            "mode": "tv",
            "media_type": "tv",
            "ids": json.dumps({"imdb_id": "tt123", "original_id": "kitsu:jigokuraku-2"}),
            "tv_data": json.dumps({"name": "Jigokuraku", "season": 1, "episode": 1}),
            "scoped_addon_url": "https://anime-kitsu.strem.fun",
            "stremio_addon_url": "https://anime-kitsu.strem.fun",
            "stremio_catalog_type": "anime",
            "stremio_meta_id": "kitsu:jigokuraku-2",
        }
    )

    assert captured["library_data"] == {
        "source": "stremio_catalog",
        "addon_url": "https://anime-kitsu.strem.fun",
        "catalog_type": "anime",
        "meta_id": "kitsu:jigokuraku-2",
    }


def test_search_catalog_backfills_missing_menu_type(monkeypatch):
    monkeypatch.setattr(
        catalog_menus,
        "catalogs_get_cache",
        lambda *args, **kwargs: {"metas": []},
    )
    monkeypatch.setattr(catalog_menus, "add_meta_items", lambda metas, params: (_ for _ in ()).throw(AssertionError(params)))
    monkeypatch.setattr(catalog_menus, "show_keyboard", lambda *args, **kwargs: "paradise")
    monkeypatch.setattr(catalog_menus.cache, "add_to_list", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus.PickleDatabase, "set_key", lambda self, key, value: None)
    monkeypatch.setattr(catalog_menus, "add_next_button", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "end_of_directory", lambda *args, **kwargs: None)

    captured = {}

    def _add_meta_items(metas, params):
        captured.update(params)

    monkeypatch.setattr(catalog_menus, "add_meta_items", _add_meta_items)

    catalog_menus.search_catalog(
        {
            "page": 1,
            "addon_url": "https://anime-kitsu.strem.fun",
            "catalog_type": "anime",
            "catalog_id": "kitsu-anime-list",
        }
    )

    assert captured["menu_type"] == "anime"
    assert captured["sub_menu_type"] == ""


def test_clear_stremio_search_history_clears_only_current_catalog(monkeypatch):
    cleared = []
    shown = []

    monkeypatch.setattr(catalog_menus.cache, "clear_list", lambda key: cleared.append(key))
    monkeypatch.setattr(catalog_menus, "_show_search_catalog_history", lambda params: shown.append(params))

    params = {
        "addon_url": "https://anime-kitsu.strem.fun",
        "catalog_type": "anime",
        "catalog_id": "kitsu-search",
    }

    catalog_menus.clear_stremio_search_history(params)

    assert cleared == ["stremio_search_catalog|https://anime-kitsu.strem.fun|anime|kitsu-search"]
    assert shown == [params]


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
    monkeypatch.setattr(catalog_menus.cache, "get", lambda key: None)
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


def test_list_stremio_episodes_main_search_url_preserves_stremio_route(monkeypatch):
    captured_urls = []

    meta_data = Meta.from_dict(
        {
            "id": "kitsu:jigokuraku-2",
            "type": "series",
            "name": "Jigokuraku 2nd Season",
            "poster": "poster.jpg",
            "background": "fanart.jpg",
            "genres": ["Anime"],
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

    monkeypatch.setattr(
        catalog_menus,
        "catalogs_get_cache",
        lambda *args, **kwargs: {"meta": meta_data},
    )
    monkeypatch.setattr(catalog_menus, "tmdb_get", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "get_addon_by_base_url", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "addon_has_stream", lambda *args, **kwargs: False)
    monkeypatch.setattr(catalog_menus, "notification", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "end_of_directory", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "setContent", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "ListItem", lambda *args, **kwargs: MagicMock())
    monkeypatch.setattr(
        catalog_menus,
        "build_url",
        lambda action, **kwargs: captured_urls.append((action, kwargs)) or f"plugin://{action}",
    )
    monkeypatch.setattr(catalog_menus, "addDirectoryItem", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "add_tmdb_episode_context_menu", lambda *args, **kwargs: [])

    catalog_menus.list_stremio_episodes(
        {
            "addon_url": "https://anime-kitsu.strem.fun",
            "catalog_type": "anime",
            "meta_id": "kitsu:jigokuraku-2",
            "season": "1",
        }
    )

    search_calls = [kwargs for action, kwargs in captured_urls if action == "search"]
    assert len(search_calls) == 1
    assert search_calls[0]["stremio_addon_url"] == "https://anime-kitsu.strem.fun"
    assert search_calls[0]["stremio_catalog_type"] == "anime"
    assert search_calls[0]["stremio_meta_id"] == "kitsu:jigokuraku-2"


def test_add_meta_items_uses_tmdb_context_menu_only_for_reliable_tmdb_ids(monkeypatch):
    added_items = []

    class _InfoTag:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None

    class _ListItem:
        def __init__(self, label=""):
            self.label = label
            self.context_menu = []

        def getVideoInfoTag(self):
            return _InfoTag()

        def setArt(self, *args, **kwargs):
            pass

        def setProperty(self, *args, **kwargs):
            pass

        def addContextMenuItems(self, items, replaceItems=False):
            self.context_menu.extend(items)

    monkeypatch.setattr(catalog_menus, "ListItem", _ListItem)
    monkeypatch.setattr(catalog_menus, "setContent", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "translation", lambda value: {90205: "Add to Library", 90116: "Open Settings"}.get(value, str(value)))
    monkeypatch.setattr(catalog_menus, "get_addon_by_base_url", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "addon_has_meta", lambda *args, **kwargs: False)
    monkeypatch.setattr(catalog_menus, "addon_has_stream", lambda *args, **kwargs: False)
    monkeypatch.setattr(catalog_menus, "build_url", lambda *args, **kwargs: "plugin://test")
    monkeypatch.setattr(catalog_menus, "kodi_play_media", lambda **kwargs: f"PlayMedia({kwargs['name']})")
    monkeypatch.setattr(catalog_menus, "container_update", lambda **kwargs: "Container.Update(settings)")
    monkeypatch.setattr(
        catalog_menus,
        "add_tmdb_movie_context_menu",
        lambda **kwargs: [("Extras", "extras"), ("Play Trailer", "trailer"), ("Add to Library", "tmdb-lib")],
    )
    monkeypatch.setattr(
        catalog_menus,
        "addDirectoryItem",
        lambda handle, url, listitem, isFolder=False: added_items.append(listitem),
    )

    metas = [
        MetaPreview(id="tmdb:100", type="movie", name="Reliable Movie", poster="", description="desc"),
        MetaPreview(id="custom:200", type="movie", name="Custom Movie", poster="", description="desc"),
    ]

    catalog_menus.add_meta_items(
        metas,
        {
            "addon_url": "https://example.com/addon",
            "menu_type": "movie",
            "catalog_type": "movie",
        },
    )

    reliable_menu = [label for label, _ in added_items[0].context_menu]
    custom_menu = [label for label, _ in added_items[1].context_menu]

    assert "Extras" in reliable_menu
    assert "Play Trailer" in reliable_menu
    assert reliable_menu.count("Add to Library") == 1
    assert "Open Settings" in reliable_menu
    assert "Extras" not in custom_menu
    assert "Play Trailer" not in custom_menu
    assert custom_menu == ["Add to Library", "Open Settings"]


def test_add_meta_items_resolves_tmdb_id_from_imdb_for_context_menu(monkeypatch):
    added_items = []
    captured_ids = {}

    class _InfoTag:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None

    class _ListItem:
        def __init__(self, label=""):
            self.label = label
            self.context_menu = []

        def getVideoInfoTag(self):
            return _InfoTag()

        def setArt(self, *args, **kwargs):
            pass

        def setProperty(self, *args, **kwargs):
            pass

        def addContextMenuItems(self, items, replaceItems=False):
            self.context_menu.extend(items)

    monkeypatch.setattr(catalog_menus, "ListItem", _ListItem)
    monkeypatch.setattr(catalog_menus, "setContent", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "translation", lambda value: {90205: "Add to Library", 90116: "Open Settings"}.get(value, str(value)))
    monkeypatch.setattr(catalog_menus, "get_addon_by_base_url", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "addon_has_meta", lambda *args, **kwargs: False)
    monkeypatch.setattr(catalog_menus, "addon_has_stream", lambda *args, **kwargs: False)
    monkeypatch.setattr(catalog_menus, "build_url", lambda *args, **kwargs: "plugin://test")
    monkeypatch.setattr(catalog_menus, "kodi_play_media", lambda **kwargs: f"PlayMedia({kwargs['name']})")
    monkeypatch.setattr(catalog_menus, "container_update", lambda **kwargs: "Container.Update(settings)")
    monkeypatch.setattr(
        catalog_menus.cache,
        "get",
        lambda key: type("FindResult", (), {"movie_results": [{"id": 550}], "tv_results": []})()
        if key == "find_by_imdb_id|tt0133093"
        else None,
    )

    def _movie_context_menu(**kwargs):
        captured_ids.update(kwargs["ids"])
        return [("Extras", "extras"), ("Play Trailer", "trailer")]

    monkeypatch.setattr(catalog_menus, "add_tmdb_movie_context_menu", _movie_context_menu)
    monkeypatch.setattr(
        catalog_menus,
        "addDirectoryItem",
        lambda handle, url, listitem, isFolder=False: added_items.append(listitem),
    )

    metas = [
        MetaPreview(id="tt0133093", type="movie", name="The Matrix", poster="", description="desc", imdb_id="tt0133093"),
    ]

    catalog_menus.add_meta_items(
        metas,
        {
            "addon_url": "https://example.com/addon",
            "menu_type": "movie",
            "catalog_type": "movie",
        },
    )

    menu_labels = [label for label, _ in added_items[0].context_menu]
    assert captured_ids["tmdb_id"] == "550"
    assert "Extras" in menu_labels
    assert "Play Trailer" in menu_labels
    assert menu_labels.count("Open Settings") == 1


def test_list_stremio_movie_builds_enriched_play_media_payload(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        catalog_menus,
        "catalogs_get_cache",
        lambda *args, **kwargs: {
            "streams": [
                type(
                    "Stream",
                    (),
                    {"title": "Movie Stream", "description": "Stream plot", "url": "https://video", "infoHash": ""},
                )()
            ]
        },
    )
    monkeypatch.setattr(catalog_menus, "notification", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "end_of_directory", lambda *args, **kwargs: None)
    monkeypatch.setattr(catalog_menus, "ListItem", lambda *args, **kwargs: MagicMock())
    monkeypatch.setattr(catalog_menus, "addDirectoryItem", lambda *args, **kwargs: None)

    def _build_url(action, **kwargs):
        captured["action"] = action
        captured["data"] = json.loads(kwargs["data"])
        return "plugin://test"

    monkeypatch.setattr(catalog_menus, "build_url", _build_url)

    catalog_menus.list_stremio_movie(
        {
            "addon_url": "https://example.com/addon",
            "catalog_type": "movie",
            "meta_id": "custom:movie",
            "ids": json.dumps({"tmdb_id": "100", "imdb_id": "tt100", "original_id": "custom:movie"}),
            "poster": "poster.jpg",
            "fanart": "fanart.jpg",
            "genres": json.dumps(["Drama"]),
            "overview": "Catalog overview",
        }
    )

    assert captured["action"] == "play_media"
    assert captured["data"] == {
        "mode": "movie",
        "source": "stremio_catalog",
        "title": "Movie Stream",
        "overview": "Stream plot",
        "poster": "poster.jpg",
        "fanart": "fanart.jpg",
        "genres": ["Drama"],
        "ids": {"tmdb_id": "100", "imdb_id": "tt100", "original_id": "custom:movie"},
        "addon_url": "https://example.com/addon",
        "catalog_type": "movie",
        "meta_id": "custom:movie",
        "url": "https://video",
        "type": catalog_menus.IndexerType.DIRECT,
    }
