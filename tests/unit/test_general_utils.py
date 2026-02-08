import pytest
from lib.utils.general.utils import (
    is_url,
    is_magnet_link,
    info_hash_to_magnet,
    supported_video_extensions,
)


def test_is_url():
    assert is_url("http://example.com") is not None
    assert is_url("https://example.com/path?query=1") is not None
    assert is_url("ftp://example.com") is not None
    assert not is_url("not a url")
    assert not is_url("")


def test_is_magnet_link():
    magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678"
    assert is_magnet_link(magnet) == magnet
    assert is_magnet_link("http://example.com") is None
    assert is_magnet_link("not a magnet") is None


def test_info_hash_to_magnet():
    info_hash = "1234567890abcdef1234567890abcdef12345678"
    magnet = info_hash_to_magnet(info_hash)
    assert info_hash in magnet
    assert magnet.startswith("magnet:?xt=urn:btih:")


def test_supported_video_extensions():
    exts = supported_video_extensions()
    assert isinstance(exts, (list, tuple))
    assert ".mp4" in exts
    assert ".mkv" in exts
    assert ".avi" in exts
    # .ts is in getSupportedMedia but also in non_direct_exts? No, let's check non_direct_exts.
    # Actually non_direct_exts contains .ts? Let's check.
