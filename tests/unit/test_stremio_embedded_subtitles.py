from pathlib import Path

from lib.clients.subtitle import opensubstremio, submanager
from lib.clients.subtitle.opensubstremio import OpenSubtitleStremioClient
from lib.domain.torrent import TorrentStream
from lib.gui.base_window import BaseWindow
from lib.utils.general.utils import IndexerType


class _DummyWindow(BaseWindow):
    def handle_action(self, action_id, control_id=None):
        return None


def test_prepare_source_data_includes_stream_subtitles():
    window = _DummyWindow("dummy.xml", "")
    source = TorrentStream(
        type=IndexerType.STREMIO_DEBRID,
        url="https://example.com/video.mp4",
        streamSubtitles=[{"url": "https://example.com/sub.en.vtt", "lang": "eng"}],
        stremioMetadata={
            "behaviorHints": {
                "videoHash": "video-hash",
                "videoSize": 123,
                "filename": "Movie.mkv",
            }
        },
    )

    source_data = window.prepare_source_data(source, source.url, "", False)

    assert source_data["stream_subtitles"] == [
        {"url": "https://example.com/sub.en.vtt", "lang": "eng"}
    ]
    assert source_data["videoHash"] == "video-hash"
    assert source_data["size"] == 123
    assert source_data["filename"] == "Movie.mkv"


def test_embedded_subtitle_download_preserves_supported_extension(monkeypatch, tmp_path):
    class _Response:
        status_code = 200

        def iter_content(self, chunk_size=8192):
            yield b"WEBVTT\n"

    monkeypatch.setattr(opensubstremio, "get_setting", lambda key: "")
    monkeypatch.setattr(opensubstremio.requests, "get", lambda *args, **kwargs: _Response())

    client = OpenSubtitleStremioClient(lambda *_args, **_kwargs: None)
    path = client.download_subtitle(
        {"url": "https://example.com/subtitles/movie.en.vtt?token=1", "lang": "eng"},
        0,
        "tt123",
        "Movie Title",
        folder_path=str(tmp_path),
    )

    assert path.endswith(".vtt")
    assert Path(path).read_bytes() == b"WEBVTT\n"


def test_subtitle_paths_sanitize_addon_controlled_imdb_ids(monkeypatch, tmp_path):
    class _Response:
        status_code = 200

        def iter_content(self, chunk_size=8192):
            yield b"subtitle"

    monkeypatch.setattr(opensubstremio, "ADDON_PROFILE_PATH", str(tmp_path))
    monkeypatch.setattr(opensubstremio.requests, "get", lambda *args, **kwargs: _Response())

    path = OpenSubtitleStremioClient(lambda *_args, **_kwargs: None).download_subtitle(
        {"url": "https://example.com/subtitle.srt", "lang": "eng"},
        0,
        "../../outside",
        "Movie Title",
    )

    relative_path = Path(path).relative_to(tmp_path / "Subtitles")
    assert relative_path.parts[0] == ".._.._outside"


def test_subtitle_manager_preserves_normal_imdb_directory_name(monkeypatch, tmp_path):
    data = {"title": "Movie Title", "mode": "movies", "ids": {"imdb_id": "tt1234567"}}
    manager = submanager.SubtitleManager(data, lambda *_args, **_kwargs: None)
    captured = {}

    monkeypatch.setattr(submanager, "ADDON_PROFILE_PATH", str(tmp_path))

    def _get_downloaded_subtitle_paths(path):
        captured["path"] = path
        return []

    monkeypatch.setattr(manager, "get_downloaded_subtitle_paths", _get_downloaded_subtitle_paths)
    monkeypatch.setattr(manager.opensub_client, "select_subtitles", lambda *args, **kwargs: [])
    monkeypatch.setattr(manager.opensub_client, "get_subtitles", lambda *args, **kwargs: None)

    assert manager.fetch_subtitles() is None
    assert captured["path"] == str(tmp_path / "Subtitles" / "tt1234567")


def test_subtitle_manager_sanitizes_addon_controlled_imdb_directory_name(monkeypatch, tmp_path):
    manager = submanager.SubtitleManager(
        {"title": "Movie Title", "mode": "movies", "ids": {"imdb_id": "../../outside"}},
        lambda *_args, **_kwargs: None,
    )
    captured = {}

    monkeypatch.setattr(submanager, "ADDON_PROFILE_PATH", str(tmp_path))

    def _get_downloaded_subtitle_paths(path):
        captured["path"] = path
        return []

    monkeypatch.setattr(manager, "get_downloaded_subtitle_paths", _get_downloaded_subtitle_paths)
    monkeypatch.setattr(manager.opensub_client, "select_subtitles", lambda *args, **kwargs: [])
    monkeypatch.setattr(manager.opensub_client, "get_subtitles", lambda *args, **kwargs: None)

    assert manager.fetch_subtitles() is None
    assert captured["path"] == str(tmp_path / "Subtitles" / ".._.._outside")


def test_subtitle_download_rejects_empty_or_html_bodies_without_persisting(monkeypatch, tmp_path):
    class _Response:
        status_code = 200

        def __init__(self, content):
            self.content = content

        def iter_content(self, chunk_size=8192):
            yield self.content

    responses = iter([_Response(b""), _Response(b"<!doctype html><title>Error</title>")])
    monkeypatch.setattr(opensubstremio.requests, "get", lambda *args, **kwargs: next(responses))
    client = OpenSubtitleStremioClient(lambda *_args, **_kwargs: None)

    for index in range(2):
        try:
            client.download_subtitle(
                {"url": "https://example.com/subtitle.srt?token=secret", "lang": "eng"},
                index,
                "tt123",
                "Movie Title",
                folder_path=str(tmp_path),
            )
        except ValueError:
            pass
        else:
            raise AssertionError("invalid subtitle response must fail")

    assert list(tmp_path.iterdir()) == []


def test_subtitle_download_redacts_urls_from_notifications_and_logs(monkeypatch, tmp_path):
    class _Response:
        status_code = 500
        headers = {}

    messages = []
    logs = []
    url = "https://example.com/subtitle.srt?token=secret"
    monkeypatch.setattr(opensubstremio.requests, "get", lambda *args, **kwargs: _Response())
    monkeypatch.setattr(opensubstremio.time, "sleep", lambda *_args: None)
    monkeypatch.setattr(opensubstremio, "kodilog", lambda message, **_kwargs: logs.append(message))
    client = OpenSubtitleStremioClient(messages.append)

    try:
        client.download_subtitle(
            {"url": url, "lang": "eng"}, 0, "tt123", "Movie", folder_path=str(tmp_path)
        )
    except Exception:
        pass
    else:
        raise AssertionError("download must fail")

    assert all(url not in message and "token=secret" not in message for message in logs + messages)


def test_subtitle_endpoint_retries_rate_limits_with_bounded_retry_after(monkeypatch):
    class _Response:
        def __init__(self, status_code, headers=None):
            self.status_code = status_code
            self.headers = headers or {}

        def json(self):
            return {"subtitles": []}

    responses = iter([_Response(429, {"Retry-After": "999"}), _Response(200)])
    delays = []
    monkeypatch.setattr(opensubstremio.requests, "get", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(opensubstremio.time, "sleep", delays.append)

    result = OpenSubtitleStremioClient(
        lambda *_args, **_kwargs: None
    )._fetch_subtitles_data_for_source("https://example.com", "movie", "tt123", max_retries=2)

    assert result == []
    assert delays == [opensubstremio.MAX_RETRY_DELAY]


def test_subtitle_manager_tries_embedded_subtitles_before_endpoint(monkeypatch, tmp_path):
    calls = []
    data = {
        "title": "Movie Title",
        "mode": "movies",
        "ids": {"imdb_id": "tt123"},
        "stream_subtitles": [{"url": "https://example.com/sub.en.srt", "lang": "eng"}],
    }
    manager = submanager.SubtitleManager(data, lambda *_args, **_kwargs: None)

    def _select(subtitles, auto_select=False):
        calls.append("embedded")
        return subtitles

    def _endpoint(*args, **kwargs):
        calls.append("endpoint")
        return [{"url": "https://example.com/endpoint.srt", "lang": "eng"}]

    monkeypatch.setattr(manager.opensub_client, "select_subtitles", _select)
    monkeypatch.setattr(manager.opensub_client, "get_subtitles", _endpoint)
    monkeypatch.setattr(
        manager.opensub_client,
        "download_subtitles_batch",
        lambda *args, **kwargs: [str(tmp_path / "embedded.srt")],
    )
    monkeypatch.setattr(submanager, "get_setting", lambda key: False)

    assert manager.fetch_subtitles(folder_path=str(tmp_path)) == [str(tmp_path / "embedded.srt")]
    assert calls == ["embedded"]


def test_unified_automation_reuses_cached_subtitles_without_prompt(monkeypatch, tmp_path):
    data = {
        "title": "Movie Title",
        "mode": "movies",
        "ids": {"imdb_id": "tt123"},
    }
    cached_subtitle = tmp_path / "cached.srt"
    cached_subtitle.write_text("subtitle")
    manager = submanager.SubtitleManager(data, lambda *_args, **_kwargs: None)

    monkeypatch.setattr(submanager, "subtitle_automation_enabled", lambda: True)
    monkeypatch.setattr(
        submanager.xbmcgui.Dialog,
        "yesno",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not prompt")),
    )

    assert manager.fetch_subtitles(folder_path=str(tmp_path)) == [str(cached_subtitle)]


def test_disabled_automation_prompts_before_reusing_cached_subtitles(monkeypatch, tmp_path):
    data = {
        "title": "Movie Title",
        "mode": "movies",
        "ids": {"imdb_id": "tt123"},
    }
    cached_subtitle = tmp_path / "cached.srt"
    cached_subtitle.write_text("subtitle")
    manager = submanager.SubtitleManager(data, lambda *_args, **_kwargs: None)
    prompts = []

    monkeypatch.setattr(submanager, "subtitle_automation_enabled", lambda: False)
    monkeypatch.setattr(
        submanager.xbmcgui.Dialog,
        "yesno",
        lambda *_args, **_kwargs: prompts.append(True) or True,
    )

    assert manager.fetch_subtitles(folder_path=str(tmp_path)) == [str(cached_subtitle)]
    assert prompts == [True]


def test_unified_automation_filters_embedded_subtitles_without_a_dialog(monkeypatch):
    client = OpenSubtitleStremioClient(lambda *_args, **_kwargs: None)
    subtitles = [
        {"url": "https://example.com/sub.en.srt", "lang": "eng"},
        {"url": "https://example.com/sub.es.srt", "lang": "spa"},
    ]

    monkeypatch.setattr(opensubstremio, "subtitle_automation_enabled", lambda: True)
    monkeypatch.setattr(opensubstremio, "get_setting", lambda key: "English")
    monkeypatch.setattr(
        opensubstremio.xbmcgui.Dialog,
        "multiselect",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not prompt")),
    )

    assert client.select_subtitles(subtitles) == [subtitles[0]]


def test_disabled_automation_keeps_embedded_subtitle_selection_manual(monkeypatch):
    client = OpenSubtitleStremioClient(lambda *_args, **_kwargs: None)
    subtitles = [
        {"url": "https://example.com/sub.en.srt", "lang": "eng"},
        {"url": "https://example.com/sub.es.srt", "lang": "spa"},
    ]

    monkeypatch.setattr(opensubstremio, "subtitle_automation_enabled", lambda: False)
    monkeypatch.setattr(opensubstremio, "get_setting", lambda key: "English")
    monkeypatch.setattr(opensubstremio.xbmcgui.Dialog, "multiselect", lambda *_args, **_kwargs: [1])

    assert client.select_subtitles(subtitles) == [subtitles[1]]


def test_subtitle_manager_falls_back_when_no_embedded_subtitle_selected(monkeypatch, tmp_path):
    calls = []
    data = {
        "title": "Movie Title",
        "mode": "movies",
        "ids": {"imdb_id": "tt123"},
        "stream_subtitles": [{"url": "https://example.com/sub.en.srt", "lang": "eng"}],
    }
    manager = submanager.SubtitleManager(data, lambda *_args, **_kwargs: None)

    monkeypatch.setattr(
        manager.opensub_client,
        "select_subtitles",
        lambda *args, **kwargs: calls.append("embedded") or [],
    )
    monkeypatch.setattr(
        manager.opensub_client,
        "get_subtitles",
        lambda *args, **kwargs: (
            calls.append("endpoint") or [{"url": "https://example.com/endpoint.srt", "lang": "eng"}]
        ),
    )
    monkeypatch.setattr(
        manager.opensub_client,
        "download_subtitles_batch",
        lambda *args, **kwargs: [str(tmp_path / "endpoint.srt")],
    )
    monkeypatch.setattr(submanager, "get_setting", lambda key: False)

    assert manager.fetch_subtitles(folder_path=str(tmp_path)) == [str(tmp_path / "endpoint.srt")]
    assert calls == ["embedded", "endpoint"]


def test_auto_select_embedded_no_language_match_does_not_open_endpoint_dialog(
    monkeypatch, tmp_path
):
    data = {
        "title": "Movie Title",
        "mode": "movies",
        "ids": {"imdb_id": "tt123"},
        "stream_subtitles": [{"url": "https://example.com/sub.es.srt", "lang": "spa"}],
    }
    manager = submanager.SubtitleManager(data, lambda *_args, **_kwargs: None)

    # New contract: get_subtitles is the public surface; the test asserts that
    # when the endpoint returns subs but no language match under auto_select,
    # the manager reports not_selected without opening a manual dialog.
    monkeypatch.setattr(
        manager.opensub_client,
        "get_subtitles",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(submanager, "get_setting", lambda key: False)
    monkeypatch.setattr(opensubstremio, "get_setting", lambda key: "English")

    def _fail_dialog(*args, **kwargs):
        raise AssertionError("Manual subtitle dialog must not open during auto-select")

    monkeypatch.setattr(opensubstremio.xbmcgui.Dialog, "multiselect", _fail_dialog)

    assert manager.fetch_subtitles(auto_select=True, folder_path=str(tmp_path)) is None
    assert manager.last_fetch_status == "not_selected"


def test_embedded_download_failure_falls_back_to_endpoint(monkeypatch, tmp_path):
    calls = []
    data = {
        "title": "Movie Title",
        "mode": "movies",
        "ids": {"imdb_id": "tt123"},
        "stream_subtitles": [{"url": "https://example.com/sub.en.srt", "lang": "eng"}],
    }
    manager = submanager.SubtitleManager(data, lambda *_args, **_kwargs: None)

    monkeypatch.setattr(
        manager.opensub_client, "select_subtitles", lambda *args, **kwargs: data["stream_subtitles"]
    )
    monkeypatch.setattr(
        manager.opensub_client,
        "get_subtitles",
        lambda *args, **kwargs: (
            calls.append("endpoint") or [{"url": "https://example.com/endpoint.srt", "lang": "eng"}]
        ),
    )

    def _download(subtitles, *args, **kwargs):
        calls.append(subtitles[0]["url"])
        if "endpoint" in subtitles[0]["url"]:
            return [str(tmp_path / "endpoint.srt")]
        return []

    monkeypatch.setattr(manager.opensub_client, "download_subtitles_batch", _download)
    monkeypatch.setattr(submanager, "get_setting", lambda key: False)

    assert manager.fetch_subtitles(folder_path=str(tmp_path)) == [str(tmp_path / "endpoint.srt")]
    assert calls == [
        "https://example.com/sub.en.srt",
        "endpoint",
        "https://example.com/endpoint.srt",
    ]


def test_endpoint_subtitle_fetch_uses_timeout(monkeypatch):
    class _Response:
        status_code = 200

        def json(self):
            return {"subtitles": []}

    captured = {}

    def _get(url, **kwargs):
        captured["url"] = url
        captured["timeout"] = kwargs.get("timeout")
        return _Response()

    monkeypatch.setattr(opensubstremio, "get_setting", lambda key: "https://example.com/")
    monkeypatch.setattr(opensubstremio, "get_int_setting", lambda key: 7)
    monkeypatch.setattr(opensubstremio.requests, "get", _get)

    client = OpenSubtitleStremioClient(lambda *_args, **_kwargs: None)
    assert (
        client._fetch_subtitles_data_for_source("https://example.com", "movie", "tt123", timeout=7)
        == []
    )

    assert captured == {
        "url": "https://example.com/subtitles/movie/tt123.json",
        "timeout": 7,
    }


def test_subtitle_endpoint_encodes_stream_extra_args_without_logging_them(monkeypatch):
    class _Response:
        status_code = 200

        def json(self):
            return {"subtitles": []}

    captured = {}
    logs = []

    def _get(url, **kwargs):
        captured["url"] = url
        return _Response()

    monkeypatch.setattr(opensubstremio.requests, "get", _get)
    monkeypatch.setattr(opensubstremio, "kodilog", lambda message, **_kwargs: logs.append(message))

    assert OpenSubtitleStremioClient(lambda *_args: None)._fetch_subtitles_data_for_source(
        "https://example.com",
        "movie",
        "tt123",
        extra_args={
            "videoHash": "hash/with space",
            "videoSize": 123,
            "filename": "Movie & Episode.mkv",
        },
    ) == []

    assert captured["url"] == (
        "https://example.com/subtitles/movie/tt123/videoHash=hash%2Fwith%20space"
        "/videoSize=123/filename=Movie%20%26%20Episode.mkv.json"
    )
    assert all("hash/with space" not in message for message in logs)


def test_subtitle_manager_passes_selected_stream_file_context_to_endpoint(monkeypatch, tmp_path):
    data = {
        "title": "Movie Title",
        "mode": "movies",
        "ids": {"imdb_id": "tt123"},
        "videoHash": "hash-value",
        "size": 987,
        "filename": "Movie.mkv",
    }
    manager = submanager.SubtitleManager(data, lambda *_args, **_kwargs: None)
    captured = {}

    monkeypatch.setattr(manager.opensub_client, "select_subtitles", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        manager.opensub_client,
        "get_subtitles",
        lambda *args, **kwargs: captured.update(kwargs) or None,
    )

    assert manager.fetch_subtitles(folder_path=str(tmp_path)) is None
    assert captured["extra_args"] == {
        "videoHash": "hash-value",
        "videoSize": 987,
        "filename": "Movie.mkv",
    }


def test_auto_select_endpoint_subtitle_fetch_caps_timeout(monkeypatch):
    class _Response:
        status_code = 200

        def json(self):
            return {"subtitles": []}

    captured = {}

    def _get(url, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        return _Response()

    monkeypatch.setattr(opensubstremio, "get_setting", lambda key: "https://example.com/")
    monkeypatch.setattr(opensubstremio, "get_int_setting", lambda key: 120)
    monkeypatch.setattr(opensubstremio.requests, "get", _get)

    client = OpenSubtitleStremioClient(lambda *_args, **_kwargs: None)
    # Per-call timeout is supplied by the caller (get_subtitles) under
    # auto_select; this test exercises the per-source method with a capped
    # timeout arg, mirroring the new contract.
    assert (
        client._fetch_subtitles_data_for_source(
            "https://example.com",
            "movie",
            "tt123",
            timeout=opensubstremio.AUTO_SELECT_ENDPOINT_TIMEOUT,
        )
        == []
    )

    assert captured["timeout"] == opensubstremio.AUTO_SELECT_ENDPOINT_TIMEOUT


def test_auto_select_download_uses_startup_safe_timeout(monkeypatch, tmp_path):
    class _Response:
        status_code = 200

        def iter_content(self, chunk_size=8192):
            yield b"subtitle"

    captured = {}

    def _get(url, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        return _Response()

    monkeypatch.setattr(opensubstremio, "get_setting", lambda key: "")
    monkeypatch.setattr(opensubstremio.requests, "get", _get)

    client = OpenSubtitleStremioClient(lambda *_args, **_kwargs: None)
    paths = client.download_subtitles_batch(
        [{"url": "https://example.com/sub.srt", "lang": "eng"}],
        "tt123",
        title="Movie Title",
        folder_path=str(tmp_path),
        auto_select=True,
    )

    assert paths == [str(tmp_path / "Subtitle No.0.Movie Title.English.srt")]
    assert captured["timeout"] == opensubstremio.AUTO_SELECT_DOWNLOAD_TIMEOUT


def test_embedded_download_failure_endpoint_empty_sets_not_selected(monkeypatch, tmp_path):
    data = {
        "title": "Movie Title",
        "mode": "movies",
        "ids": {"imdb_id": "tt123"},
        "stream_subtitles": [{"url": "https://example.com/sub.en.srt", "lang": "eng"}],
    }
    manager = submanager.SubtitleManager(data, lambda *_args, **_kwargs: None)

    monkeypatch.setattr(
        manager.opensub_client, "select_subtitles", lambda *args, **kwargs: data["stream_subtitles"]
    )
    monkeypatch.setattr(manager.opensub_client, "get_subtitles", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        manager.opensub_client, "download_subtitles_batch", lambda *args, **kwargs: []
    )
    monkeypatch.setattr(submanager, "get_setting", lambda key: False)

    assert manager.fetch_subtitles(auto_select=True, folder_path=str(tmp_path)) is None
    assert manager.last_fetch_status == "not_selected"


def test_embedded_download_failure_endpoint_none_sets_not_found(monkeypatch, tmp_path):
    data = {
        "title": "Movie Title",
        "mode": "movies",
        "ids": {"imdb_id": "tt123"},
        "stream_subtitles": [{"url": "https://example.com/sub.en.srt", "lang": "eng"}],
    }
    manager = submanager.SubtitleManager(data, lambda *_args, **_kwargs: None)

    monkeypatch.setattr(
        manager.opensub_client, "select_subtitles", lambda *args, **kwargs: data["stream_subtitles"]
    )
    monkeypatch.setattr(manager.opensub_client, "get_subtitles", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        manager.opensub_client, "download_subtitles_batch", lambda *args, **kwargs: []
    )
    monkeypatch.setattr(submanager, "get_setting", lambda key: False)

    assert manager.fetch_subtitles(auto_select=True, folder_path=str(tmp_path)) is None
    assert manager.last_fetch_status == "not_found"


def test_auto_select_does_not_call_deepl_translation(monkeypatch, tmp_path):
    data = {
        "title": "Movie Title",
        "mode": "movies",
        "ids": {"imdb_id": "tt123"},
        "stream_subtitles": [{"url": "https://example.com/sub.en.srt", "lang": "eng"}],
    }
    manager = submanager.SubtitleManager(data, lambda *_args, **_kwargs: None)
    subtitle_path = str(tmp_path / "embedded.srt")

    monkeypatch.setattr(
        manager.opensub_client, "select_subtitles", lambda *args, **kwargs: data["stream_subtitles"]
    )
    monkeypatch.setattr(
        manager.opensub_client, "download_subtitles_batch", lambda *args, **kwargs: [subtitle_path]
    )
    monkeypatch.setattr(submanager, "get_setting", lambda key: key == "deepl_enabled")

    def _fail_translation(*args, **kwargs):
        raise AssertionError("DeepL translation must not run during auto-select")

    monkeypatch.setattr(manager.translator, "translate_multiple_subtitles", _fail_translation)

    assert manager.fetch_subtitles(auto_select=True, folder_path=str(tmp_path)) == [subtitle_path]


def test_manual_subtitle_flow_can_still_translate(monkeypatch, tmp_path):
    data = {
        "title": "Movie Title",
        "mode": "movies",
        "ids": {"imdb_id": "tt123"},
        "stream_subtitles": [{"url": "https://example.com/sub.en.srt", "lang": "eng"}],
    }
    manager = submanager.SubtitleManager(data, lambda *_args, **_kwargs: None)
    subtitle_path = str(tmp_path / "embedded.srt")
    translated_path = str(tmp_path / "translated.srt")
    translated_calls = []

    monkeypatch.setattr(
        manager.opensub_client, "select_subtitles", lambda *args, **kwargs: data["stream_subtitles"]
    )
    monkeypatch.setattr(
        manager.opensub_client, "download_subtitles_batch", lambda *args, **kwargs: [subtitle_path]
    )
    monkeypatch.setattr(submanager, "get_setting", lambda key: key == "deepl_enabled")
    monkeypatch.setattr(submanager.xbmcgui.Dialog, "yesno", lambda *args, **kwargs: True)

    def _translate(paths, imdb_id, season, episode):
        translated_calls.append((paths, imdb_id, season, episode))
        return [translated_path]

    monkeypatch.setattr(manager.translator, "translate_multiple_subtitles", _translate)

    assert manager.fetch_subtitles(folder_path=str(tmp_path)) == [translated_path]
    assert translated_calls == [([subtitle_path], "tt123", None, None)]
