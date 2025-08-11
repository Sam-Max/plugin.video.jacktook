import json
import xbmc
import xbmcaddon


ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo("path")
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_VERSION = ADDON.getAddonInfo("version")
ADDON_NAME = ADDON.getAddonInfo("name")


def kodilog(message, level=xbmc.LOGINFO):
    xbmc.log("[###JACKTOOKLOG###] " + str(message), level)


def get_installed_addons(addon_type="", content="unknown", enabled="all"):
    data = execute_json_rpc(
        "Addons.GetAddons", type=addon_type, content=content, enabled=enabled
    )
    addons = data["result"].get("addons")
    return [(a["addonid"], a["type"]) for a in addons] if addons else []


def notify_all(sender, message, data=None):
    params = {"sender": sender, "message": message}
    if data is not None:
        params["data"] = data
    return execute_json_rpc("JSONRPC.NotifyAll", **params).get("result") == "OK"


def run_script(script_id, *args):
    xbmc.executebuiltin("RunScript({})".format(",".join((script_id,) + args)))


def execute_json_rpc(method, rpc_version="2.0", rpc_id=1, **params):
    return json.loads(
        xbmc.executeJSONRPC(
            json.dumps(
                dict(jsonrpc=rpc_version, method=method, params=params, id=rpc_id)
            )
        )
    )



class ResolveTimeoutError(Exception):
    pass


class NoProvidersError(Exception):
    pass


def assure_str(s):
    return s


def str_to_bytes(s):
    return s.encode()


def bytes_to_str(b):
    return b.decode()
