from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lib.api.stremio.addon_manager import AddonManager
from lib.clients.stremio.protocol import is_safe_http_url, request_with_safe_redirects
from lib.clients.subtitle import opensubstremio, submanager


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/subtitle.srt",
        "https://user:password@example.com/subtitle.srt",
        "http://127.0.0.1/subtitle.srt",
        "http://169.254.1.1/subtitle.srt",
        "http://10.0.0.1/subtitle.srt",
    ],
)
def test_subtitle_network_policy_rejects_unsafe_destinations(url):
    assert is_safe_http_url(url, resolve_dns=False) is False


def test_redirect_target_is_rejected_before_second_request():
    calls = []

    class Redirect:
        status_code = 302
        headers = {"Location": "http://127.0.0.1/subtitle.srt"}

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Redirect()

    with pytest.raises(ValueError):
        request_with_safe_redirects(
            get,
            "https://example.com/subtitle.srt",
            validator=lambda url: not url.startswith("http://127."),
        )

    assert len(calls) == 1


def test_subtitle_download_hard_cap_removes_partial_file(monkeypatch, tmp_path):
    class Response:
        status_code = 200

        def iter_content(self, chunk_size=8192):
            yield b"x" * 6
            yield b"y" * 6

    monkeypatch.setattr(opensubstremio, "MAX_SUBTITLE_BYTES", 10)
    monkeypatch.setattr(opensubstremio, "is_safe_http_url", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(opensubstremio.requests, "get", lambda *_args, **_kwargs: Response())
    client = opensubstremio.OpenSubtitleStremioClient(lambda *_args: None)

    with pytest.raises(ValueError):
        client.download_subtitle(
            {"url": "https://example.com/subtitle.srt", "lang": "eng"},
            0,
            "item",
            "Title",
            folder_path=str(tmp_path),
        )

    assert list(Path(tmp_path).iterdir()) == []


def test_integrated_opensubtitles_can_be_disabled(monkeypatch):
    monkeypatch.setattr(
        opensubstremio,
        "get_setting",
        lambda key, default=None: False if key == "stremio_opensubtitles_enabled" else default,
    )
    client = opensubstremio.OpenSubtitleStremioClient(lambda *_args: None)
    _manager, sources = client._resolve_runtime_subtitle_sources([], AddonManager([]))

    assert sources == []


def test_embedded_subtitle_cancel_does_not_fall_back(monkeypatch, tmp_path):
    manager = submanager.SubtitleManager(
        {
            "title": "Title",
            "mode": "movies",
            "ids": {"imdb_id": "item"},
            "stream_subtitles": [{"url": "https://example.com/subtitle.srt", "lang": "eng"}],
        },
        lambda *_args: None,
    )
    monkeypatch.setattr(manager.opensub_client, "select_subtitles", lambda *_args, **_kwargs: [])
    manager.opensub_client.selection_cancelled = True
    endpoint = MagicMock()
    monkeypatch.setattr(manager.opensub_client, "get_subtitles", endpoint)

    assert manager.fetch_subtitles(folder_path=str(tmp_path)) is None
    assert manager.last_fetch_status == "cancelled"
    endpoint.assert_not_called()
