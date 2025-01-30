import json
from typing import List, Optional


class Resource:
    def __init__(
        self, name: str, types: List[str], id_prefixes: Optional[List[str]] = None
    ):
        self.name = name
        self.types = types
        self.id_prefixes = id_prefixes or []


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
        contact_email: Optional[str] = None,
        logo: Optional[str] = None,
        background: Optional[str] = None,
    ):
        self.id = id
        self.version = version
        self.name = name
        self.description = description
        self.catalogs = catalogs
        self.resources = resources
        self.types = types
        self.behavior_hints = behavior_hints
        self.contact_email = contact_email
        self.logo = logo
        self.background = background

    def isConfigurationRequired(self):
        return self.behavior_hints.get("configurationRequired", False)

    def isConfigurable(self):
        return self.behavior_hints.get("configurable", False)


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
                        types=resource.get("types", []),
                        id_prefixes=resource.get("idPrefixes", []),
                    )
                )
                for resource in item["manifest"]["resources"]
            ]
            manifest = Manifest(
                id=item["manifest"]["id"],
                version=item["manifest"]["version"],
                name=item["manifest"]["name"],
                description=item["manifest"]["description"],
                catalogs=item["manifest"]["catalogs"],
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

    def get_addons_with_resource_and_id_prefix(
        self, resource_name: str, id_prefix: str
    ) -> List[Addon]:
        result = []
        for addon in self.addons:
            if addon.manifest.isConfigurationRequired():
                continue
            if addon.manifest.id == "org.stremio.local":
                continue
            for resource in addon.manifest.resources:
                if isinstance(resource, str):
                    if resource == resource_name and id_prefix in addon.manifest.types:
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
