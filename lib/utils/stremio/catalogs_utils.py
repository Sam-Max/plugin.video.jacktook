from datetime import timedelta

from lib.clients.stremio.addon_client import StremioAddonCatalogsClient
from lib.clients.stremio.protocol import cache_ttl_seconds, safe_cache_key
from lib.db.cached import cache
from lib.utils.kodi.settings import get_cache_expiration, is_cache_enabled
from lib.utils.kodi.utils import kodilog


def catalogs_get_cache(path, params, *args, **kwargs):
    identity = {
        "path": path,
        "addon": params.get("addon_key") or params.get("addon_url", ""),
        "catalog_type": params.get("catalog_type", ""),
        "catalog_id": params.get("catalog_id", ""),
        "meta_id": params.get("meta_id", ""),
        "args": args,
        "kwargs": kwargs,
    }
    identifier = safe_cache_key("stremio_resource", identity)
    data = cache.get(identifier)
    if data:
        return data

    handlers = {
        "search_catalog": lambda query: StremioAddonCatalogsClient(params).search_catalog(query),
        "list_catalog": lambda **kwargs: StremioAddonCatalogsClient(params).get_catalog_info(
            **kwargs
        ),
        "list_stremio_seasons": lambda: StremioAddonCatalogsClient(params).get_meta_info(),
        "list_stremio_episodes": lambda: StremioAddonCatalogsClient(params).get_meta_info(),
        "list_stremio_tv": lambda: StremioAddonCatalogsClient(params).get_stream_info(),
        "list_stremio_movie": lambda: StremioAddonCatalogsClient(params).get_stream_info(),
    }

    try:
        handler = handlers.get(path, lambda: None)
        if args or kwargs:
            data = handler(*args, **kwargs)
        else:
            data = handler()
    except Exception as e:
        kodilog(f"Error: {e}")
        return {}

    if data is not None:
        fallback_seconds = get_cache_expiration() * 60 * 60 if is_cache_enabled() else 0
        ttl = cache_ttl_seconds(
            data.get("cacheMaxAge") if isinstance(data, dict) else None,
            fallback_seconds,
        )
        if ttl > 0:
            cache.set(identifier, data, timedelta(seconds=ttl))

    return data
