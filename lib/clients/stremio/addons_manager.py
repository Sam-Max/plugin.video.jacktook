import json
from typing import List, Optional, Any


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
        return "/".join(self.transport_url.split("/")[:-1])

    def key(self):
        return self.manifest.id

    def isSupported(self, resource_name: str, type: str, id_prefix: str) -> bool:
        for resource in self.manifest.resources:
            if (
                resource.name == resource_name
                and type in resource.types
                and id_prefix in resource.id_prefixes
            ):
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
                        types=resource.get(
                            "types", item["manifest"].get("types", [])
                        ),
                        id_prefixes=resource.get(
                            "idPrefixes", item["manifest"].get("idPrefixes", [])
                        ),
                    )
                )
                for resource in item["manifest"].get("resources", [])
            ]

            manifest = Manifest(
                id=item["manifest"]["id"],
                version=item["manifest"]["version"],
                name=item["manifest"]["name"],
                description=item["manifest"].get("description", ""),
                catalogs=item["manifest"].get("catalogs", []),
                addon_catalogs=item["manifest"].get("addonCatalogs", []),
                config=item["manifest"].get("config", []),
                resources=resources,
                types=item["manifest"]["types"],
                behavior_hints=item["manifest"].get("behaviorHints", {}),
                contact_email=item["manifest"].get("contactEmail"),
                logo=item["manifest"].get("logo"),
                background=item["manifest"].get("background"),
            )

            addons.append(
                Addon(
                    transport_url=item["transportUrl"],
                    transport_name=item["transportName"],
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
