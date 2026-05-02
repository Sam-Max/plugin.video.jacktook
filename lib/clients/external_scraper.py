import json
import os
import sys
from typing import Callable, List, Optional

from lib.clients.base import BaseClient
from lib.domain.torrent import TorrentStream
from lib.utils.general.utils import Indexer
from lib.utils.kodi.utils import kodilog


_BYTES_PER_GB = 1073741824


class ExternalScraperClient(BaseClient):
    """Generic client for external scraper modules.

    Accepts any ``xbmc.python.module`` addon that exposes a ``sources()``
    function returning provider tuples.  The module is a soft dependency:
    if the addon is not installed or fails to import, ``initialized`` is
    ``False`` and searches return an empty list.

    The data dict passed to providers:

    * Movies: ``{imdb, title, aliases, year}``
    * TV: ``{imdb, tvdb, tvshowtitle, title, aliases, year, season, episode}``
    """

    def __init__(
        self,
        module_id: str,
        module_display_name: str,
        notification: Optional[Callable],
    ) -> None:
        super().__init__(None, notification)
        self.module_id = module_id
        self.module_name = module_id.split(".")[-1]
        self.module_display_name = module_display_name
        self._sources_func = None
        self._providers = None
        self.initialized = self._init_providers()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_providers(self) -> bool:
        """Locate the addon and import its provider list.

        .. note::
            ``sys.path`` is **not** restored after import.  Providers
            perform runtime imports inside their ``sources()`` methods,
            so the library path must remain on ``sys.path`` for the
            lifetime of the client.
        """
        addon_path = self._resolve_addon_path()
        if not addon_path:
            kodilog(f"ExternalScraper ({self.module_id}): addon not found")
            return False

        lib_path = os.path.join(addon_path, "lib")
        if not os.path.isdir(lib_path):
            kodilog(
                f"ExternalScraper ({self.module_id}): lib dir not found at {lib_path}"
            )
            return False

        if lib_path not in sys.path:
            sys.path.insert(0, lib_path)

        try:
            # Import the top-level package
            module = __import__(self.module_name, fromlist=["sources"])
            self._sources_func = module.sources
            self._providers = self._sources_func(specified_folders=["torrents"])
            provider_count = len(self._providers) if self._providers else 0
            kodilog(
                f"ExternalScraper ({self.module_id}): loaded {provider_count} providers"
            )
            return bool(self._providers)
        except Exception as exc:
            kodilog(
                f"ExternalScraper ({self.module_id}): failed to import providers: {exc}"
            )
            return False

    def _resolve_addon_path(self) -> Optional[str]:
        """Locate the addon path via xbmcaddon or JSON-RPC."""
        # 1) xbmcaddon (fastest)
        try:
            import xbmcaddon  # noqa: WPS433

            addon = xbmcaddon.Addon(self.module_id)
            return addon.getAddonInfo("path")
        except Exception:
            pass

        # 2) JSON-RPC fallback
        try:
            import xbmc  # noqa: WPS433

            response = xbmc.executeJSONRPC(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": "Addons.GetAddonDetails",
                        "params": {
                            "addonid": self.module_id,
                            "properties": ["path"],
                        },
                        "id": 1,
                    }
                )
            )
            data = json.loads(response)
            return data.get("result", {}).get("addon", {}).get("path")
        except Exception as exc:
            kodilog(
                f"ExternalScraper ({self.module_id}): JSON-RPC fallback failed: {exc}"
            )
            return None

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        tmdb_id: str,
        query: str,
        mode: str,
        media_type: str,
        season: Optional[int],
        episode: Optional[int],
        imdb_id: str = "",
        tvdb_id: str = "",
        year: str = "",
        aliases: Optional[List[str]] = None,
    ) -> List[TorrentStream]:
        kodilog(
            f"[ExternalScraper ({self.module_id})] search() called: "
            f"query={query}, mode={mode}, imdb={imdb_id}, year={year}, aliases={aliases}, "
            f"providers={len(self._providers) if self._providers else 0}"
        )
        if not self.initialized or not self._providers:
            kodilog(
                f"[ExternalScraper ({self.module_id})] not initialised, returning empty"
            )
            return []

        is_tv = mode == "tv" or media_type == "tv"

        data = self._build_data(
            query=query,
            mode=mode,
            season=season,
            episode=episode,
            imdb_id=imdb_id,
            tvdb_id=tvdb_id,
            year=year,
            aliases=aliases,
        )

        all_results: List[TorrentStream] = []

        for provider_name, source_class in self._providers:
            # Filter providers by media-type capability
            if is_tv:
                if hasattr(source_class, "hasEpisodes") and not source_class.hasEpisodes:
                    continue
            else:
                if hasattr(source_class, "hasMovies") and not source_class.hasMovies:
                    continue

            try:
                provider_instance = source_class()

                # Single episode / movie results
                results = provider_instance.sources(data, {})
                if results:
                    mapped = self._map_results(results, provider_name)
                    all_results.extend(mapped)

                # Pack results for TV
                if is_tv and hasattr(source_class, "pack_capable") and source_class.pack_capable:
                    try:
                        pack_results = provider_instance.sources_packs(data, {})
                        if pack_results:
                            mapped_packs = self._map_results(
                                pack_results, provider_name, is_pack=True
                            )
                            all_results.extend(mapped_packs)
                    except Exception as exc:
                        kodilog(
                            f"ExternalScraper ({self.module_id}): "
                            f"provider '{provider_name}' packs error: {exc}"
                        )
            except Exception as exc:
                kodilog(
                    f"ExternalScraper ({self.module_id}): "
                    f"provider '{provider_name}' error: {exc}"
                )

        kodilog(
            f"[ExternalScraper ({self.module_id})] returning {len(all_results)} results"
        )
        return all_results

    # ------------------------------------------------------------------
    # Data mapping helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_data(
        query: str,
        mode: str,
        season: Optional[int],
        episode: Optional[int],
        imdb_id: str = "",
        tvdb_id: str = "",
        year: str = "",
        aliases: Optional[List[str]] = None,
    ) -> dict:
        """Build the data dict that external providers expect.

        Matches the convention:

        * Movies: ``{imdb, title, aliases, year}``
        * TV: ``{imdb, tvdb, tvshowtitle, title, aliases, year, season, episode}``
        """
        is_tv = mode in ("tv", "episode")

        data: dict = {
            "aliases": aliases or [],
            "year": str(year) if year else "",
        }

        if imdb_id:
            data["imdb"] = imdb_id

        if is_tv:
            data["tvshowtitle"] = query
            data["title"] = ""
            data["season"] = str(season) if season else ""
            data["episode"] = str(episode) if episode else ""
            if tvdb_id:
                data["tvdb"] = tvdb_id
        else:
            data["title"] = query

        return data

    def _map_results(
        self,
        results: list,
        provider_name: str,
        is_pack: bool = False,
    ) -> List[TorrentStream]:
        """Map external provider result dicts to Jacktook TorrentStream."""
        mapped: List[TorrentStream] = []

        for item in results:
            try:
                info_hash = (item.get("hash") or "").lower()
                url = item.get("url", "") or ""

                # Some legacy providers put the hash in url as "magnet:HASH"
                # without the ?xt=urn:btih: prefix and leave hash empty.
                if url.startswith("magnet:") and not url.startswith("magnet:?"):
                    legacy_hash = url[7:].strip()
                    if legacy_hash:
                        info_hash = legacy_hash.lower()
                        url = f"magnet:?xt=urn:btih:{info_hash}"

                if info_hash and not url.startswith("magnet:?"):
                    url = f"magnet:?xt=urn:btih:{info_hash}"

                raw_size = item.get("size", 0)
                try:
                    size_bytes = int(float(raw_size) * _BYTES_PER_GB) if raw_size else 0
                except (ValueError, TypeError):
                    size_bytes = 0

                package = item.get("package")
                result_is_pack = is_pack or package in ("season", "show")

                try:
                    seeders = int(item.get("seeders", 0) or 0)
                except (ValueError, TypeError):
                    seeders = 0

                quality = item.get("quality", "") or "N/A"
                title = item.get("name", "") or ""

                mapped.append(
                    TorrentStream(
                        title=title,
                        type="torrent",
                        indexer=Indexer.EXTERNAL_SCRAPER,
                        subindexer=provider_name,
                        addonInstanceLabel=self.module_display_name,
                        infoHash=info_hash,
                        url=url,
                        size=size_bytes,
                        seeders=seeders,
                        quality=quality,
                        provider=provider_name,
                        isPack=result_is_pack,
                        publishDate="",
                    )
                )
            except Exception as exc:
                kodilog(f"ExternalScraper: failed to map result: {exc}")
                continue

        return mapped

    # ------------------------------------------------------------------
    # BaseClient contract
    # ------------------------------------------------------------------

    def parse_response(self, res) -> List[TorrentStream]:
        """Not used — ExternalScraperClient does not make HTTP requests."""
        return []
