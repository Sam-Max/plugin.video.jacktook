import re
from urllib.parse import urlsplit

import xbmc


_ERROR_PREFIX_RE = re.compile(
    r"^(?:\[[^\]]+\]\s*)?(?:error|failed|traceback|exception|crash)\b",
    re.IGNORECASE,
)


def _resolve_log_level(message, level):
    if level is not None:
        return level
    if isinstance(message, BaseException):
        return xbmc.LOGERROR
    if _ERROR_PREFIX_RE.match(str(message)):
        return xbmc.LOGERROR
    return xbmc.LOGDEBUG


def kodilog(message, level=None):
    xbmc.log("[###JACKTOOKLOG###] " + str(message), _resolve_log_level(message, level))


def summarize_locator_for_log(value):
    text = str(value or "").strip()
    if not text:
        return ""

    magnet_match = re.search(r"btih:([A-Fa-f0-9]{8,40})", text)
    if text.startswith("magnet:?"):
        if magnet_match:
            return "magnet:{}".format(magnet_match.group(1).lower()[:12])
        return "magnet"

    if re.fullmatch(r"[A-Fa-f0-9]{40}", text):
        return "infohash:{}".format(text.lower()[:12])

    if text.startswith(("http://", "https://")):
        parts = urlsplit(text)
        path = parts.path or "/"
        return "{}://{}{}".format(parts.scheme, parts.netloc, path)

    return text[:80]
