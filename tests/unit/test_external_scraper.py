"""Unit tests for the external scraper client integration.

These tests verify the data-mapping, provider-filtering and result-parsing
logic without requiring the ``script.module.magneto`` addon to be installed.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from lib.clients.external_scraper import ExternalScraperClient, _BYTES_PER_GB
from lib.domain.torrent import TorrentStream
from lib.utils.general.utils import Indexer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def external_scraper_client():
    """Return a ExternalScraperClient whose providers are not loaded yet."""
    with patch.object(ExternalScraperClient, "_init_providers", return_value=False):
        client = ExternalScraperClient("script.module.magneto", "Magneto Module", notification=MagicMock())
    return client


@pytest.fixture
def external_scraper_client_with_providers():
    """Return a ExternalScraperClient with a mocked provider list."""
    with patch.object(
        ExternalScraperClient, "_resolve_addon_path", return_value="/fake/magneto"
    ):
        with patch.object(
            ExternalScraperClient, "_init_providers", return_value=True
        ):
            client = ExternalScraperClient("script.module.magneto", "Magneto Module", notification=MagicMock())
            client.initialized = True
            client._providers = []
            return client


class FakeProvider:
    """A fake external provider that returns configurable results."""

    hasMovies = True
    hasEpisodes = True
    pack_capable = False

    def __init__(self, results=None, pack_results=None):
        self._results = results or []
        self._pack_results = pack_results or []

    def sources(self, data, hostDict):
        return list(self._results)

    def sources_packs(self, data, hostDict):
        return list(self._pack_results)


def make_provider(results=None, pack_results=None, **kwargs):
    """Return a *class* that produces FakeProvider instances with the given data."""
    class _ConfiguredProvider(FakeProvider):
        def __init__(self):
            super().__init__(results=results, pack_results=pack_results)

    for key, value in kwargs.items():
        setattr(_ConfiguredProvider, key, value)
    return _ConfiguredProvider


# ---------------------------------------------------------------------------
# _build_data
# ---------------------------------------------------------------------------

class TestBuildData:
    def test_movie_data_dict(self, external_scraper_client):
        data = external_scraper_client._build_data(
            query="Inception",
            mode="movies",
            season=None,
            episode=None,
            imdb_id="tt1375666",
            year="2010",
        )
        assert data["title"] == "Inception"
        assert data["imdb"] == "tt1375666"
        assert data["year"] == "2010"
        assert data["aliases"] == []
        assert "tvshowtitle" not in data
        assert "season" not in data
        assert "episode" not in data

    def test_tv_data_dict(self, external_scraper_client):
        data = external_scraper_client._build_data(
            query="Breaking Bad",
            mode="tv",
            season=1,
            episode=1,
            imdb_id="tt0903747",
            tvdb_id="81189",
            year="2008",
        )
        assert data["tvshowtitle"] == "Breaking Bad"
        assert data["title"] == ""  # episode name not available
        assert data["imdb"] == "tt0903747"
        assert data["tvdb"] == "81189"
        assert data["year"] == "2008"
        assert data["season"] == "1"
        assert data["episode"] == "1"
        assert "tvshowtitle" in data

    def test_empty_ids_omitted(self, external_scraper_client):
        data = external_scraper_client._build_data(
            query="Test", mode="movies", season=None, episode=None
        )
        assert "imdb" not in data
        assert "tvdb" not in data
        assert data["year"] == ""

    def test_episode_mode_treated_as_tv(self, external_scraper_client):
        data = external_scraper_client._build_data(
            query="Show", mode="episode", season=2, episode=5
        )
        assert data["tvshowtitle"] == "Show"
        assert data["season"] == "2"
        assert data["episode"] == "5"


# ---------------------------------------------------------------------------
# _map_results
# ---------------------------------------------------------------------------

class TestMapResults:
    def test_basic_movie_result(self, external_scraper_client):
        scraper_results = [
            {
                "name": "Inception 2010 1080p BluRay",
                "hash": "ABC123DEF456",
                "url": "",
                "size": 1.5,
                "seeders": 100,
                "quality": "1080p",
                "provider": "torrentio",
            }
        ]
        mapped = external_scraper_client._map_results(scraper_results, "torrentio")

        assert len(mapped) == 1
        res = mapped[0]
        assert isinstance(res, TorrentStream)
        assert res.title == "Inception 2010 1080p BluRay"
        assert res.infoHash == "abc123def456"  # lower-cased
        assert res.url == "magnet:?xt=urn:btih:abc123def456"
        assert res.size == int(1.5 * _BYTES_PER_GB)
        assert res.seeders == 100
        assert res.quality == "1080p"
        assert res.indexer == Indexer.EXTERNAL_SCRAPER
        assert res.subindexer == "torrentio"
        assert res.provider == "torrentio"
        assert res.isPack is False

    def test_result_with_existing_magnet_url(self, external_scraper_client):
        scraper_results = [
            {
                "name": "Movie",
                "hash": "HASH123",
                "url": "magnet:?xt=urn:btih:HASH123&dn=Movie",
                "size": 0,
                "seeders": 0,
                "quality": "",
            }
        ]
        mapped = external_scraper_client._map_results(scraper_results, "provider_x")
        assert mapped[0].url == "magnet:?xt=urn:btih:HASH123&dn=Movie"

    def test_pack_result(self, external_scraper_client):
        scraper_results = [
            {
                "name": "Show S01 COMPLETE",
                "hash": "PACKHASH",
                "url": "",
                "size": 4.0,
                "seeders": 50,
                "quality": "1080p",
                "package": "season",
            }
        ]
        mapped = external_scraper_client._map_results(scraper_results, "torrentio")
        assert mapped[0].isPack is True

    def test_show_pack_result(self, external_scraper_client):
        scraper_results = [
            {
                "name": "Show COMPLETE SERIES",
                "hash": "SHOWPACK",
                "url": "",
                "size": 20.0,
                "seeders": 10,
                "package": "show",
            }
        ]
        mapped = external_scraper_client._map_results(scraper_results, "torrentio")
        assert mapped[0].isPack is True

    def test_explicit_is_pack_override(self, external_scraper_client):
        """When is_pack=True is passed, force isPack even without package key."""
        scraper_results = [
            {"name": "Pack", "hash": "H", "url": "", "size": 1.0, "seeders": 1}
        ]
        mapped = external_scraper_client._map_results(
            scraper_results, "provider", is_pack=True
        )
        assert mapped[0].isPack is True

    def test_size_conversion(self, external_scraper_client):
        scraper_results = [
            {"name": "Tiny", "hash": "H", "url": "", "size": 0.5, "seeders": 1}
        ]
        mapped = external_scraper_client._map_results(scraper_results, "p")
        assert mapped[0].size == int(0.5 * _BYTES_PER_GB)

    def test_zero_size_when_missing(self, external_scraper_client):
        scraper_results = [
            {"name": "NoSize", "hash": "H", "url": "", "size": 0, "seeders": 1}
        ]
        mapped = external_scraper_client._map_results(scraper_results, "p")
        assert mapped[0].size == 0

    def test_seeders_default_to_zero(self, external_scraper_client):
        scraper_results = [
            {"name": "NoSeeders", "hash": "H", "url": "", "size": 1.0}
        ]
        mapped = external_scraper_client._map_results(scraper_results, "p")
        assert mapped[0].seeders == 0

    def test_quality_defaults_to_na(self, external_scraper_client):
        scraper_results = [
            {"name": "NoQuality", "hash": "H", "url": "", "size": 1.0, "seeders": 1}
        ]
        mapped = external_scraper_client._map_results(scraper_results, "p")
        assert mapped[0].quality == "N/A"

    def test_invalid_size_does_not_crash(self, external_scraper_client):
        scraper_results = [
            {
                "name": "BadSize",
                "hash": "H",
                "url": "",
                "size": "not_a_number",
                "seeders": 1,
            }
        ]
        mapped = external_scraper_client._map_results(scraper_results, "p")
        assert mapped[0].size == 0

    def test_empty_results_returns_empty_list(self, external_scraper_client):
        assert external_scraper_client._map_results([], "p") == []


# ---------------------------------------------------------------------------
# Provider filtering
# ---------------------------------------------------------------------------

class TestProviderFiltering:
    def test_tv_skips_movie_only_providers(self, external_scraper_client_with_providers):
        client = external_scraper_client_with_providers

        client._providers = [
            ("movie_only", make_provider(hasEpisodes=False)),
            ("tv_prov", make_provider(results=[{"name": "Ep1", "hash": "H", "size": 1}])),
        ]

        results = client.search(
            "", "Show", "tv", "tv", season=1, episode=1
        )
        assert len(results) == 1
        assert results[0].title == "Ep1"

    def test_movie_skips_tv_only_providers(self, external_scraper_client_with_providers):
        client = external_scraper_client_with_providers

        client._providers = [
            ("tv_only", make_provider(hasMovies=False)),
            ("movie_prov", make_provider(results=[{"name": "Movie", "hash": "H", "size": 1}])),
        ]

        results = client.search("", "Movie", "movies", "movies", season=0, episode=0)
        assert len(results) == 1
        assert results[0].title == "Movie"

    def test_missing_has_flags_defaults_to_included(self, external_scraper_client_with_providers):
        """Providers without hasMovies/hasEpisodes are not filtered out."""
        client = external_scraper_client_with_providers

        class NoFlagsProvider:
            pack_capable = False

            def __init__(self):
                pass

            def sources(self, data, hostDict):
                return [{"name": "Generic", "hash": "H", "size": 1}]

        client._providers = [("generic", NoFlagsProvider)]

        results = client.search("", "Title", "movies", "movies", season=0, episode=0)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# sources_packs integration
# ---------------------------------------------------------------------------

class TestPackIntegration:
    def test_tv_calls_sources_packs_when_capable(self, external_scraper_client_with_providers):
        client = external_scraper_client_with_providers

        client._providers = [
            (
                "packer",
                make_provider(
                    results=[{"name": "Ep1", "hash": "E1", "size": 1}],
                    pack_results=[
                        {"name": "S01 Pack", "hash": "S01", "size": 10, "package": "season"}
                    ],
                    pack_capable=True,
                ),
            )
        ]

        results = client.search("", "Show", "tv", "tv", season=1, episode=1)
        titles = [r.title for r in results]
        assert "Ep1" in titles
        assert "S01 Pack" in titles
        assert any(r.isPack for r in results)

    def test_tv_skips_sources_packs_when_not_capable(
        self, external_scraper_client_with_providers
    ):
        client = external_scraper_client_with_providers

        client._providers = [
            (
                "non_packer",
                make_provider(results=[{"name": "Ep1", "hash": "E1", "size": 1}]),
            )
        ]

        results = client.search("", "Show", "tv", "tv", season=1, episode=1)
        assert len(results) == 1
        assert results[0].title == "Ep1"

    def test_movie_never_calls_sources_packs(self, external_scraper_client_with_providers):
        client = external_scraper_client_with_providers

        client._providers = [
            (
                "packer",
                make_provider(
                    results=[{"name": "Movie", "hash": "M", "size": 1}],
                    pack_results=[{"name": "ShouldNotAppear", "hash": "X", "size": 1}],
                    pack_capable=True,
                ),
            )
        ]

        results = client.search("", "Movie", "movies", "movies", season=0, episode=0)
        assert len(results) == 1
        assert results[0].title == "Movie"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_provider_exception_gracefully_ignored(self, external_scraper_client_with_providers):
        client = external_scraper_client_with_providers

        class ExplodingProvider:
            hasMovies = True
            hasEpisodes = True
            pack_capable = False

            def sources(self, data, hostDict):
                raise RuntimeError("boom")

        client._providers = [
            ("boom", ExplodingProvider()),
            ("good", make_provider(results=[{"name": "Safe", "hash": "S", "size": 1}])),
        ]
        results = client.search("", "Title", "movies", "movies", season=0, episode=0)
        assert len(results) == 1
        assert results[0].title == "Safe"

    def test_sources_packs_exception_gracefully_ignored(
        self, external_scraper_client_with_providers
    ):
        client = external_scraper_client_with_providers

        class BadPacksProvider(FakeProvider):
            pack_capable = True

            def sources_packs(self, data, hostDict):
                raise RuntimeError("packs boom")

        client._providers = [
            (
                "bad_packs",
                make_provider(results=[{"name": "Ep", "hash": "E", "size": 1}]),
            )
        ]
        results = client.search("", "Show", "tv", "tv", season=1, episode=1)
        assert len(results) == 1  # sources() still works
        assert results[0].title == "Ep"

    def test_map_results_skips_invalid_items(self, external_scraper_client):
        """If one item fails to map, the rest are still processed."""
        results = [
            {"name": "Good", "hash": "H", "url": "", "size": 1, "seeders": 1},
            {"name": "Bad", "hash": None, "url": None, "size": "crash", "seeders": None},
            {"name": "AlsoGood", "hash": "G", "url": "", "size": 2, "seeders": 2},
        ]
        mapped = external_scraper_client._map_results(results, "p")
        assert len(mapped) == 3  # None hash is handled gracefully

    def test_uninitialized_client_returns_empty(self):
        with patch.object(ExternalScraperClient, "_init_providers", return_value=False):
            client = ExternalScraperClient("script.module.magneto", "Magneto Module", notification=MagicMock())
        assert client.search("", "Title", "movies", "movies", season=0, episode=0) == []


# ---------------------------------------------------------------------------
# Addon resolution
# ---------------------------------------------------------------------------

class TestAddonResolution:
    @patch("xbmcaddon.Addon")
    def test_resolve_via_xbmcaddon(self, mock_addon_class):
        mock_addon = MagicMock()
        mock_addon.getAddonInfo.return_value = "/path/to/magneto"
        mock_addon_class.return_value = mock_addon

        client = ExternalScraperClient("script.module.magneto", "Magneto Module", notification=MagicMock())
        path = client._resolve_addon_path()
        assert path == "/path/to/magneto"

    @patch("xbmcaddon.Addon", side_effect=Exception("not installed"))
    @patch("xbmc.executeJSONRPC")
    def test_resolve_via_jsonrpc_fallback(self, mock_rpc, mock_addon):
        mock_rpc.return_value = '{"result": {"addon": {"path": "/rpc/magneto"}}}'

        client = ExternalScraperClient("script.module.magneto", "Magneto Module", notification=MagicMock())
        path = client._resolve_addon_path()
        assert path == "/rpc/magneto"

    @patch("xbmcaddon.Addon", side_effect=Exception("not installed"))
    @patch("xbmc.executeJSONRPC", return_value='{"error": {}}')
    def test_resolve_returns_none_on_failure(self, mock_rpc, mock_addon):
        client = ExternalScraperClient("script.module.magneto", "Magneto Module", notification=MagicMock())
        path = client._resolve_addon_path()
        assert path is None
        assert client.initialized is False