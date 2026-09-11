from pathlib import Path
from unittest.mock import MagicMock

from lib.api.nuvio import NuvioClient

LANGUAGE_ROOT = (
    Path(__file__).resolve().parents[2] / "resources" / "language"
)


def _client():
    return NuvioClient(access_token="access", refresh_token="refresh", expires_at="", profile_id=2)


def _response(status_code, payload=None):
    response = MagicMock(status_code=status_code)
    response.json.return_value = payload
    return response


def _rpc_payload():
    return [
        {
            "profile_id": 2,
            "collections_json": [
                {
                    "id": "col-1",
                    "title": "My Collection",
                    "backdropImageUrl": "https://img/back.jpg",
                    "pinToTop": True,
                    "viewMode": "grid",
                    "showAllTab": False,
                    "folders": [
                        {
                            "id": "folder-1",
                            "title": "Movies",
                            "coverImageUrl": "https://img/cover.jpg",
                            "coverEmoji": "",
                            "tileShape": "square",
                            "hideTitle": False,
                            "sources": [
                                {
                                    "addonId": "com.example.addon",
                                    "type": "movie",
                                    "catalogId": "top",
                                    "provider": "addon",
                                    "genre": "Action",
                                    "title": "Top Movies",
                                    "catalog": {"id": "top", "name": "Top", "type": "movie"},
                                    "display": {"name": "Top Movies Display"},
                                    "catalogName": "Top Catalog",
                                },
                                {
                                    "addonId": "com.example.other",
                                    "type": "series",
                                    "catalogId": "shows",
                                    "provider": "addon",
                                    "catalog": {
                                        "id": "shows",
                                        "name": "Fallback Name",
                                        "type": "series",
                                    },
                                },
                                {"type": "movie"},
                            ],
                        },
                        {
                            "id": "folder-2",
                            "title": "Only Catalog Sources",
                            "coverImageUrl": "",
                            "coverEmoji": "sun",
                            "catalogSources": [
                                {
                                    "addonId": "com.example.addon",
                                    "type": "movie",
                                    "catalogId": "catalog-x",
                                }
                            ],
                        },
                        {"title": "No id"},
                    ],
                }
            ],
            "updated_at": "2024-01-01T00:00:00Z",
        },
        {"profile_id": 2},
        "junk-row",
    ]


def test_get_collections_normalizes_rpc_payload(monkeypatch):
    post = MagicMock(return_value=_response(200, _rpc_payload()))
    monkeypatch.setattr("lib.api.nuvio.requests.post", post)

    collections = _client().get_collections()

    assert collections == [
        {
            "id": "col-1",
            "title": "My Collection",
            "backdrop": "https://img/back.jpg",
            "view_mode": "grid",
            "folders": [
                {
                    "id": "folder-1",
                    "title": "Movies",
                    "cover": "https://img/cover.jpg",
                    "emoji": "",
                    "sources": [
                        {
                            "id": "",
                            "kind": "addon",
                            "label": "Top Movies",
                            "provider": "addon",
                            "type": "movie",
                            "catalog_id": "top",
                            "addon_id": "com.example.addon",
                            "media_type": "",
                            "sort_by": "",
                            "tmdb_source_type": "",
                            "filters": {},
                        },
                        {
                            "id": "",
                            "kind": "addon",
                            "label": "Fallback Name",
                            "provider": "addon",
                            "type": "series",
                            "catalog_id": "shows",
                            "addon_id": "com.example.other",
                            "media_type": "",
                            "sort_by": "",
                            "tmdb_source_type": "",
                            "filters": {},
                        },
                        {
                            "id": "",
                            "kind": "unknown",
                            "label": "",
                            "provider": "",
                            "type": "movie",
                            "catalog_id": "",
                            "addon_id": "",
                            "media_type": "",
                            "sort_by": "",
                            "tmdb_source_type": "",
                            "filters": {},
                        },
                    ],
                },
                {
                    "id": "folder-2",
                    "title": "Only Catalog Sources",
                    "cover": "",
                    "emoji": "sun",
                    "sources": [
                        {
                            "id": "",
                            "kind": "addon",
                            "label": "",
                            "provider": "",
                            "type": "movie",
                            "catalog_id": "catalog-x",
                            "addon_id": "com.example.addon",
                            "media_type": "",
                            "sort_by": "",
                            "tmdb_source_type": "",
                            "filters": {},
                        }
                    ],
                },
            ],
        }
    ]
    assert post.call_args.args[0].endswith("/rest/v1/rpc/sync_pull_collections")
    assert post.call_args.kwargs["json"] == {"p_profile_id": 2}


def test_normalize_source_keeps_tmdb_discover_family():
    source = {
        "id": "src-6P4FKCTO",
        "name": "Live-Action Romantic Comedies",
        "genre": "Live-Action Romantic Comedies",
        "title": "Live-Action Romantic Comedies",
        "sortBy": "popularity.desc",
        "tmdbId": None,
        "filters": {
            "withGenres": "35,10749",
            "voteCountGte": 75,
            "withoutGenres": "16",
            "withoutKeywords": "155477|256466",
            "withOriginalLanguage": "en",
        },
        "provider": "tmdb",
        "mediaType": "MOVIE",
        "tmdbSourceType": "DISCOVER",
    }

    normalized = NuvioClient._normalize_collection_source(source)

    assert normalized is not None
    assert normalized["kind"] == "tmdb"
    assert normalized["id"] == "src-6P4FKCTO"
    assert normalized["label"] == "Live-Action Romantic Comedies"
    assert normalized["provider"] == "tmdb"
    assert normalized["media_type"] == "movie"
    assert normalized["sort_by"] == "popularity.desc"
    assert normalized["tmdb_source_type"] == "DISCOVER"
    assert normalized["filters"] == source["filters"]
    assert normalized["type"] == ""
    assert normalized["catalog_id"] == ""
    assert normalized["addon_id"] == ""


def test_normalize_source_lowercases_tv_media_type():
    normalized = NuvioClient._normalize_collection_source(
        {"provider": "tmdb", "mediaType": "TV", "filters": {"withGenres": "18"}}
    )

    assert normalized is not None
    assert normalized["kind"] == "tmdb"
    assert normalized["media_type"] == "tv"


def test_normalize_source_keeps_addon_family():
    normalized = NuvioClient._normalize_collection_source(
        {
            "addonId": "aio-metadata",
            "type": "movie",
            "catalogId": "flixpatrol.netflix.in.movie",
            "provider": "addon",
            "genre": "None",
        }
    )

    assert normalized is not None
    assert normalized["kind"] == "addon"
    assert normalized["type"] == "movie"
    assert normalized["catalog_id"] == "flixpatrol.netflix.in.movie"
    assert normalized["addon_id"] == "aio-metadata"
    assert normalized["provider"] == "addon"
    assert normalized["filters"] == {}


def test_normalize_source_keeps_unknown_family():
    normalized = NuvioClient._normalize_collection_source({"type": "movie"})

    assert normalized is not None
    assert normalized["kind"] == "unknown"
    assert normalized["type"] == "movie"
    assert normalized["catalog_id"] == ""


def test_normalize_source_drops_only_non_dict_entries():
    assert NuvioClient._normalize_collection_source(None) is None
    assert NuvioClient._normalize_collection_source("junk") is None
    assert NuvioClient._normalize_collection_source([]) is None


def test_get_collections_returns_none_without_profile():
    assert NuvioClient(access_token="access", profile_id=None).get_collections() is None


def test_get_collections_returns_empty_list_for_valid_empty_payload(monkeypatch):
    monkeypatch.setattr(
        "lib.api.nuvio.requests.post", MagicMock(return_value=_response(200, []))
    )
    assert _client().get_collections() == []

    monkeypatch.setattr(
        "lib.api.nuvio.requests.post",
        MagicMock(return_value=_response(200, [{"collections_json": []}])),
    )
    assert _client().get_collections() == []


def test_get_collections_returns_none_on_http_error(monkeypatch):
    monkeypatch.setattr(
        "lib.api.nuvio.requests.post", MagicMock(return_value=_response(500))
    )
    assert _client().get_collections() is None


def test_get_collections_returns_none_on_invalid_json(monkeypatch):
    invalid_json = _response(200)
    invalid_json.json.side_effect = ValueError("no json")
    monkeypatch.setattr("lib.api.nuvio.requests.post", MagicMock(return_value=invalid_json))

    assert _client().get_collections() is None


def test_get_collections_returns_none_on_non_list(monkeypatch):
    monkeypatch.setattr(
        "lib.api.nuvio.requests.post",
        MagicMock(return_value=_response(200, {"unexpected": "shape"})),
    )
    assert _client().get_collections() is None


# ---------------------------------------------------------------------------
# View helpers
# ---------------------------------------------------------------------------


def _patch_view_shell(monkeypatch, view):
    item = MagicMock()
    monkeypatch.setattr(view, "make_list_item", MagicMock(return_value=item))
    add_items = MagicMock()
    monkeypatch.setattr(view, "add_directory_items_batch", add_items)
    monkeypatch.setattr(view, "setContent", MagicMock())
    monkeypatch.setattr(view, "end_of_directory", MagicMock())
    monkeypatch.setattr(view, "apply_section_view", MagicMock())
    monkeypatch.setattr(view, "set_pluging_category", MagicMock())
    monkeypatch.setattr(view, "notification", MagicMock())
    monkeypatch.setattr(view, "translation", lambda string_id: f"text-{string_id}")
    return item, add_items


def _stub_client(monkeypatch, view, collections):
    monkeypatch.setattr(
        view,
        "NuvioClient",
        MagicMock(return_value=MagicMock(get_collections=MagicMock(return_value=collections))),
    )


def _addon_source(addon_id, catalog_id, source_type):
    return {
        "id": f"src-{catalog_id}",
        "kind": "addon",
        "type": source_type,
        "catalog_id": catalog_id,
        "addon_id": addon_id,
        "provider": "addon",
        "label": catalog_id,
    }


def _tmdb_source(source_id="src-tmdb", media_type="movie"):
    return {
        "id": source_id,
        "kind": "tmdb",
        "label": "Discover Source",
        "provider": "tmdb",
        "type": "",
        "catalog_id": "",
        "addon_id": "",
        "media_type": media_type,
        "sort_by": "popularity.desc",
        "tmdb_source_type": "DISCOVER",
        "filters": {"withGenres": "35", "voteCountGte": 75},
    }


def _collections_with_sources():
    return [
        {
            "id": "col-1",
            "title": "My Collection",
            "backdrop": "",
            "view_mode": "",
            "folders": [
                {
                    "id": "folder-1",
                    "title": "Movies",
                    "cover": "",
                    "emoji": "",
                    "sources": [
                        _addon_source("com.example.addon", "top", "movie"),
                        _addon_source("com.missing.addon", "shows", "series"),
                    ],
                }
            ],
        }
    ]


def _collections_with_all_kinds():
    return [
        {
            "id": "col-1",
            "title": "My Collection",
            "backdrop": "",
            "view_mode": "",
            "folders": [
                {
                    "id": "folder-1",
                    "title": "Movies",
                    "cover": "",
                    "emoji": "",
                    "sources": [
                        _addon_source("com.example.addon", "top", "movie"),
                        _tmdb_source(),
                        {
                            "id": "src-unknown",
                            "kind": "unknown",
                            "label": "Mystery",
                            "provider": "",
                            "type": "",
                            "catalog_id": "",
                            "addon_id": "",
                            "media_type": "",
                            "sort_by": "",
                            "tmdb_source_type": "",
                            "filters": {},
                        },
                    ],
                }
            ],
        }
    ]


def test_has_nuvio_collections_follows_sync_flag(monkeypatch):
    from lib.utils.views import nuvio_collections as view

    monkeypatch.setattr(view, "is_nuvio_progress_sync_enabled", lambda: False)
    assert view.has_nuvio_collections() is False

    monkeypatch.setattr(view, "is_nuvio_progress_sync_enabled", lambda: True)
    assert view.has_nuvio_collections() is True


def test_show_nuvio_collections_builds_one_folder_per_collection(monkeypatch):
    from lib.utils.views import nuvio_collections as view

    item, add_items = _patch_view_shell(monkeypatch, view)
    _stub_client(
        monkeypatch,
        view,
        [
            {
                "id": "col-1",
                "title": "My Collection",
                "backdrop": "https://img/back.jpg",
                "view_mode": "",
                "folders": [],
            },
            {
                "id": "col-2",
                "title": "",
                "backdrop": "",
                "view_mode": "",
                "folders": [],
            },
        ],
    )

    view.show_nuvio_collections({})

    directory_items = add_items.call_args.args[0]
    assert len(directory_items) == 2

    first_url, _first_item, first_is_folder = directory_items[0]
    assert "action=nuvio_collection_folders" in first_url
    assert "collection_id=col-1" in first_url
    assert first_is_folder is True

    second_url, _second_item, second_is_folder = directory_items[1]
    assert "collection_id=col-2" in second_url
    assert second_is_folder is True

    assert view.make_list_item.call_args_list[0].kwargs["label"] == "My Collection"
    assert view.make_list_item.call_args_list[1].kwargs["label"] == "col-2"
    item.setArt.assert_any_call(
        {
            "thumb": "https://img/back.jpg",
            "fanart": "https://img/back.jpg",
            "icon": "https://img/back.jpg",
        }
    )
    view.notification.assert_not_called()


def test_show_nuvio_collections_notifies_when_empty(monkeypatch):
    from lib.utils.views import nuvio_collections as view

    _item, add_items = _patch_view_shell(monkeypatch, view)
    _stub_client(monkeypatch, view, [])

    view.show_nuvio_collections({})

    assert add_items.call_args.args[0] == []
    view.notification.assert_called_once_with("text-91052")


def test_show_nuvio_collection_sources_routes_resolved_and_unavailable(monkeypatch):
    from lib.utils.views import nuvio_collections as view

    _item, add_items = _patch_view_shell(monkeypatch, view)
    _stub_client(monkeypatch, view, _collections_with_sources())

    addon = MagicMock()
    addon.key.return_value = "com.example.addon"
    resolve = MagicMock(
        side_effect=lambda addon_key="", addon_url="": (
            addon if addon_key == "com.example.addon" else None
        )
    )
    monkeypatch.setattr(view, "resolve_catalog_addon", resolve)

    view.show_nuvio_collection_sources({"collection_id": "col-1", "folder_id": "folder-1"})

    directory_items = add_items.call_args.args[0]
    assert len(directory_items) == 2

    resolved_url, _resolved_item, resolved_is_folder = directory_items[0]
    assert "action=list_catalog" in resolved_url
    assert "addon_key=com.example.addon" in resolved_url
    assert "menu_type=movie" in resolved_url
    assert "catalog_type=movie" in resolved_url
    assert "catalog_id=top" in resolved_url
    assert resolved_is_folder is True

    unavailable_url, _unavailable_item, unavailable_is_folder = directory_items[1]
    assert "action=nuvio_collection_source_unavailable" in unavailable_url
    assert "list_catalog" not in unavailable_url
    assert unavailable_is_folder is False

    resolve.assert_any_call(addon_key="com.example.addon")
    resolve.assert_any_call(addon_key="com.missing.addon")
    view.notification.assert_not_called()


def test_show_nuvio_collection_sources_notifies_when_empty(monkeypatch):
    from lib.utils.views import nuvio_collections as view

    _item, add_items = _patch_view_shell(monkeypatch, view)
    _stub_client(
        monkeypatch,
        view,
        [
            {
                "id": "col-1",
                "title": "My Collection",
                "backdrop": "",
                "view_mode": "",
                "folders": [
                    {
                        "id": "folder-1",
                        "title": "Movies",
                        "cover": "",
                        "emoji": "",
                        "sources": [],
                    }
                ],
            }
        ],
    )
    monkeypatch.setattr(view, "resolve_catalog_addon", MagicMock(return_value=None))

    view.show_nuvio_collection_sources({"collection_id": "col-1", "folder_id": "folder-1"})

    assert add_items.call_args.args[0] == []
    view.notification.assert_called_once_with("text-91052")


def test_show_nuvio_collection_sources_missing_folder_ends_directory(monkeypatch):
    from lib.utils.views import nuvio_collections as view

    _item, add_items = _patch_view_shell(monkeypatch, view)
    _stub_client(monkeypatch, view, _collections_with_sources())

    view.show_nuvio_collection_sources({"collection_id": "col-1", "folder_id": "missing"})

    add_items.assert_not_called()
    view.end_of_directory.assert_called_once_with(cache=False)
    view.notification.assert_not_called()


def test_show_nuvio_collection_sources_routes_by_kind(monkeypatch):
    from lib.utils.views import nuvio_collections as view

    _item, add_items = _patch_view_shell(monkeypatch, view)
    _stub_client(monkeypatch, view, _collections_with_all_kinds())
    addon = MagicMock()
    addon.key.return_value = "com.example.addon"
    monkeypatch.setattr(view, "resolve_catalog_addon", MagicMock(return_value=addon))

    view.show_nuvio_collection_sources({"collection_id": "col-1", "folder_id": "folder-1"})

    directory_items = add_items.call_args.args[0]
    assert len(directory_items) == 3

    addon_url, _addon_item, addon_is_folder = directory_items[0]
    assert "action=list_catalog" in addon_url
    assert addon_is_folder is True

    tmdb_url, _tmdb_item, tmdb_is_folder = directory_items[1]
    assert "action=nuvio_collection_discover" in tmdb_url
    assert "source_id=src-tmdb" in tmdb_url
    assert tmdb_is_folder is True

    unknown_url, _unknown_item, unknown_is_folder = directory_items[2]
    assert "action=nuvio_collection_source_unavailable" in unknown_url
    assert "reason=unsupported" in unknown_url
    assert unknown_is_folder is False
    view.notification.assert_not_called()


def _discover_data(results, total_results=5, total_pages=3):
    data = MagicMock()
    data.total_results = total_results
    data.total_pages = total_pages
    data.results = results
    return data


def _patch_discover_deps(monkeypatch, view, data):
    tmdb_get = MagicMock(return_value=data)
    monkeypatch.setattr("lib.clients.tmdb.utils.utils.tmdb_get", tmdb_get)

    class _FakeTmdbClient:
        @staticmethod
        def _get_cached_tmdb_item_metadata(res, mode):
            return {"title": getattr(res, "name", "") or getattr(res, "title", "")}

    base = MagicMock()
    base.add_media_directory_item.return_value = ("item-url", MagicMock(), False)
    monkeypatch.setattr("lib.clients.tmdb.tmdb.TmdbClient", _FakeTmdbClient)
    monkeypatch.setattr("lib.clients.tmdb.base.BaseTmdbClient", base)

    set_media_info_tag = MagicMock()
    monkeypatch.setattr(view, "set_media_infoTag", set_media_info_tag)
    add_next = MagicMock()
    monkeypatch.setattr(view, "add_next_button", add_next)
    return tmdb_get, base, set_media_info_tag, add_next


def test_discover_params_maps_movie_filters():
    from lib.utils.views.nuvio_collections import _discover_params

    source = {
        "media_type": "movie",
        "sort_by": "primary_release_date.desc",
        "filters": {
            "withGenres": "35",
            "voteCountGte": 75,
            "releaseDateGte": "2020-01-01",
            "releaseDateLte": "2021-01-01",
            "withOriginalLanguage": "en",
        },
    }

    params = _discover_params(source, 2)

    assert params["with_genres"] == "35"
    assert params["vote_count.gte"] == 75
    assert params["primary_release_date.gte"] == "2020-01-01"
    assert params["primary_release_date.lte"] == "2021-01-01"
    assert params["with_original_language"] == "en"
    assert params["sort_by"] == "primary_release_date.desc"
    assert params["page"] == 2


def test_discover_params_maps_tv_release_dates():
    from lib.utils.views.nuvio_collections import _discover_params

    params = _discover_params(
        {"media_type": "tv", "sort_by": "", "filters": {"releaseDateGte": "2020-01-01"}},
        1,
    )

    assert params["first_air_date.gte"] == "2020-01-01"
    assert "primary_release_date.gte" not in params
    assert "sort_by" not in params
    assert params["page"] == 1


def test_discover_params_omits_empty_values():
    from lib.utils.views.nuvio_collections import _discover_params

    params = _discover_params(
        {
            "media_type": "movie",
            "sort_by": "",
            "filters": {"withGenres": "", "withoutGenres": None, "withKeywords": "1|2"},
        },
        3,
    )

    assert "with_genres" not in params
    assert "without_genres" not in params
    assert params["with_keywords"] == "1|2"
    assert params["page"] == 3


def test_show_nuvio_collection_discover_renders_results_and_next_page(monkeypatch):
    from lib.utils.views import nuvio_collections as view

    _item, add_items = _patch_view_shell(monkeypatch, view)
    _stub_client(monkeypatch, view, _collections_with_all_kinds())

    first = MagicMock(name="first")
    first.name = "First Show"
    first.title = ""
    first.id = 11
    first.media_type = ""
    second = MagicMock(name="second")
    second.name = ""
    second.title = "Second Movie"
    second.id = 22
    second.media_type = "movie"

    tmdb_get, base, set_media_info_tag, add_next = _patch_discover_deps(
        monkeypatch, view, _discover_data([first, second], total_pages=3)
    )

    view.show_nuvio_collection_discover(
        {
            "collection_id": "col-1",
            "folder_id": "folder-1",
            "source_id": "src-tmdb",
            "page": 1,
        }
    )

    tmdb_get.assert_called_once_with(
        "discover_movie",
        {
            "with_genres": "35",
            "vote_count.gte": 75,
            "sort_by": "popularity.desc",
            "page": 1,
        },
    )
    directory_items = add_items.call_args.args[0]
    assert len(directory_items) == 2
    assert base.add_media_directory_item.call_count == 2
    assert set_media_info_tag.call_count == 2
    add_next.assert_called_once_with(
        "nuvio_collection_discover",
        page=1,
        collection_id="col-1",
        folder_id="folder-1",
        source_id="src-tmdb",
    )
    view.end_of_directory.assert_called_once_with(cache=False)
    view.apply_section_view.assert_called_once_with("view.main")
    view.notification.assert_not_called()


def test_show_nuvio_collection_discover_no_next_page_on_last_page(monkeypatch):
    from lib.utils.views import nuvio_collections as view

    _item, _add_items = _patch_view_shell(monkeypatch, view)
    _stub_client(monkeypatch, view, _collections_with_all_kinds())
    _tmdb_get, _base, _set_media_info_tag, add_next = _patch_discover_deps(
        monkeypatch, view, _discover_data([], total_pages=3)
    )

    view.show_nuvio_collection_discover(
        {
            "collection_id": "col-1",
            "folder_id": "folder-1",
            "source_id": "src-tmdb",
            "page": 3,
        }
    )

    add_next.assert_not_called()


def test_show_nuvio_collection_discover_notifies_when_no_results(monkeypatch):
    from lib.utils.views import nuvio_collections as view

    _item, add_items = _patch_view_shell(monkeypatch, view)
    _stub_client(monkeypatch, view, _collections_with_all_kinds())
    _patch_discover_deps(monkeypatch, view, _discover_data([], total_results=0, total_pages=0))

    view.show_nuvio_collection_discover(
        {
            "collection_id": "col-1",
            "folder_id": "folder-1",
            "source_id": "src-tmdb",
            "page": 1,
        }
    )

    add_items.assert_not_called()
    view.notification.assert_called_once_with("text-91056")
    view.end_of_directory.assert_called_once_with(cache=False)


def test_show_nuvio_collections_load_failure_degrades_to_empty(monkeypatch):
    from lib.utils.views import nuvio_collections as view

    _item, add_items = _patch_view_shell(monkeypatch, view)

    class _BoomClient:
        def get_collections(self):
            raise RuntimeError("offline")

    monkeypatch.setattr(view, "NuvioClient", lambda: _BoomClient())

    view.show_nuvio_collections({})

    assert add_items.call_args.args[0] == []
    view.notification.assert_called_once_with("text-91052")


def test_load_collections_returns_empty_when_client_returns_none(monkeypatch):
    from lib.utils.views import nuvio_collections as view

    _stub_client(monkeypatch, view, None)

    assert view._load_collections() == []


def test_nuvio_collection_source_unavailable_picks_message_by_reason(monkeypatch):
    import lib.navigation as navigation

    notification = MagicMock()
    monkeypatch.setattr(navigation, "notification", notification)
    monkeypatch.setattr(navigation, "translation", lambda string_id: f"text-{string_id}")

    navigation.nuvio_collection_source_unavailable({"reason": "unsupported"})
    notification.assert_called_once_with("text-91055", time=3000)

    notification.reset_mock()
    navigation.nuvio_collection_source_unavailable({"reason": None})
    notification.assert_called_once_with("text-91053", time=3000)


def test_nuvio_collections_strings_are_defined_in_every_supported_catalogue():
    catalogues = list(LANGUAGE_ROOT.glob("*/strings.po"))
    assert len(catalogues) == 6

    for catalogue in catalogues:
        content = catalogue.read_text()
        for string_id in range(91051, 91057):
            assert content.count(f'msgctxt "#{string_id}"') == 1, catalogue
