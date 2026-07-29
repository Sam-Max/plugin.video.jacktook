"""Shared Stremio protocol, cache, and network safety helpers."""

from typing import Any, Mapping, Optional
from urllib.parse import quote


def build_resource_url(
    base_url: str,
    resource: str,
    resource_type: str,
    resource_id: Any,
    extras: Optional[Mapping[str, Any]] = None,
) -> str:
    """Build an official Stremio HTTP resource route."""
    components = [resource, resource_type, resource_id]
    path = "/".join(quote(str(component), safe="") for component in components)
    extra_pairs = []
    for key in sorted(extras or {}, key=lambda value: str(value)):
        value = extras[key]
        if value in (None, ""):
            continue
        extra_pairs.append("{}={}".format(quote(str(key), safe=""), quote(str(value), safe="")))
    if extra_pairs:
        path += "/" + "&".join(extra_pairs)
    return "{}/{}.json".format((base_url or "").rstrip("/"), path)
