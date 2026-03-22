from typing import Any, Dict, Optional

from lib.api.debrid.base import ProviderException
from lib.utils.kodi.utils import translation
from lib.utils.general.utils import supported_video_extensions


PACKED_RELEASE_FALLBACK_TEMPLATE = (
    "{provider} cannot directly play packed releases (.rar/.zip). "
    "Choose a source with video files instead."
)


def get_packed_release_message(provider_name: str) -> str:
    template = translation(30918)
    if not isinstance(template, str) or not template:
        template = PACKED_RELEASE_FALLBACK_TEMPLATE
    return template.format(provider=provider_name)


def get_file_name(file_data: Optional[Dict[str, Any]]) -> str:
    if not file_data:
        return ""

    return str(
        file_data.get("path")
        or file_data.get("filename")
        or file_data.get("short_name")
        or file_data.get("name")
        or file_data.get("n")
        or ""
    )


def is_direct_playable_file(filename: Optional[str]) -> bool:
    if not filename:
        return False

    lowered = filename.lower()
    return any(lowered.endswith(ext) for ext in supported_video_extensions())


def ensure_direct_playable_file(filename: Optional[str]) -> None:
    if not filename:
        return

    if is_direct_playable_file(filename):
        return

    raise ProviderException(get_packed_release_message("This provider"))


def ensure_direct_playable_file_for_provider(
    filename: Optional[str], provider_name: str
) -> None:
    if not filename:
        return

    if is_direct_playable_file(filename):
        return

    raise ProviderException(get_packed_release_message(provider_name))
