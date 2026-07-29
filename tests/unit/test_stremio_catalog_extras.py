from lib.api.stremio.addon_manager import AddonManager
from lib.clients.stremio import catalog_menus


def _addon_item(manifest):
    return {"manifest": manifest, "transportUrl": "https://example.com/config/manifest.json"}


def test_required_catalog_extra_and_option_limit_are_enforced(monkeypatch):
    manager = AddonManager(
        [_addon_item({"id": "catalog.addon", "name": "Catalog", "types": ["movie"], "resources": ["catalog"], "catalogs": [{"type": "movie", "id": "filtered", "extra": [{"name": "genre", "isRequired": True, "options": ["Drama", "Comedy"], "optionsLimit": 1}]}]})]
    )
    captured = {}
    choices = []
    monkeypatch.setattr(catalog_menus, "get_addon_by_base_url", lambda *_args: manager.addons[0])
    monkeypatch.setattr(catalog_menus.xbmcgui.Dialog, "select", lambda self, heading, options: choices.extend(options) or 0)
    monkeypatch.setattr(catalog_menus, "catalogs_get_cache", lambda path, params, **kwargs: captured.update(kwargs) or {"metas": []})
    monkeypatch.setattr(catalog_menus, "setContent", lambda *_args: None)
    monkeypatch.setattr(catalog_menus, "end_of_directory", lambda: None)
    monkeypatch.setattr(catalog_menus, "notification", lambda *_args: None)

    catalog_menus.list_catalog({"addon_url": manager.addons[0].url(), "menu_type": "movie", "catalog_type": "movie", "catalog_id": "filtered"})

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
