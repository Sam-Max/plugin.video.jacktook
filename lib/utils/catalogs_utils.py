from datetime import timedelta
from lib.api.jacktook.kodi import kodilog
from lib.clients.stremio_addon import StremioAddonCatalogsClient
from lib.db.cached import cache
from lib.utils.settings import get_cache_expiration, is_cache_enabled


def catalogs_get_cache(path, params, *args, **kwargs):
    identifier = f"{path}{params}{args}"
    data = cache.get(identifier, hashed_key=True)
    if data:
        return data
    
    handlers = {
        "search_catalog": lambda p:  StremioAddonCatalogsClient(params).search_catalog(p),
        "list_stremio_catalog": lambda p:  StremioAddonCatalogsClient(params).get_catalog_info(p),
        "list_stremio_seasons": lambda:  StremioAddonCatalogsClient(params).get_meta_info(),
        "list_stremio_episodes": lambda:  StremioAddonCatalogsClient(params).get_meta_info(),
        "list_stremio_tv": lambda:  StremioAddonCatalogsClient(params).get_stream_info(),
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
        cache.set(
            identifier,
            data,
            timedelta(hours=get_cache_expiration() if is_cache_enabled() else 0),
            hashed_key=True,
        )

    return data