import json
from unittest.mock import MagicMock

from lib.api.stremio.addon_manager import AddonManager
from lib.clients.nuvio import addon_selection
from lib.clients.nuvio.constants import NUVIO_ADDONS_KEY, NUVIO_USER_ADDONS
from lib.clients.nuvio.helpers import get_selected_stream_addon_records, get_selected_stream_addons
from lib.clients.stremio.addon_client import StremioAddonClient
from lib.clients.stremio.constants import STREMIO_ADDONS_KEY, STREMIO_USER_ADDONS


def _manifest(name="Nuvio Stream"):
    return {"id": "nuvio.stream", "name": name, "types": ["movie"], "resources": ["stream"]}


def _record(manifest=None):
    return {
        "manifest": manifest or _manifest(),
        "transportUrl": "https://addon.example/private/manifest.json",
        "transportName": "nuvio",
    }


def test_nuvio_selection_persists_only_nuvio_cache_keys(monkeypatch):
    cache = MagicMock()
    cache.get.return_value = []
    dialog = MagicMock()
    dialog.multiselect.return_value = [0]
    monkeypatch.setattr(addon_selection, "cache", cache)
    monkeypatch.setattr(addon_selection.xbmcgui, "Dialog", lambda: dialog)
    monkeypatch.setattr(
        addon_selection.NuvioClient,
        "get_addons",
        lambda _self: [
            {
                "url": "https://addon.example/private/manifest.json",
                "name": "Remote",
                "enabled": True,
                "sort_order": 1,
            }
        ],
    )
    monkeypatch.setattr(addon_selection, "_fetch_manifest", lambda _url: (_manifest(), _url))

    addon_selection.nuvio_toggle_addons()

    saved_keys = [call.args[0] for call in cache.set.call_args_list]
    assert saved_keys == [NUVIO_USER_ADDONS, NUVIO_ADDONS_KEY]
    assert STREMIO_USER_ADDONS not in saved_keys
    assert STREMIO_ADDONS_KEY not in saved_keys


def test_nuvio_selection_preserves_existing_records_when_remote_load_fails(monkeypatch):
    cache = MagicMock()
    cache.get.side_effect = lambda key: {
        NUVIO_USER_ADDONS: [_record()],
        NUVIO_ADDONS_KEY: json.dumps(["nuvio.stream|selection"]),
    }.get(key)
    dialog = MagicMock()
    monkeypatch.setattr(addon_selection, "cache", cache)
    monkeypatch.setattr(addon_selection.xbmcgui, "Dialog", lambda: dialog)
    monkeypatch.setattr(addon_selection.NuvioClient, "get_addons", lambda _self: None)

    addon_selection.nuvio_toggle_addons()

    cache.set.assert_not_called()
    dialog.ok.assert_called_once_with(
        addon_selection.translation(91018), addon_selection.translation(91022)
    )


def test_nuvio_manifest_fetch_accepts_safe_manifest_and_rejects_insecure_url(monkeypatch):
    response = MagicMock()
    response.url = "https://addon.example/private/manifest.json"
    response.headers = {}
    response.iter_content.return_value = [json.dumps(_manifest()).encode("utf-8")]
    monkeypatch.setattr(addon_selection, "_is_safe_http_url", lambda _url: True)
    monkeypatch.setattr(addon_selection, "_request_with_safe_redirects", lambda _url: response)

    manifest, url = addon_selection._fetch_manifest(response.url)

    assert manifest["id"] == "nuvio.stream"
    assert url == response.url
    requests_get = MagicMock()
    monkeypatch.setattr(addon_selection.requests, "get", requests_get)
    try:
        addon_selection._fetch_manifest("http://addon.example/private/manifest.json")
    except ValueError as error:
        assert str(error) == "invalid manifest URL"
    else:
        raise AssertionError("insecure manifests must be rejected")
    requests_get.assert_not_called()


def test_nuvio_selected_addons_are_loaded_without_stremio_records(monkeypatch):
    record = _record()
    selected_key = addon_selection._addon_key(record)
    monkeypatch.setattr(
        "lib.clients.nuvio.helpers.cache.get",
        lambda key: {NUVIO_USER_ADDONS: [record], NUVIO_ADDONS_KEY: [selected_key]}.get(key),
    )

    addons = get_selected_stream_addons()

    assert len(addons) == 1
    assert addons[0].transport_name == "nuvio"


def test_nuvio_source_manager_records_are_read_from_nuvio_cache_only(monkeypatch):
    record = _record()
    selected_key = addon_selection._addon_key(record)
    monkeypatch.setattr(
        "lib.clients.nuvio.helpers.cache.get",
        lambda key: {NUVIO_USER_ADDONS: [record], NUVIO_ADDONS_KEY: [selected_key]}.get(key),
    )

    records = get_selected_stream_addon_records()

    assert records == [{"key": selected_key, "name": "Nuvio Stream"}]


def test_nuvio_streams_keep_an_explicit_nuvio_presentation_label():
    addon = AddonManager([_record()]).addons[0]

    client = StremioAddonClient(addon)

    assert client.indexer_name == "Nuvio"
    assert client.instance_label == "Nuvio Stream (Nuvio)"
