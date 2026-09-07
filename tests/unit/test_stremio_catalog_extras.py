from lib.api.stremio.addon_manager import AddonManager
from lib.clients.stremio import catalog_menus


def _addon_item(manifest):
    return {"manifest": manifest, "transportUrl": "https://example.com/config/manifest.json"}


def test_required_catalog_extra_and_option_limit_are_enforced(monkeypatch):
    manager = AddonManager(
        [
            _addon_item(
                {
                    "id": "catalog.addon",
                    "name": "Catalog",
                    "types": ["movie"],
                    "resources": ["catalog"],
                    "catalogs": [
                        {
                            "type": "movie",
                            "id": "filtered",
                            "extra": [
                                {
                                    "name": "genre",
                                    "isRequired": True,
                                    "options": ["Drama", "Comedy"],
                                    "optionsLimit": 1,
                                }
                            ],
                        }
                    ],
                }
            )
        ]
    )
    captured = {}
    choices = []
    monkeypatch.setattr(catalog_menus, "get_addon_by_base_url", lambda *_args: manager.addons[0])
    monkeypatch.setattr(
        catalog_menus.xbmcgui.Dialog,
        "select",
        lambda self, heading, options: choices.extend(options) or 0,
    )
    monkeypatch.setattr(
        catalog_menus,
        "catalogs_get_cache",
        lambda path, params, **kwargs: captured.update(kwargs) or {"metas": []},
    )
    monkeypatch.setattr(catalog_menus, "setContent", lambda *_args: None)
    monkeypatch.setattr(catalog_menus, "end_of_directory", lambda: None)
    monkeypatch.setattr(catalog_menus, "notification", lambda *_args: None)

    catalog_menus.list_catalog(
        {
            "addon_url": manager.addons[0].url(),
            "menu_type": "movie",
            "catalog_type": "movie",
            "catalog_id": "filtered",
        }
    )

    assert choices == ["Drama"]
    assert captured == {"genre": "Drama"}


def test_optional_catalog_extra_is_not_selected_or_sent_without_route_param(monkeypatch):
    manager = AddonManager(
        [
            _addon_item(
                {
                    "id": "catalog.addon",
                    "name": "Catalog",
                    "types": ["movie"],
                    "resources": ["catalog"],
                    "catalogs": [
                        {
                            "type": "movie",
                            "id": "popular",
                            "extra": [{"name": "genre", "options": ["Drama", "Comedy"]}],
                        }
                    ],
                }
            )
        ]
    )
    captured = []
    monkeypatch.setattr(catalog_menus, "get_addon_by_base_url", lambda *_args: manager.addons[0])
    monkeypatch.setattr(
        catalog_menus.xbmcgui.Dialog,
        "select",
        lambda *_args: (_ for _ in ()).throw(AssertionError("optional extra selected")),
    )
    monkeypatch.setattr(
        catalog_menus,
        "catalogs_get_cache",
        lambda _path, _params, **kwargs: captured.append(kwargs) or {"metas": []},
    )
    monkeypatch.setattr(catalog_menus, "setContent", lambda *_args: None)
    monkeypatch.setattr(catalog_menus, "end_of_directory", lambda: None)
    monkeypatch.setattr(catalog_menus, "notification", lambda *_args: None)

    params = {
        "addon_url": manager.addons[0].url(),
        "menu_type": "movie",
        "catalog_type": "movie",
        "catalog_id": "popular",
    }
    catalog_menus.list_catalog(params)
    catalog_menus.list_catalog({**params, "genre": "Drama"})

    assert captured == [{}, {"genre": "Drama"}]


def test_extra_display_name_shows_years_for_all_numeric_genre_options(monkeypatch):
    monkeypatch.setattr(
        catalog_menus, "translation", lambda value: "Years" if value == 90027 else str(value)
    )

    assert (
        catalog_menus._extra_display_name({"name": "genre", "options": ["2026", "2025", "1920"]})
        == "Years"
    )


def test_extra_display_name_keeps_genre_for_mixed_options(monkeypatch):
    monkeypatch.setattr(catalog_menus, "translation", lambda value: str(value))

    extra = {"name": "genre", "options": ["2026", "Drama"]}
    assert catalog_menus._extra_display_name(extra) == "genre"


def test_extra_display_name_keeps_original_name_for_other_extras():
    extra = {"name": "search", "options": []}
    assert catalog_menus._extra_display_name(extra) == "search"


def test_is_no_filter_options_detects_none_placeholder():
    assert catalog_menus._is_no_filter_options(["None"]) is True
    assert catalog_menus._is_no_filter_options(["none", ""]) is True
    assert catalog_menus._is_no_filter_options([]) is False
    assert catalog_menus._is_no_filter_options(["None", "Drama"]) is False
    assert catalog_menus._is_no_filter_options(["Drama"]) is False


def test_required_genre_with_only_none_option_is_skipped_without_dialog(monkeypatch):
    manager = AddonManager(
        [
            _addon_item(
                {
                    "id": "catalog.addon",
                    "name": "Catalog",
                    "types": ["movie"],
                    "resources": ["catalog"],
                    "catalogs": [
                        {
                            "type": "movie",
                            "id": "platform",
                            "extra": [
                                {"name": "genre", "isRequired": True, "options": ["None"]},
                                {"name": "skip"},
                            ],
                        }
                    ],
                }
            )
        ]
    )
    monkeypatch.setattr(catalog_menus, "get_addon_by_base_url", lambda *_args: manager.addons[0])
    monkeypatch.setattr(
        catalog_menus.xbmcgui.Dialog,
        "select",
        lambda *_args: (_ for _ in ()).throw(AssertionError("dialog shown for None-only extra")),
    )
    captured = {}
    monkeypatch.setattr(
        catalog_menus,
        "catalogs_get_cache",
        lambda _path, _params, **kwargs: captured.update(kwargs) or {"metas": []},
    )
    monkeypatch.setattr(catalog_menus, "setContent", lambda *_args: None)
    monkeypatch.setattr(catalog_menus, "end_of_directory", lambda: None)
    monkeypatch.setattr(catalog_menus, "notification", lambda *_args: None)

    catalog_menus.list_catalog(
        {
            "addon_url": manager.addons[0].url(),
            "menu_type": "movie",
            "catalog_type": "movie",
            "catalog_id": "platform",
        }
    )

    assert captured == {}
