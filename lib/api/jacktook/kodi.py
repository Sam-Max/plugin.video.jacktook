import json
import logging
from .utils import assure_str
import xbmc
import xbmcaddon

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_NAME = ADDON.getAddonInfo("name")


def log(message, level=xbmc.LOGINFO):
    xbmc.log("[JACKTOOKAPI] " + str(message), level)


def get_installed_addons(addon_type="", content="unknown", enabled="all"):
    data = execute_json_rpc(
        "Addons.GetAddons", type=addon_type, content=content, enabled=enabled
    )
    addons = data["result"].get("addons")
    return [(a["addonid"], a["type"]) for a in addons] if addons else []


def execute_json_rpc(method, rpc_version="2.0", rpc_id=1, **params):
    """
    Execute a JSON-RPC call.
    :param method: The JSON-RPC method, as specified in https://kodi.wiki/view/JSON-RPC_API.
    """
    return json.loads(
        xbmc.executeJSONRPC(
            json.dumps(
                dict(jsonrpc=rpc_version, method=method, params=params, id=rpc_id)
            )
        )
    )


def run_script(script_id, *args):
    """
    Runs the python script. You must specify the add-on id of the script.
    As of 2007/02/24, all extra parameters are passed to the script as arguments and
    can be accessed by python using sys.argv.
    """
    xbmc.executebuiltin("RunScript({})".format(",".join((script_id,) + args)))


def notify_all(sender, message, data=None):
    """
    Notify all other connected clients.
    :return: The call outcome.
    :rtype: bool
    """
    # We could use NotifyAll(sender, data [, json]) builtin as well.
    params = {"sender": sender, "message": message}
    if data is not None:
        params["data"] = data
    return execute_json_rpc("JSONRPC.NotifyAll", **params).get("result") == "OK"


def set_logger(name=None, level=logging.NOTSET):
    logger = logging.getLogger(name)
    logger.handlers = [KodiLogHandler()]
    logger.setLevel(level)
    return logger


class KodiLogHandler(logging.StreamHandler):
    levels = {
        logging.CRITICAL: xbmc.LOGFATAL,
        logging.ERROR: xbmc.LOGERROR,
        logging.WARNING: xbmc.LOGWARNING,
        logging.INFO: xbmc.LOGINFO,
        logging.DEBUG: xbmc.LOGDEBUG,
        logging.NOTSET: xbmc.LOGNONE,
    }

    def __init__(self):
        super(KodiLogHandler, self).__init__()
        self.setFormatter(logging.Formatter("[{}] %(message)s".format(ADDON_ID)))

    def emit(self, record):
        xbmc.log(assure_str(self.format(record)), self.levels[record.levelno])

    def flush(self):
        pass
