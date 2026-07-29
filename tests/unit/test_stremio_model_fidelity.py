from lib.api.stremio.models import Stream
from lib.clients.stremio import playback as stremio_playback


def test_archive_objects_servers_and_behavior_hints_survive_normalization():
    archive = {"url": "https://example.com/archive", "name": "part"}
    stream = Stream.from_dict({"rarUrls": [archive], "servers": [{"url": "https://example.com/server"}], "fileMustInclude": "*.mkv", "behaviorHints": {"countryAllowlist": ["US"], "countryDenylist": ["CA"], "bingeGroup": "group-value", "notWebReady": True}})

    candidate = stremio_playback.normalize_stream(stream)

    assert stream.fileMustInclude == "*.mkv"
    assert candidate.archiveUrls == [archive]
    assert candidate.servers == [{"url": "https://example.com/server"}]
    assert candidate.metadata["behaviorHints"] == {"countryWhitelist": ["US"], "countryBlacklist": ["CA"], "bingeGroup": "group-value", "notWebReady": True}
    decision = stremio_playback.classify(candidate)
    assert decision.code == "unsupported_archive"
    assert decision.reason == "Archive and Usenet sources are not supported."
