"""Neutral bridge between the Stremio and Nuvio catalog worlds.

This is the ONLY module allowed to import both
``lib.clients.stremio.catalog_menus`` and ``lib.clients.nuvio.helpers``.
``catalog_menus`` stays Stremio-pure and accepts injected extras/resolvers;
this hub supplies the Nuvio side so navigation and the router keep the
current merged behaviour without the client file knowing about Nuvio.
"""

from lib.clients.nuvio.helpers import (
    get_nuvio_addon_by_base_url,
    get_nuvio_addon_by_key,
)
from lib.clients.nuvio.helpers import (
    get_selected_catalogs_addons as get_nuvio_catalogs_addons,
)
from lib.clients.nuvio.helpers import get_selected_tv_addons as get_nuvio_tv_addons
from lib.clients.stremio import catalog_menus
from lib.utils.kodi.utils import kodilog


def get_extra_catalog_addons(menu_type=""):
    """Return Nuvio-owned addons for a menu, exception-safe (``[]`` on failure)."""
    try:
        if menu_type == "tv":
            return get_nuvio_tv_addons()
        return get_nuvio_catalogs_addons()
    except Exception as exc:
        kodilog(f"catalog_hub: extra catalog addons unavailable: {type(exc).__name__}")
        return []


def catalog_addon_resolver(kind, value):
    """Resolve an addon Nuvio-first-fallback style: Stremio is tried in the client.

    This resolver is meant to be passed as ``addon_resolver``/``resolver`` into
    ``catalog_menus`` helpers, which always try Stremio first and only call the
    resolver on a miss. Exception-safe: returns ``None`` on failure.
    """
    try:
        if kind == "key":
            return get_nuvio_addon_by_key(value)
        if kind == "url":
            return get_nuvio_addon_by_base_url(value)
    except Exception as exc:
        kodilog(f"catalog_hub: addon resolution failed: {type(exc).__name__}")
    return None


def resolve_catalog_addon(addon_key="", addon_url=""):
    """Resolve one addon, Stremio-first with Nuvio fallback, exception-safe."""
    try:
        from lib.clients.stremio.helpers import get_addon_by_base_url, get_addon_by_key

        if addon_key:
            try:
                addon = get_addon_by_key(addon_key)
            except Exception:
                addon = None
            if addon is None:
                addon = catalog_addon_resolver("key", addon_key)
            return addon
        if addon_url:
            try:
                addon = get_addon_by_base_url(addon_url)
            except Exception:
                addon = None
            if addon is None:
                addon = catalog_addon_resolver("url", addon_url)
            return addon
    except Exception as exc:
        kodilog(f"catalog_hub: resolve_catalog_addon failed: {type(exc).__name__}")
    return None


def list_merged_catalogs(menu_type="", sub_menu_type=""):
    """List Stremio catalogs merged with Nuvio extras (navigation entry point)."""
    return catalog_menus.list_stremio_catalogs(
        menu_type,
        sub_menu_type,
        extra_addons=get_extra_catalog_addons(menu_type),
    )


def list_catalog(params):
    """Router entry point for ``list_catalog`` with Nuvio resolution."""
    return catalog_menus.list_catalog(params, addon_resolver=catalog_addon_resolver)


def search_catalog(params):
    """Router entry point for ``search_catalog`` with Nuvio resolution."""
    return catalog_menus.search_catalog(params, addon_resolver=catalog_addon_resolver)


def list_catalog_genres(params):
    """Router entry point for ``list_catalog_genres`` with Nuvio extras/resolution."""
    return catalog_menus.list_catalog_genres(
        params,
        addon_resolver=catalog_addon_resolver,
        extra_addons=get_extra_catalog_addons(params.get("menu_type", "")),
    )
