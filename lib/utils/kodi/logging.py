import re

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
