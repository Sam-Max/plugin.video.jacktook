import json
from typing import List, Optional, Any
from urllib.parse import urlsplit, urlunsplit


def normalize_transport_url(url: str) -> str:
    if not url:
        return ""

    normalized_url = str(url).strip()
    if normalized_url.startswith("stremio://"):
        normalized_url = normalized_url.replace("stremio://", "https://", 1)

    parts = urlsplit(normalized_url)
    path = parts.path.rstrip("/")
    if path.endswith("/manifest.json"):
        path = path[: -len("/manifest.json")]

    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, parts.query, "")
    )


def build_addon_base_url(transport_url: str) -> str:
    return normalize_transport_url(transport_url)


def build_addon_instance_key(addon_like: Any) -> str:
    manifest = {}
    addon_id = ""
    transport_url = ""

    if isinstance(addon_like, Addon):
        addon_id = addon_like.manifest.id or ""
        transport_url = addon_like.transport_url or ""
    elif isinstance(addon_like, dict):
        manifest = addon_like.get("manifest") or {}
        addon_id = (
            manifest.get("id")
            or addon_like.get("id")
            or addon_like.get("name")
            or ""
        )
        transport_url = addon_like.get("transportUrl") or addon_like.get("transport_url") or ""

    normalized_url = normalize_transport_url(transport_url)
    if addon_id and normalized_url:
        return f"{addon_id}|{normalized_url}"
    return addon_id or normalized_url


def build_addon_instance_label(addon_like: Any) -> str:
    if isinstance(addon_like, Addon):
        name = addon_like.manifest.name or addon_like.manifest.id or "Unknown Addon"
        transport_url = addon_like.transport_url
        transport_name = addon_like.transport_name
    else:
        manifest = addon_like.get("manifest") or {}
        name = (
            manifest.get("name")
            or manifest.get("id")
            or addon_like.get("name")
            or "Unknown Addon"
        )
        transport_url = addon_like.get("transportUrl") or addon_like.get("transport_url") or ""
        transport_name = addon_like.get("transportName") or addon_like.get("transport_name") or ""

    normalized_url = normalize_transport_url(transport_url)
    parts = urlsplit(normalized_url)
    host = parts.netloc or "local"

    if transport_name == "custom":
        origin = "custom"
    elif transport_name:
        origin = "account"
    else:
        origin = "addon"

    return f"{name} ({host}, {origin})"


class Catalog:
    def __init__(self, type: str, id: str, name: str, extra: List[dict] = None):
        self.type = type
        self.id = id
        self.name = name
        self.extra = extra or []
        self.genres = []
        for item in self.extra:
            if item.get("name") == "genre" and "options" in item:
                self.genres = item["options"]


class Resource:
    def __init__(
        self,
        name: str,
        types: List[str],
        id_prefixes: Optional[List[str]] = None,
        extra: Optional[List[dict]] = None,
    ):
        self.name = name
        self.types = types
        self.id_prefixes = id_prefixes or []
        self.extra = extra or []


class Config:
    def __init__(
        self,
        key: str,
        type: str,
        default: Optional[str] = None,
        title: Optional[str] = None,
        options: Optional[List[str]] = None,
        required: bool = False,
    ):
        self.key = key
        self.type = type
        self.default = default
        self.title = title
        self.options = options
        self.required = required


class Manifest:
    def __init__(
        self,
        id: str,
        version: str,
        name: str,
        description: str,
        catalogs: List[dict],
        resources: List[Resource],
        types: List[str],
        behavior_hints: dict,
        addon_catalogs: Optional[List[dict]] = None,
        config: Optional[List[dict]] = None,
        contact_email: Optional[str] = None,
        logo: Optional[str] = None,
        background: Optional[str] = None,
    ):
        self.id = id
        self.version = version
        self.name = name
        self.description = description
        self.catalogs = [
            Catalog(
                type=cat["type"],
                id=cat["id"],
                name=cat.get("name"),
                extra=cat.get("extra"),
            )
            for cat in catalogs
        ]
        self.addon_catalogs = [
            Catalog(
                type=cat["type"],
                id=cat["id"],
                name=cat.get("name"),
                extra=cat.get("extra"),
            )
            for cat in (addon_catalogs or [])
        ]
        self.config = [
            Config(
                key=c["key"],
                type=c["type"],
                default=c.get("default"),
                title=c.get("title"),
                options=c.get("options"),
                required=c.get("required", False),
            )
            for c in (config or [])
        ]
        self.resources = resources
        self.types = types
        self.behavior_hints = behavior_hints
        self.contact_email = contact_email
        self.logo = logo
        self.background = background

    def isConfigurationRequired(self):
        return self.behavior_hints.get("configurationRequired", False)

    def isConfigurable(self):
        return self.behavior_hints.get("configurable", False) or bool(self.config)

    def isAdult(self):
        return self.behavior_hints.get("adult", False)

    def isP2P(self):
        return self.behavior_hints.get("p2p", False)


class Addon:
    def __init__(self, transport_url: str, transport_name: str, manifest: Manifest):
        self.transport_url = transport_url
        self.transport_name = transport_name
        self.manifest = manifest

    def url(self):
        return build_addon_base_url(self.transport_url)

    def key(self):
        return build_addon_instance_key(self)

    def label(self):
        return build_addon_instance_label(self)

    def isSupported(self, resource_name: str, type: str, id_prefix: str) -> bool:
        norm_prefix = id_prefix.rstrip(":")
        for resource in self.manifest.resources:
            if resource.name == resource_name and type in resource.types:
                for rp in resource.id_prefixes:
                    if rp.rstrip(":") == norm_prefix:
                        return True
        return False


class AddonManager:
    def __init__(self, src):
        if isinstance(src, str):
            src = json.loads(src)

        self.addons = self._parse_addons(src)

    def _parse_addons(self, data: List[dict]) -> List[Addon]:
        addons = []
        for item in data:
            resources = [
                (
                    Resource(
                        name=resource,
                        types=item["manifest"].get("types", []),
                        id_prefixes=item["manifest"].get("idPrefixes", []),
                    )
                    if isinstance(resource, str)
                    else Resource(
                        name=(
                            resource["name"] if isinstance(resource, dict) else resource
                        ),
                        types=resource.get("types", item["manifest"].get("types", [])),
                        id_prefixes=resource.get(
                            "idPrefixes", item["manifest"].get("idPrefixes", [])
                        ),
                    )
                )
                for resource in item["manifest"].get("resources", [])
            ]

            manifest_data = item["manifest"]
            transport_url = item.get("transportUrl") or ""

            logo = manifest_data.get("logo")
            background = manifest_data.get("background")

            if transport_url:
                from urllib.parse import urljoin

                if logo and not logo.startswith(("http://", "https://")):
                    logo = urljoin(transport_url, logo)
                if background and not background.startswith(("http://", "https://")):
                    background = urljoin(transport_url, background)

            manifest = Manifest(
                id=manifest_data.get("id") or manifest_data.get("name") or "unknown",
                version=manifest_data.get("version", "0.0.1"),
                name=manifest_data.get("name", "Unknown Addon"),
                description=manifest_data.get("description", ""),
                catalogs=manifest_data.get("catalogs", []),
                addon_catalogs=manifest_data.get("addonCatalogs", []),
                config=manifest_data.get("config", []),
                resources=resources,
                types=manifest_data.get("types", []),
                behavior_hints=manifest_data.get("behaviorHints", {}),
                contact_email=manifest_data.get("contactEmail"),
                logo=logo,
                background=background,
            )

            addons.append(
                Addon(
                    transport_url=transport_url,
                    transport_name=item.get("transportName", ""),
                    manifest=manifest,
                )
            )
        return addons

    def get_addons_with_resource(
        self,
        resource_name: str,
    ) -> List[Addon]:
        result = []
        for addon in self.addons:
            if addon.manifest.id == "org.stremio.local":
                continue
            for resource in addon.manifest.resources:
                if isinstance(resource, str):
                    if resource == resource_name:
                        result.append(addon)
                        break

                if resource.name == resource_name:
                    result.append(addon)
                    break
        return result

    def get_addons_with_resource_and_id_prefix(
        self, resource_name: str, id_prefix: str
    ) -> List[Addon]:
        result = []
        for addon in self.addons:
            if addon.manifest.id == "org.stremio.local":
                continue
            for resource in addon.manifest.resources:
                if isinstance(resource, str):
                    if (
                        resource == resource_name
                        and id_prefix in addon.manifest.id_prefixes
                    ):
                        result.append(addon)
                        break

                if resource.name == resource_name and id_prefix in resource.id_prefixes:
                    result.append(addon)
                    break
        return result

    def get_addon_by_url(self, url: str) -> Optional[Addon]:
        for addon in self.addons:
            if addon.transport_url == url:
                return addon
        return None
