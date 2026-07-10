"""Unit tests for Stremio subtitle addon discovery (multi-source).

Seeded with T1 resolver tests in T1, extended by T8 with the F1-F9 / EC1-EC6 cases.

Covers:
- T1: AddonManager.get_addon_by_key
- T2: OpenSubtitleStremioClient multi-source behavior (F1, F3, F4, F6, F7, F8, EC1-EC6)
- T6: legacy migration memento (F5)
- T3: stremio_subtitle_addons_select (CSV roundtrip - F2)
"""

import json

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _manifest(manifest_id, resources=None, types=None, name=None):
    """Build a minimal manifest dict that AddonManager._parse_addons accepts."""
    types = types or ["movie", "series"]
    resources = resources or [
        {"name": "subtitles", "types": types, "idPrefixes": ["tt"]},
    ]
    return {
        "id": manifest_id,
        "version": "0.0.1",
        "name": name or manifest_id,
        "description": "test",
        "types": types,
        "resources": resources,
        "catalogs": [],
        "idPrefixes": ["tt"],
        "behaviorHints": {},
    }


def _addon_item(manifest_id, transport_url, transport_name="addon", name=None):
    return {
        "transportUrl": transport_url,
        "transportName": transport_name,
        "manifest": _manifest(manifest_id, name=name),
    }


@pytest.fixture
def settings_store():
    """Local setting stub isolated per test (does NOT mutate global state)."""
    return {
        "stremio_subtitle_addons": "",
        "stremio_subtitle_addons_migrated": False,
        "stremio_sub_addon_host": "",
        "subtitle_language": "English",
        "auto_subtitle_download": False,
        "stremio_timeout": 10,
    }


@pytest.fixture
def patch_opensubstremio_settings(monkeypatch, settings_store):
    """Apply ``settings_store`` to ``opensubstremio.get_setting``/``set_setting``.

    Keeps the test isolated from conftest / process state.
    """
    from lib.clients.subtitle import opensubstremio

    def _get(key, default=None):
        if key in settings_store:
            value = settings_store[key]
            return value if value is not None else default
        return default

    def _set(key, value):
        settings_store[key] = value

    monkeypatch.setattr(opensubstremio, "get_setting", _get)
    monkeypatch.setattr(opensubstremio, "set_setting", _set)
    monkeypatch.setattr(opensubstremio, "subtitle_automation_enabled", lambda: False)
    return settings_store


# ---------------------------------------------------------------------------
# T1 - AddonManager.get_addon_by_key
# ---------------------------------------------------------------------------


def test_get_addon_by_key_hit():
    from lib.api.stremio.addon_manager import AddonManager

    src = [
        _addon_item("a.example", "https://a.example/manifest.json"),
        _addon_item("b.example", "https://b.example/manifest.json"),
    ]
    manager = AddonManager(json.dumps(src))
    target = manager.addons[1]
    assert manager.get_addon_by_key(target.key()) is target


def test_get_addon_by_key_miss_returns_none():
    from lib.api.stremio.addon_manager import AddonManager

    src = [_addon_item("a.example", "https://a.example/manifest.json")]
    manager = AddonManager(json.dumps(src))
    assert manager.get_addon_by_key("nope|https://nope/manifest.json") is None


def test_get_addon_by_key_first_match_wins():
    from lib.api.stremio.addon_manager import AddonManager

    # Two addons intentionally resolved to the same normalized transport_url
    # so that build_addon_instance_key returns the same key for both.
    src = [
        _addon_item("a.example", "https://a.example/manifest.json", name="A"),
        _addon_item("a.example", "https://a.example", name="A-dup"),
    ]
    manager = AddonManager(json.dumps(src))
    keys = {a.key() for a in manager.addons}
    assert len(keys) == 1  # precondition: keys match
    key = next(iter(keys))
    result = manager.get_addon_by_key(key)
    assert result is manager.addons[0]


# ---------------------------------------------------------------------------
# T8 - F1: discover subtitle-capable addons
# ---------------------------------------------------------------------------


def test_discover_subtitle_addons():
    """F1: AddonManager.get_addons_with_resource('subtitles') returns
    addons whose manifest declares a subtitles resource, excluding
    org.stremio.local and non-subtitle resources.
    """
    from lib.api.stremio.addon_manager import AddonManager

    src = [
        _addon_item(
            "a.example",
            "https://a.example/manifest.json",
            name="A",
        ),
        # stream-only addon: should be excluded
        {
            "transportUrl": "https://b.example/manifest.json",
            "transportName": "addon",
            "manifest": _manifest(
                "b.example",
                name="B",
                resources=[{"name": "stream", "types": ["movie"], "idPrefixes": ["tt"]}],
            ),
        },
        # second subtitle addon
        _addon_item(
            "c.example",
            "https://c.example/manifest.json",
            name="C",
        ),
    ]
    manager = AddonManager(json.dumps(src))
    result = manager.get_addons_with_resource("subtitles")
    result_ids = [a.manifest.id for a in result]
    assert "a.example" in result_ids
    assert "c.example" in result_ids
    assert "b.example" not in result_ids


# ---------------------------------------------------------------------------
# T8 - F2: CSV roundtrip (NOT JSON) for stremio_subtitle_addons
# ---------------------------------------------------------------------------


def test_csv_roundtrip(patch_opensubstremio_settings):
    """F2: the new explicit-select setting is stored as CSV, not JSON.

    The selection handler (T3) writes via ``",".join(...)`` and reads via
    ``str(...).split(",")`` to match the existing ``stremio_bypass_addon_list``
    convention.  The client reads the same way in :meth:`get_subtitles`.
    """

    store = patch_opensubstremio_settings
    # Simulate handler write of two keys.
    keys = [
        "community.opensubtitlesv3.pro|https://opensubtitlesv3-pro.example/eyJ4/",
        "other.addon|https://other.example/",
    ]
    store["stremio_subtitle_addons"] = ",".join(keys)

    # The client must split CSV.
    raw = str(store["stremio_subtitle_addons"] or "").strip()
    parsed = [k.strip() for k in raw.split(",") if k.strip()]
    assert parsed == keys

    # It is NOT JSON.
    with pytest.raises(ValueError):
        json.loads(parsed[0])


# ---------------------------------------------------------------------------
# T8 - F3: empty selection => no HTTP
# ---------------------------------------------------------------------------


def test_empty_selection_no_http(monkeypatch, patch_opensubstremio_settings):
    """F3: with empty selection AND no legacy host, the external lookup is
    skipped entirely; no HTTP request is made.
    """
    from lib.clients.subtitle import opensubstremio
    from lib.clients.subtitle.opensubstremio import OpenSubtitleStremioClient

    patch_opensubstremio_settings["stremio_subtitle_addons"] = ""
    patch_opensubstremio_settings["stremio_sub_addon_host"] = ""

    def _fail_get(*args, **kwargs):
        raise AssertionError("HTTP must NOT be called on empty selection")

    monkeypatch.setattr(opensubstremio.requests, "get", _fail_get)

    client = OpenSubtitleStremioClient(lambda *_a, **_k: None)
    result = client.get_subtitles("movie", "tt0111161", auto_select=True)
    assert result is None


# ---------------------------------------------------------------------------
# T8 - F4: merge + dedup by url
# ---------------------------------------------------------------------------


def test_merge_dedup_by_url(monkeypatch, patch_opensubstremio_settings):
    """F4: K1 returns [s1(url=u1), s2] and K2 returns [s3(url=u1), s4]
    -> merged deduped result is [s1, s2, s4] (u1 dup removed; first-seen
    from K1 kept).
    """
    from lib.api.stremio.addon_manager import AddonManager
    from lib.clients.subtitle.opensubstremio import OpenSubtitleStremioClient

    src = [
        _addon_item("k1", "https://k1.example/manifest.json", name="K1"),
        _addon_item("k2", "https://k2.example/manifest.json", name="K2"),
    ]
    manager = AddonManager(json.dumps(src))

    responses = {
        "k1.example": [
            {"id": "s1", "url": "https://cdn/u1.srt", "lang": "eng"},
            {"id": "s2", "url": "https://cdn/u2.srt", "lang": "eng"},
        ],
        "k2.example": [
            {"id": "s3", "url": "https://cdn/u1.srt", "lang": "eng"},
            {"id": "s4", "url": "https://cdn/u4.srt", "lang": "eng"},
        ],
    }

    def _fetch(self, base_url, *args, **kwargs):
        host = base_url.split("//", 1)[-1].split("/", 1)[0]
        return responses.get(host)

    keys = [a.key() for a in manager.addons]
    patch_opensubstremio_settings["stremio_subtitle_addons"] = ",".join(keys)
    monkeypatch.setattr(
        OpenSubtitleStremioClient,
        "_fetch_subtitles_data_for_source",
        _fetch,
    )

    client = OpenSubtitleStremioClient(lambda *_a, **_k: None)
    merged = client.get_subtitles("movie", "tt0111161", auto_select=True, addon_manager=manager)

    assert merged is not None
    assert [s["id"] for s in merged] == ["s1", "s2", "s4"]
    # First-seen from K1 won the duplicate.
    assert merged[0]["id"] == "s1"


def test_manual_external_subtitles_show_their_addon_labels(
    monkeypatch, patch_opensubstremio_settings
):
    """Manual external choices identify the selected addon's display label."""
    from lib.api.stremio.addon_manager import AddonManager
    from lib.clients.subtitle import opensubstremio
    from lib.clients.subtitle.opensubstremio import OpenSubtitleStremioClient

    manager = AddonManager(
        json.dumps(
            [
                _addon_item("first", "https://first.example/manifest.json", name="First Subs"),
                _addon_item("second", "https://second.example/manifest.json", name="Second Subs"),
            ]
        )
    )
    patch_opensubstremio_settings["stremio_subtitle_addons"] = ",".join(
        addon.key() for addon in manager.addons
    )
    monkeypatch.setattr(
        OpenSubtitleStremioClient,
        "_fetch_subtitles_data_for_source",
        lambda _self, base_url, *_args, **_kwargs: [
            {
                "id": base_url,
                "url": f"{base_url}/subtitle.srt",
                "lang": "eng",
            }
        ],
    )
    created_items = []

    def _list_item(**kwargs):
        created_items.append(kwargs)
        return object()

    monkeypatch.setattr(opensubstremio.xbmcgui, "ListItem", _list_item)
    monkeypatch.setattr(opensubstremio.xbmcgui.Dialog, "multiselect", lambda *_a, **_k: [])

    client = OpenSubtitleStremioClient(lambda *_a, **_k: None)
    assert client.get_subtitles("movie", "tt0111161", addon_manager=manager) == []

    assert "First Subs (first.example, account)" in created_items[0]["label"]
    assert "Second Subs (second.example, account)" in created_items[1]["label"]
    assert all("https://" not in item["label"] for item in created_items)


def test_manual_embedded_subtitles_show_stream_source(monkeypatch, patch_opensubstremio_settings):
    """Manual embedded choices identify subtitles carried by the stream."""
    from lib.clients.subtitle import opensubstremio
    from lib.clients.subtitle.opensubstremio import OpenSubtitleStremioClient

    created_items = []

    def _list_item(**kwargs):
        created_items.append(kwargs)
        return object()

    monkeypatch.setattr(opensubstremio.xbmcgui, "ListItem", _list_item)
    monkeypatch.setattr(opensubstremio.xbmcgui.Dialog, "multiselect", lambda *_a, **_k: [])

    client = OpenSubtitleStremioClient(lambda *_a, **_k: None)
    assert client.select_subtitles([{"url": "https://cdn/embedded.srt", "lang": "eng"}]) == []

    assert "Embedded stream subtitle" in created_items[0]["label"]
    assert created_items[0]["label2"] == "English"


# ---------------------------------------------------------------------------
# T8 - EC5: dedup falls back to (sub_id, lang) when url is absent
# ---------------------------------------------------------------------------


def test_merge_dedup_by_subid_lang_fallback(monkeypatch, patch_opensubstremio_settings):
    """EC5: when url is absent, dedup uses (sub_id, lang) first-seen wins."""
    from lib.api.stremio.addon_manager import AddonManager
    from lib.clients.subtitle.opensubstremio import OpenSubtitleStremioClient

    src = [
        _addon_item("k1", "https://k1.example/manifest.json", name="K1"),
        _addon_item("k2", "https://k2.example/manifest.json", name="K2"),
    ]
    manager = AddonManager(json.dumps(src))

    responses = {
        "k1.example": [
            {"id": "abc", "lang": "eng"},  # no url
        ],
        "k2.example": [
            {"id": "abc", "lang": "eng"},  # same id+lang, no url -> dedup
            {"id": "def", "lang": "eng"},  # unique
        ],
    }

    def _fetch(self, base_url, *args, **kwargs):
        host = base_url.split("//", 1)[-1].split("/", 1)[0]
        return responses.get(host)

    keys = [a.key() for a in manager.addons]
    patch_opensubstremio_settings["stremio_subtitle_addons"] = ",".join(keys)
    monkeypatch.setattr(
        OpenSubtitleStremioClient,
        "_fetch_subtitles_data_for_source",
        _fetch,
    )

    client = OpenSubtitleStremioClient(lambda *_a, **_k: None)
    merged = client.get_subtitles("movie", "tt0111161", auto_select=True, addon_manager=manager)
    assert merged is not None
    # K1's "abc" wins, K2's "abc" is dropped, K2's "def" is kept.
    assert [s["id"] for s in merged] == ["abc", "def"]


# ---------------------------------------------------------------------------
# T8 - EC6: isSupported prefix-skip (kitsu video vs tt-only addon)
# ---------------------------------------------------------------------------


def test_idsupported_prefix_skip(monkeypatch, patch_opensubstremio_settings):
    """EC6: an addon supporting only ``tt`` queried for a ``kitsu:1`` video
    is skipped via ``isSupported`` (DEBUG logged) and not errored.
    """
    from lib.api.stremio.addon_manager import AddonManager
    from lib.clients.subtitle.opensubstremio import OpenSubtitleStremioClient

    src = [
        # only "tt" prefixes supported
        _addon_item("tt-only", "https://tt-only.example/manifest.json", name="TT Only"),
    ]
    # narrow the manifest's subtitle resource to only "tt" prefixes
    src[0]["manifest"]["resources"] = [
        {"name": "subtitles", "types": ["movie", "series"], "idPrefixes": ["tt"]},
    ]
    manager = AddonManager(json.dumps(src))

    def _fetch(self, base_url, *args, **kwargs):
        raise AssertionError("Kitsy video must not trigger HTTP on tt-only addon")

    keys = [a.key() for a in manager.addons]
    patch_opensubstremio_settings["stremio_subtitle_addons"] = ",".join(keys)
    monkeypatch.setattr(
        OpenSubtitleStremioClient,
        "_fetch_subtitles_data_for_source",
        _fetch,
    )

    client = OpenSubtitleStremioClient(lambda *_a, **_k: None)
    result = client.get_subtitles("movie", "kitsu:1", auto_select=True, addon_manager=manager)
    # No resolved sources -> result is None (silent skip).
    assert result is None


# ---------------------------------------------------------------------------
# T8 - F5: legacy migration runs once
# ---------------------------------------------------------------------------


def test_legacy_migration_once(monkeypatch, patch_opensubstremio_settings):
    """F5: first call with empty selection + legacy host queries the legacy
    host exactly once and writes the memento. The second call must NOT
    re-query the legacy host.
    """
    from lib.clients.subtitle.opensubstremio import OpenSubtitleStremioClient

    store = patch_opensubstremio_settings
    store["stremio_subtitle_addons"] = ""
    store["stremio_sub_addon_host"] = "https://legacy.example/subtitles/"
    store["stremio_subtitle_addons_migrated"] = False

    fetch_calls = []

    def _fetch(self, base_url, *args, **kwargs):
        fetch_calls.append(base_url)
        return [{"id": "L1", "url": "https://cdn/legacy.srt", "lang": "eng"}]

    monkeypatch.setattr(
        OpenSubtitleStremioClient,
        "_fetch_subtitles_data_for_source",
        _fetch,
    )

    client = OpenSubtitleStremioClient(lambda *_a, **_k: None)

    # First call: legacy queried, memento set.
    first = client.get_subtitles("movie", "tt0111161", auto_select=True)
    assert first is not None
    assert len(fetch_calls) == 1
    assert fetch_calls[0] == "https://legacy.example/subtitles"
    assert store["stremio_subtitle_addons_migrated"] is True

    # Second call: legacy NOT queried.
    fetch_calls.clear()
    second = client.get_subtitles("movie", "tt0111161", auto_select=True)
    assert second is None
    assert fetch_calls == []


# ---------------------------------------------------------------------------
# T8 - F6: autoplay timeout cap
# ---------------------------------------------------------------------------


def test_autoplay_timeout_cap(monkeypatch, patch_opensubstremio_settings):
    """F6: with auto_select=True and elapsed time exceeding AUTO_SELECT_ENDPOINT_TIMEOUT,
    the loop aborts via the cap break so remaining addons are NOT queried.
    Deterministically forces elapsed time past the cap via a fake time.monotonic
    so the behavior is pinned (removing the break in opensubstremio must fail
    this test).
    """
    import lib.clients.subtitle.opensubstremio as obs_mod
    from lib.api.stremio.addon_manager import AddonManager
    from lib.clients.subtitle.opensubstremio import OpenSubtitleStremioClient

    # Fake clock: each call advances 3 simulated seconds. Sequence produced:
    #   start = monotonic() -> 0  (start anchor recorded)
    #   iter 1 cap check: monotonic() -> 3 (elapsed 3 < cap 5 -> proceed)
    #   iter 1 fetch (returns subs), queried=1
    #   iter 2 cap check: monotonic() -> 6 (elapsed 6 >= cap 5 -> BREAK)
    # Hence only the first addon is queried; remaining 2 are skipped.
    clock = {"t": 0.0}

    def fake_monotonic():
        clock["t"] += 3.0
        return clock["t"]

    monkeypatch.setattr(obs_mod.time, "monotonic", fake_monotonic)

    src = [
        _addon_item("slow1", "https://slow1.example/manifest.json", name="Slow1"),
        _addon_item("slow2", "https://slow2.example/manifest.json", name="Slow2"),
        _addon_item("slow3", "https://slow3.example/manifest.json", name="Slow3"),
    ]
    manager = AddonManager(json.dumps(src))

    fetch_calls = []

    def _fetch(self, base_url, *args, **kwargs):
        fetch_calls.append(base_url)
        return [{"id": "x", "url": f"https://cdn/{base_url}.srt", "lang": "eng"}]

    keys = [a.key() for a in manager.addons]
    patch_opensubstremio_settings["stremio_subtitle_addons"] = ",".join(keys)
    monkeypatch.setattr(
        OpenSubtitleStremioClient,
        "_fetch_subtitles_data_for_source",
        _fetch,
    )

    client = OpenSubtitleStremioClient(lambda *_a, **_k: None)
    result = client.get_subtitles("movie", "tt0111161", auto_select=True, addon_manager=manager)

    # A result is returned (whatever was collected before the cap fired).
    assert result is not None
    # THE cap must fire: only the first addon is queried, the other two are
    # skipped. If this assertion fails, someone broke the break+cap logic.
    assert len(fetch_calls) == 1, (
        f"cap should abort after the first addon; got fetch_calls={fetch_calls}"
    )


def test_autoplay_timeout_cap_generous_path(monkeypatch, patch_opensubstremio_settings):
    """F6 (complement): when the clock is generous (elapsed < cap), all selected
    addons are queried and the result aggregates across all sources. Ensures
    the cap path does not over-aggressively bail when there is headroom.
    """
    import time as _time

    from lib.api.stremio.addon_manager import AddonManager
    from lib.clients.subtitle.opensubstremio import OpenSubtitleStremioClient

    src = [
        _addon_item("fast1", "https://fast1.example/manifest.json", name="Fast1"),
        _addon_item("fast2", "https://fast2.example/manifest.json", name="Fast2"),
        _addon_item("fast3", "https://fast3.example/manifest.json", name="Fast3"),
    ]
    manager = AddonManager(json.dumps(src))

    # Real time, no sleeps: elapsed stays well below the 5s cap.
    fetch_calls = []

    def _fetch(self, base_url, *args, **kwargs):
        fetch_calls.append(base_url)
        return [{"id": f"x{base_url}", "url": f"https://cdn/{base_url}.srt", "lang": "eng"}]

    keys = [a.key() for a in manager.addons]
    patch_opensubstremio_settings["stremio_subtitle_addons"] = ",".join(keys)
    monkeypatch.setattr(
        OpenSubtitleStremioClient,
        "_fetch_subtitles_data_for_source",
        _fetch,
    )

    client = OpenSubtitleStremioClient(lambda *_a, **_k: None)
    result = client.get_subtitles("movie", "tt0111161", auto_select=True, addon_manager=manager)

    assert result is not None
    assert len(fetch_calls) == 3, (
        f"generous cap should allow all 3 addons; got fetch_calls={fetch_calls}"
    )


# ---------------------------------------------------------------------------
# T8 - F7: independent failure isolation
# ---------------------------------------------------------------------------


def test_independent_failure_isolation(monkeypatch, patch_opensubstremio_settings):
    """F7: K1 raises / fails and K2 returns subs -> K2 subs returned,
    K1 failure logged. No abort.
    """
    from lib.api.stremio.addon_manager import AddonManager
    from lib.clients.subtitle.opensubstremio import OpenSubtitleStremioClient

    src = [
        _addon_item("k1", "https://k1.example/manifest.json", name="K1"),
        _addon_item("k2", "https://k2.example/manifest.json", name="K2"),
    ]
    manager = AddonManager(json.dumps(src))

    def _fetch(self, base_url, *args, **kwargs):
        if "k1.example" in base_url:
            return None  # failure path: HTTP 500 / network error
        return [{"id": "ok1", "url": "https://cdn/ok1.srt", "lang": "eng"}]

    keys = [a.key() for a in manager.addons]
    patch_opensubstremio_settings["stremio_subtitle_addons"] = ",".join(keys)
    monkeypatch.setattr(
        OpenSubtitleStremioClient,
        "_fetch_subtitles_data_for_source",
        _fetch,
    )

    client = OpenSubtitleStremioClient(lambda *_a, **_k: None)
    result = client.get_subtitles("movie", "tt0111161", auto_select=True, addon_manager=manager)
    assert result is not None
    assert [s["id"] for s in result] == ["ok1"]


# ---------------------------------------------------------------------------
# T8 - EC1: 200 with empty subtitles[] is NOT an error
# ---------------------------------------------------------------------------


def test_200_empty_not_error(monkeypatch, patch_opensubstremio_settings):
    """EC1: addon returns ``{"subtitles": []}`` -> 0 subs for that addon,
    no error, no abort.
    """
    from lib.api.stremio.addon_manager import AddonManager
    from lib.clients.subtitle.opensubstremio import OpenSubtitleStremioClient

    src = [_addon_item("k1", "https://k1.example/manifest.json", name="K1")]
    manager = AddonManager(json.dumps(src))

    def _fetch(self, base_url, *args, **kwargs):
        return []

    keys = [a.key() for a in manager.addons]
    patch_opensubstremio_settings["stremio_subtitle_addons"] = ",".join(keys)
    monkeypatch.setattr(
        OpenSubtitleStremioClient,
        "_fetch_subtitles_data_for_source",
        _fetch,
    )

    client = OpenSubtitleStremioClient(lambda *_a, **_k: None)
    result = client.get_subtitles("movie", "tt0111161", auto_select=True, addon_manager=manager)
    assert result is None  # no subs anywhere -> graceful no result


# ---------------------------------------------------------------------------
# T8 - EC2: trailing-slash normalization in URL builder
# ---------------------------------------------------------------------------


def test_trailing_slash_normalization(monkeypatch, patch_opensubstremio_settings):
    """EC2: a base URL with a trailing slash is normalized to exactly one
    slash before ``subtitles/...``.
    """
    from lib.clients.subtitle import opensubstremio
    from lib.clients.subtitle.opensubstremio import OpenSubtitleStremioClient

    captured = {}

    def _get(url, **kwargs):
        captured["url"] = url

        class _R:
            status_code = 200

            def json(self_inner):
                return {"subtitles": []}

        return _R()

    monkeypatch.setattr(opensubstremio.requests, "get", _get)
    client = OpenSubtitleStremioClient(lambda *_a, **_k: None)
    # The base has a trailing slash.
    client._fetch_subtitles_data_for_source("https://example.com/", "movie", "tt0111161", timeout=5)
    assert captured["url"] == "https://example.com/subtitles/movie/tt0111161.json"
    # Exactly one slash between base and "subtitles".
    assert "example.com//subtitles" not in captured["url"]


# ---------------------------------------------------------------------------
# T8 - EC3: base64 path segment preserved
# ---------------------------------------------------------------------------


def test_config_token_base_preserved(monkeypatch, patch_opensubstremio_settings):
    """EC3: a base URL with a base64 path segment is preserved as part of
    the base; the resulting endpoint = ``{base}/subtitles/movie/...``.
    """
    from lib.clients.subtitle import opensubstremio
    from lib.clients.subtitle.opensubstremio import OpenSubtitleStremioClient

    captured = {}

    def _get(url, **kwargs):
        captured["url"] = url

        class _R:
            status_code = 200

            def json(self_inner):
                return {"subtitles": []}

        return _R()

    monkeypatch.setattr(opensubstremio.requests, "get", _get)
    client = OpenSubtitleStremioClient(lambda *_a, **_k: None)
    # base64-style path segment
    base = "https://opensubtitlesv3-pro.example/eyJsYW5ncyI6WyJlbmciXX0="
    client._fetch_subtitles_data_for_source(base, "movie", "tt0111161", timeout=5)
    assert captured["url"] == (
        "https://opensubtitlesv3-pro.example"
        "/eyJsYW5ncyI6WyJlbmciXX0=/subtitles/movie/tt0111161.json"
    )


# ---------------------------------------------------------------------------
# T8 - F8: language filter applied AFTER merge+dedup
# ---------------------------------------------------------------------------


def test_lang_filter_at_merge(monkeypatch, patch_opensubstremio_settings):
    """F8: with merged set [spa, eng] and configured lang=Spanish
    (``eng`` is filtered out under auto_select).
    """
    from lib.api.stremio.addon_manager import AddonManager
    from lib.clients.subtitle.opensubstremio import OpenSubtitleStremioClient

    src = [
        _addon_item("k1", "https://k1.example/manifest.json", name="K1"),
        _addon_item("k2", "https://k2.example/manifest.json", name="K2"),
    ]
    manager = AddonManager(json.dumps(src))

    def _fetch(self, base_url, *args, **kwargs):
        host = base_url.split("//", 1)[-1].split("/", 1)[0]
        if host == "k1.example":
            return [{"id": "s1", "url": "https://cdn/s1.srt", "lang": "spa"}]
        return [{"id": "s2", "url": "https://cdn/s2.srt", "lang": "eng"}]

    keys = [a.key() for a in manager.addons]
    patch_opensubstremio_settings["stremio_subtitle_addons"] = ",".join(keys)
    patch_opensubstremio_settings["subtitle_language"] = "Spanish"
    monkeypatch.setattr(
        OpenSubtitleStremioClient,
        "_fetch_subtitles_data_for_source",
        _fetch,
    )

    client = OpenSubtitleStremioClient(lambda *_a, **_k: None)
    result = client.get_subtitles("movie", "tt0111161", auto_select=True, addon_manager=manager)
    # lang filter at merge: only spa survives.
    assert result is not None
    assert [s["id"] for s in result] == ["s1"]


# ---------------------------------------------------------------------------
# T8 - F9: end-of-phase summary log + per-source log lines
# ---------------------------------------------------------------------------


def test_summary_log_lines_emitted(monkeypatch, patch_opensubstremio_settings):
    """F9: external lookup emits a summary line with counts.
    Also verifies per-source skip log lines for unsupported addons.
    """
    from lib.api.stremio.addon_manager import AddonManager
    from lib.clients.subtitle import opensubstremio
    from lib.clients.subtitle.opensubstremio import OpenSubtitleStremioClient

    src = [
        _addon_item("k1", "https://k1.example/manifest.json", name="K1"),
    ]
    manager = AddonManager(json.dumps(src))

    captured_logs = []

    def _fake_log(message, level=None):
        captured_logs.append(message)

    monkeypatch.setattr(opensubstremio, "kodilog", _fake_log)

    def _fetch(self, base_url, *args, **kwargs):
        return [{"id": "x1", "url": "https://cdn/x1.srt", "lang": "eng"}]

    keys = [a.key() for a in manager.addons]
    patch_opensubstremio_settings["stremio_subtitle_addons"] = ",".join(keys)
    monkeypatch.setattr(
        OpenSubtitleStremioClient,
        "_fetch_subtitles_data_for_source",
        _fetch,
    )

    client = OpenSubtitleStremioClient(lambda *_a, **_k: None)
    client.get_subtitles("movie", "tt0111161", auto_select=True, addon_manager=manager)

    summary = [m for m in captured_logs if "external lookup: queried" in m]
    assert summary, f"expected summary log line, got {captured_logs!r}"
    assert "1 addon(s)" in summary[0]
    assert "1 returned 1 subs total" in summary[0]
    assert "0 failed" in summary[0]
