import base64
import json
import sys
import threading
import time

from .utils import (
    ADDON_ID,
    bytes_to_str,
    get_installed_addons,
    kodilog,
    notify_all,
    run_script,
    str_to_bytes,
)
import xbmc


__all__ = ["ProviderResult", "Provider"]


def get_providers():
    return [
        p_id
        for p_id, _ in get_installed_addons(addon_type="xbmc.python.script")
        if p_id.startswith("script.jacktook.") and p_id != ADDON_ID
    ]


def send_to_providers(providers, method, *args, **kwargs):
    data = {}
    if args:
        data["args"] = args
    if kwargs:
        data["kwargs"] = kwargs
    data_b64 = bytes_to_str(base64.b64encode(str_to_bytes(json.dumps(data))))
    for provider in providers:
        run_script(provider, ADDON_ID, method, data_b64)


def _setter_and_getter(attribute):
    def setter(self, value):
        self[attribute] = value

    def getter(self):
        return self.get(attribute)

    setter.__doc__ = None
    getter.__doc__ = None
    return setter, property(getter)


class ProviderResult(dict):
    set_title, title = _setter_and_getter("title")
    set_indexer, indexer = _setter_and_getter("indexer")
    set_guid, guid = _setter_and_getter("guid")
    set_quality, quality = _setter_and_getter("quality")
    set_seeders, seeders = _setter_and_getter("seeders")
    set_peers, peers = _setter_and_getter("peers")
    set_size, size = _setter_and_getter("size")


class Provider(object):
    def __init__(self):
        self._methods = {}
        for name in dir(self):
            if not name.startswith("_") and name != "register":
                attr = getattr(self, name)
                if callable(attr):
                    self._methods[name] = attr

    def search(self, query):
        raise NotImplementedError("'search' method must be implemented")

    def search_movie(self, tmdb_id, title, titles, year=None):
        raise NotImplementedError("'search_movie' method must be implemented")

    def search_show(self, tmdb_id, show_title, titles, year=None):
        raise NotImplementedError("'search_show' method must be implemented")

    def search_season(self, tmdb_id, show_title, season_number, titles):
        raise NotImplementedError("'search_season' method must be implemented")

    def search_episode(
        self, tmdb_id, show_title, season_number, episode_number, titles
    ):
        raise NotImplementedError("'search_episode' method must be implemented")

    def resolve(self, provider_data):
        raise NotImplementedError("'resolve' method must be implemented")

    def ping(self):
        kodilog("Ping method called")
        return ADDON_ID

    def register(self):
        if len(sys.argv) != 4:
            kodilog("Expecting 4 arguments")
            kodilog("Providers can't be called")
            return

        _, sender, method, data_b64 = sys.argv
        if method in self._methods:
            try:
                data = json.loads(base64.b64decode(data_b64))
                value = self._methods[method](
                    *data.get("args", []), **data.get("kwargs", {})
                )
            except Exception as e:
                kodilog(f"Failed running method '{method}': {e}")
                value = None
            if not notify_all(ADDON_ID, f"{sender}.{method}", value):
                kodilog("Failed sending provider data")
        else:
            kodilog(
                f"Unknown method provided '{method}'. Expecting one of {list(self._methods.keys())}"
            )
            raise ValueError("Unknown method provided")


class ProviderListener(xbmc.Monitor):
    def __init__(self, providers, method, timeout=10):
        super(ProviderListener, self).__init__()
        self._waiting = {i: True for i in providers}
        self._method = "Other.{}.{}".format(ADDON_ID, method)
        self._timeout = timeout
        self._data = {}
        self._lock = threading.Lock()
        self._start_time = time.time()

    def onNotification(self, sender, method, data):
        kodilog(
            f"Received notification with sender={sender}, method={method}, data={data}",
            level=xbmc.LOGDEBUG,
        )
        with self._lock:
            if method == self._method and self._waiting.get(sender, False):
                try:
                    self._data[sender] = json.loads(data)
                except Exception as e:
                    kodilog(f"Unable to get data from sender '{sender}': {e}")
                else:
                    self._waiting[sender] = False
                    self.on_receive(sender)

    def on_receive(self, sender):
        pass

    def is_complete(self):
        with self._lock:
            return not any(self._waiting.values())

    def wait(self, **kwargs):
        if kwargs.get("reset"):
            self._start_time = time.time()
        timeout = kwargs.get("timeout", self._timeout)
        while not (
            self.is_complete()
            or 0 < timeout < time.time() - self._start_time
            or self.waitForAbort(0.2)
        ):
            pass

    def get_missing(self):
        with self._lock:
            return [k for k, v in self._waiting.items() if v]

    @property
    def data(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.wait()
        missing = self.get_missing()
        if missing:
            kodilog("Provider(s) timed out: %s", ", ".join(missing))
        return False
