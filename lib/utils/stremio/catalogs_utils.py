from datetime import timedelta
from time import perf_counter
from lib.clients.stremio.addon_client import StremioAddonCatalogsClient
from lib.db.cached import cache
from lib.utils.kodi.utils import kodilog
from lib.utils.kodi.settings import get_cache_expiration, is_cache_enabled


def catalogs_get_cache(path, params, *args, **kwargs):
    identifier = f"{path}{params}{args}"
    start = perf_counter()
    data = cache.get(identifier)
    if data:
        elapsed_ms = (perf_counter() - start) * 1000
        kodilog(
            f"Stremio cache hit: path={path} addon={params.get('addon_url', '')} catalog={params.get('catalog_type', '')}/{params.get('catalog_id', '')} elapsed_ms={elapsed_ms:.1f}"
        )
        return data

    kodilog(
        f"Stremio cache miss: path={path} addon={params.get('addon_url', '')} catalog={params.get('catalog_type', '')}/{params.get('catalog_id', '')}"
    )

    handlers = {
        "search_catalog": lambda query: StremioAddonCatalogsClient(
            params
        ).search_catalog(query),
        "list_catalog": lambda **kwargs: StremioAddonCatalogsClient(
            params
        ).get_catalog_info(**kwargs),
        "list_stremio_seasons": lambda: StremioAddonCatalogsClient(
            params
        ).get_meta_info(),
        "list_stremio_episodes": lambda: StremioAddonCatalogsClient(
            params
        ).get_meta_info(),
        "list_stremio_tv": lambda: StremioAddonCatalogsClient(params).get_stream_info(),
        "list_stremio_movie": lambda: StremioAddonCatalogsClient(
            params
        ).get_stream_info(),
    }

    try:
        fetch_start = perf_counter()
        handler = handlers.get(path, lambda: None)
        if args or kwargs:
            data = handler(*args, **kwargs)
        else:
            data = handler()
        fetch_elapsed_ms = (perf_counter() - fetch_start) * 1000
        kodilog(
            f"Stremio fetch complete: path={path} addon={params.get('addon_url', '')} elapsed_ms={fetch_elapsed_ms:.1f} has_data={data is not None}"
        )
    except Exception as e:
        kodilog(f"Error: {e}")
        return {}

    if data is not None:
        store_start = perf_counter()
        cache.set(
            identifier,
            data,
            timedelta(hours=get_cache_expiration() if is_cache_enabled() else 0),
        )
        store_elapsed_ms = (perf_counter() - store_start) * 1000
        total_elapsed_ms = (perf_counter() - start) * 1000
        kodilog(
            f"Stremio cache store: path={path} store_ms={store_elapsed_ms:.1f} total_ms={total_elapsed_ms:.1f}"
        )

    return data
