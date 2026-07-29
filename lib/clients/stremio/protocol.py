"""Shared Stremio protocol, cache, and network safety helpers."""

import hashlib
import ipaddress
import json
import socket
from typing import Any, Callable, Mapping, Optional
from urllib.parse import quote, urljoin, urlsplit


MAX_RESOURCE_JSON_BYTES = 1024 * 1024
MIN_CACHE_TTL_SECONDS = 60
MAX_CACHE_TTL_SECONDS = 24 * 60 * 60
MAX_REDIRECTS = 5


def is_safe_http_url(url: Any, resolve_dns: bool = True) -> bool:
    """Return whether *url* is a public HTTP(S) destination."""
    try:
        parts = urlsplit(str(url or ""))
        if (
            parts.scheme.lower() not in {"http", "https"}
            or not parts.hostname
            or parts.username
            or parts.password
        ):
            return False
        try:
            addresses = [str(ipaddress.ip_address(parts.hostname))]
        except ValueError:
            if not resolve_dns:
                return True
            addresses = [entry[4][0] for entry in socket.getaddrinfo(parts.hostname, None)]
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                return False
        return True
    except (OSError, ValueError):
        return False


def request_with_safe_redirects(
    request: Callable[..., Any], url: str, validator: Callable[[str], bool], **kwargs: Any
) -> Any:
    """Request a URL while validating every redirect before following it."""
    target = url
    for _ in range(MAX_REDIRECTS + 1):
        if not validator(target):
            raise ValueError("unsafe request destination")
        response = request(target, allow_redirects=False, **kwargs)
        if response.status_code not in {301, 302, 303, 307, 308}:
            return response
        location = (getattr(response, "headers", {}) or {}).get("Location")
        if not location:
            return response
        target = urljoin(target, location)
    raise ValueError("too many redirects")


def response_json(response: Any, max_bytes: int = MAX_RESOURCE_JSON_BYTES) -> Any:
    """Decode a bounded JSON response."""
    content_length = (getattr(response, "headers", {}) or {}).get("Content-Length")
    if content_length and int(content_length) > max_bytes:
        raise ValueError("JSON response too large")
    content = getattr(response, "content", None)
    if isinstance(content, (bytes, bytearray)):
        if len(content) > max_bytes:
            raise ValueError("JSON response too large")
        return json.loads(content.decode("utf-8"))
    return response.json()


def cache_ttl_seconds(value: Any, default: int) -> int:
    """Clamp a Stremio cacheMaxAge value to the supported cache lifetime."""
    try:
        ttl = int(default if value is None else value)
    except (TypeError, ValueError):
        ttl = int(default)
    if ttl <= 0:
        return 0
    return min(MAX_CACHE_TTL_SECONDS, max(MIN_CACHE_TTL_SECONDS, ttl))


def safe_cache_key(prefix: str, identity: Any) -> str:
    """Build a deterministic cache key without exposing identity values."""
    payload = json.dumps(identity, sort_keys=True, default=str, separators=(",", ":"))
    return "{}:{}".format(prefix, hashlib.sha256(payload.encode("utf-8")).hexdigest())


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
