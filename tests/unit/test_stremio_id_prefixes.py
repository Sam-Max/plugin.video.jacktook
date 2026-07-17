from unittest.mock import MagicMock, patch

from lib.api.stremio.addon_manager import AddonManager
from lib.clients.stremio.addon_selection import (
    STREMIO_ADDONS_KEY,
    _filter_stream_addons_by_id_prefix,
    add_custom_stremio_addon,
)


def _addon(addon_id, prefixes, resource_types):
    return {
        "manifest": {
            "id": addon_id,
            "name": addon_id,
            "types": resource_types,
            "resources": [
                {"name": "stream", "types": resource_types, "idPrefixes": prefixes}
            ],
        },
        "transportUrl": "https://{}.example/manifest.json".format(addon_id),
    }


def test_addon_support_and_prefix_lookup_treat_empty_prefixes_as_wildcard():
    manager = AddonManager([_addon("wildcard", [], ["movie"]), _addon("imdb", ["tt:"], ["movie"])])
    wildcard, imdb = manager.addons

    assert wildcard.isSupported("stream", "movie", "tmdb")
    assert not wildcard.isSupported("stream", "series", "tmdb")
    assert not wildcard.isSupported("catalog", "movie", "tmdb")
    assert imdb.isSupported("stream", "movie", "tt")
    assert not imdb.isSupported("stream", "movie", "tmdb")
    tmdb_addons = manager.get_addons_with_resource_and_id_prefix("stream", "tmdb")
    tt_addons = manager.get_addons_with_resource_and_id_prefix("stream", "tt")
    assert [addon.manifest.id for addon in tmdb_addons] == ["wildcard"]
    assert [addon.manifest.id for addon in tt_addons] == [
        "wildcard",
        "imdb",
    ]


def test_stream_selection_only_keeps_wildcards_for_video_types():
    manager = AddonManager(
        [
            _addon("movie", [], ["movie"]),
            _addon("series", [], ["series"]),
            _addon("tv", [], ["tv"]),
            _addon("channel", [], ["channel"]),
            _addon("imdb", ["tt"], ["movie"]),
            _addon("kitsu", ["kitsu"], ["movie"]),
        ]
    )

    selected = _filter_stream_addons_by_id_prefix(manager.addons, ["tmdb"])

    assert [addon.manifest.id for addon in selected] == ["movie", "series"]


def test_add_custom_stremio_addon_only_auto_adds_video_stream_wildcards():
    manifests = [
        _addon("movie", [], ["movie"])["manifest"],
        _addon("series", [], ["series"])["manifest"],
        _addon("tv", [], ["tv"])["manifest"],
        _addon("channel", [], ["channel"])["manifest"],
    ]

    for manifest in manifests:
        dialog = MagicMock()
        dialog.input.return_value = "https://{}.example/manifest.json".format(manifest["id"])
        response = MagicMock(url=dialog.input.return_value)
        response.json.return_value = manifest
        cache = MagicMock()
        cache.get.return_value = None

        with patch("lib.clients.stremio.addon_selection.xbmcgui.Dialog", return_value=dialog):
            with patch("lib.clients.stremio.addon_selection.requests.get", return_value=response):
                with patch("lib.clients.stremio.addon_selection.cache", cache):
                    add_custom_stremio_addon({})

        saved_keys = [call.args[0] for call in cache.set.call_args_list]
        if manifest["id"] in {"movie", "series"}:
            assert STREMIO_ADDONS_KEY in saved_keys
        else:
            assert STREMIO_ADDONS_KEY not in saved_keys
