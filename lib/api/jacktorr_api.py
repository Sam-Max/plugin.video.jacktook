from json import dumps
import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import quote


class TorrServer(object):
    def __init__(self, host, port, username, password, ssl_enabled=False, session=None):
        self._base_url = "{}://{}:{}".format(
            "https" if ssl_enabled else "http", host, port
        )
        self._username = username
        self._password = password
        self._auth = HTTPBasicAuth(self._username, self._password)
        self._session = session or requests

    @property
    def torr_version(self):
        """tests server status"""
        return self._get("/echo").content

    def add_magnet(self, magnet, title="", poster="", data=""):
        return self._post(
            "/torrents",
            data=dumps(
                {
                    "action": "add",
                    "link": magnet,
                    "title": title,
                    "poster": poster,
                    "data": data,
                    "save_to_db": True,
                }
            ),
        ).json()["hash"]

    def add_torrent(self, path, title="", poster="", data=""):
        with open(path, "rb") as file:
            return self._post(
                "/torrent/upload",
                files={"file": file},
                data={
                    "save": "true",
                    "title": title,
                    "poster": poster,
                    "data": data,
                },
            ).json()["hash"]

    def add_torrent_obj(self, obj, title="", poster="", data=""):
        return self._post(
            "/torrent/upload",
            files={"file": obj},
            data={
                "save": "true",
                "title": title,
                "poster": poster,
                "data": data,
            },
        ).json()["hash"]

    def torrents(self):
        """read info about all torrents (doesn't fill file_stats info)"""
        return self._post("/torrents", data=dumps({"action": "list"})).json()

    def get_torrent_info_by_hash(self, hash):
        """not extended info"""
        return self._post(
            "/torrents", data=dumps({"action": "get", "hash": hash})
        ).json()

    def get_torrent_info(self, link):
        """read extended info of one torrent"""
        return self._get("/stream", params={"link": link, "stat": "true"}).json()

    def get_torrent_file_info(self, link, file_index=1):
        """read extended info of file of torrent"""
        return self._get(
            "/stream", params={"link": link, "index": file_index, "stat": "true"}
        ).json()

    def drop_torrent(self, hash):
        return self._post("/torrents", data=dumps({"action": "drop", "hash": hash}))

    def remove_torrent(self, info_hash, save_to_db=True):
        """delete torrent from TorrServer"""
        return self._post(
            "/torrents",
            data=dumps({"action": "rem", "hash": info_hash, "save_to_db": save_to_db}),
        )

    def play_torrent(self, hash, id):
        """Play given torrent referenced by hash"""
        """ application/octet-stream """
        return self._get("/play", params={"hash": hash, "id": id})

    def play_stream(self, link, title="", poster=""):
        """Play given torrent referenced by link"""
        """ application/octet-stream """
        return self._get(
            "/stream",
            params={"link": link, "title": title, "poster": poster, "play": "true"},
        )

    def preload_torrent(self, link, file_id=1, title=""):
        """preload torrent"""
        return self._get(
            "/stream",
            params={
                "link": link,
                "index": file_id,
                "title": title,
                "stat": "true",
                "preload": "true",
            },
        )

    def get_stream_url(self, link, path, file_id):
        """returns the stream url"""
        return f"{self._base_url}/stream/{quote(path)}?link={link}&index={file_id}&play"

    def get_settings(self):
        res = self._post("/settings", data=dumps({"action": "get"}))
        return res.json()

    def _post(self, url, **kwargs):
        return self._request("post", url, **kwargs)

    def _put(self, url, **kwargs):
        return self._request("put", url, **kwargs)

    def _get(self, url, **kwargs):
        return self._request("get", url, **kwargs)

    def _delete(self, url, **kwargs):
        return self._request("delete", url, **kwargs)

    def _request(self, method, url, **kwargs):
        try:
            return self._session.request(
                method, self._base_url + url, auth=self._auth, **kwargs
            )
        except Exception as e:
            raise TorrServerError(str(e))


class TorrServerError(Exception):
    pass

