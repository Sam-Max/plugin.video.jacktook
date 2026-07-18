import json
from unittest.mock import MagicMock

from lib.api.stremio.addon_manager import AddonManager
from lib.clients.stremio import addon_selection


def _manifest(addon_id="configured"):
    return {
        "id": addon_id,
        "name": "Configured Addon",
        "types": ["movie"],
        "resources": ["stream"],
    }


def _response(manifest, url="https://addon.example/token/manifest.json"):
    response = MagicMock()
    response.url = url
    response.headers = {}
    response.iter_content.return_value = [json.dumps(manifest).encode("utf-8")]
    return response


def test_configurable_addons_remain_in_selection():
    manager = AddonManager(
        [
            {
                "manifest": dict(
                    _manifest(), behaviorHints={"configurationRequired": True, "configurable": True}
                ),
                "transportUrl": "https://addon.example/manifest.json",
            },
            {
                "manifest": dict(
                    _manifest("config-list"), config=[{"key": "token", "type": "text"}]
                ),
                "transportUrl": "https://config-list.example/manifest.json",
            },
        ]
    )

    assert addon_selection._filter_excluded_addons(manager.addons) == manager.addons
    assert manager.addons[1].manifest.isConfigurable()


def test_configuration_url_only_uses_standard_https_manifest_endpoint():
    manager = AddonManager(
        [
            {
                "manifest": dict(_manifest(), behaviorHints={"configurable": True}),
                "transportUrl": "https://addon.example/v1/manifest.json",
            }
        ]
    )

    assert addon_selection._configuration_url(manager.addons[0]) == "https://addon.example/v1/configure"
    manager.addons[0].transport_url = "https://addon.example/manifest.json?token=secret"
    assert addon_selection._configuration_url(manager.addons[0]) == ""
    manager.addons[0].transport_url = "http://addon.example/manifest.json"
    assert addon_selection._configuration_url(manager.addons[0]) == ""


def test_configure_addon_opens_derived_url(monkeypatch):
    manager = AddonManager(
        [
            {
                "manifest": dict(_manifest(), behaviorHints={"configurable": True}),
                "transportUrl": "https://addon.example/manifest.json",
            }
        ]
    )
    dialog = MagicMock()
    dialog.select.return_value = 0
    monkeypatch.setattr(addon_selection, "get_addons", lambda: manager)
    monkeypatch.setattr(
        addon_selection, "get_addon_display_name", lambda addon: addon.manifest.name
    )
    monkeypatch.setattr(addon_selection.xbmcgui, "Dialog", lambda: dialog)
    monkeypatch.setattr(
        addon_selection.webbrowser,
        "open",
        lambda url, new: url == "https://addon.example/configure",
    )

    addon_selection.configure_stremio_addon()

    assert dialog.ok.call_count == 0


def test_custom_import_rejects_insecure_url_without_exposing_token(monkeypatch):
    dialog = MagicMock()
    dialog.input.return_value = "http://addon.example/manifest.json?token=secret"
    kodilog = MagicMock()
    monkeypatch.setattr(addon_selection.xbmcgui, "Dialog", lambda: dialog)
    monkeypatch.setattr(addon_selection, "kodilog", kodilog)
    monkeypatch.setattr(addon_selection.requests, "get", MagicMock())

    addon_selection.add_custom_stremio_addon({})

    addon_selection.requests.get.assert_not_called()
    assert "secret" not in kodilog.call_args.args[0]
    assert "addon.example/<redacted>" in kodilog.call_args.args[0]
    assert dialog.ok.call_args.args[1] == addon_selection.translation(90838)


def test_custom_import_rejects_manifest_larger_than_limit(monkeypatch):
    response = _response(_manifest())
    response.headers = {"Content-Length": str(addon_selection.MAX_MANIFEST_BYTES + 1)}
    monkeypatch.setattr(addon_selection.requests, "get", lambda *args, **kwargs: response)

    try:
        addon_selection._fetch_manifest("https://addon.example/manifest.json")
    except ValueError as error:
        assert str(error) == "manifest too large"
    else:
        raise AssertionError("oversized manifests must be rejected")


def test_custom_import_persists_only_configured_manifest_instance(monkeypatch):
    dialog = MagicMock()
    dialog.input.return_value = "https://addon.example/token/manifest.json"
    cache = MagicMock()
    cache.get.return_value = None
    monkeypatch.setattr(addon_selection.xbmcgui, "Dialog", lambda: dialog)
    monkeypatch.setattr(addon_selection.requests, "get", lambda *args, **kwargs: _response(_manifest()))
    monkeypatch.setattr(addon_selection, "cache", cache)

    addon_selection.add_custom_stremio_addon({})

    saved_user_addons = [
        call.args[1]
        for call in cache.set.call_args_list
        if call.args[0] == addon_selection.STREMIO_USER_ADDONS
    ]
    assert saved_user_addons[0][0]["transportUrl"] == dialog.input.return_value
    assert "config" not in saved_user_addons[0][0]
