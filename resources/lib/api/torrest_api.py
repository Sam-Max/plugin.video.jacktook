from collections import namedtuple
import requests


STATUS_QUEUED = 0
STATUS_CHECKING = 1
STATUS_FINDING = 2
STATUS_DOWNLOADING = 3
STATUS_FINISHED = 4
STATUS_SEEDING = 5
STATUS_ALLOCATING = 6
STATUS_CHECKING_RESUME_DATA = 7
STATUS_PAUSED = 8
STATUS_BUFFERING = 9

TorrentStatus = namedtuple("TorrentStatus", [
    "active_time",  # type:int
    "all_time_download",  # type:int
    "all_time_upload",  # type:int
    "download_rate",  # type:int
    "finished_time",  # type:int
    "has_metadata",  # type:bool
    "paused",  # type:bool
    "peers",  # type:int
    "peers_total",  # type:int
    "progress",  # type:float
    "seeders",  # type:int
    "seeders_total",  # type:int
    "seeding_time",  # type:int
    "state",  # type:int
    "total",  # type:int
    "total_done",  # type:int
    "total_wanted",  # type:int
    "total_wanted_done",  # type:int
    "upload_rate",  # type:int
])

TorrentInfo = namedtuple("TorrentInfo", [
    "info_hash",  # type:str
    "name",  # type:str
    "size",  # type:int
])

Torrent = namedtuple("Torrent", list(TorrentInfo._fields) + [
    "status",  # type:TorrentStatus
])

FileStatus = namedtuple("FileStatus", [
    "total",  # type:int
    "total_done",  # type:int
    "buffering_total",  # type:int
    "buffering_progress",  # type:float
    "priority",  # type:int
    "progress",  # type:float
    "state",  # type:int
])

FileInfo = namedtuple("FileInfo", [
    "id",  # type:int
    "length",  # type:int
    "name",  # type:str
    "path",  # type:str
])

File = namedtuple("File", list(FileInfo._fields) + [
    "status",  # type:FileStatus
])


def from_dict(data, clazz, **converters):
    if data is None:
        return None
    # data = dict(data)
    for k, converter in converters.items():
        data[k] = converter(data.get(k))
    return clazz(**data)


class TorrestError(Exception):
    pass


class Torrest(object):
    def __init__(self, host, port, credentials, ssl_enabled=False, session=None):
        self.host = host
        self.port = port
        self.username, self.password = credentials
        self.ssl_enabled = ssl_enabled
        self._base_url = "{}://{}:{}".format("https" if self.ssl_enabled else "http", self.host, self.port)
        self._session = session or requests

    def add_magnet(self, magnet, ignore_duplicate=False, download=False):
        r = self._post("/add/magnet", params={
            "uri": magnet, "ignore_duplicate": self._bool_str(ignore_duplicate),
            "download": self._bool_str(download)})
        return r.json()["info_hash"]

    def add_torrent(self, path, ignore_duplicate=False, download=False):
        with open(path, "rb") as f:
            return self.add_torrent_obj(f, ignore_duplicate=ignore_duplicate, download=download)

    def add_torrent_obj(self, obj, ignore_duplicate=False, download=False):
        r = self._post("/add/torrent", files={"torrent": obj}, params={
            "ignore_duplicate": self._bool_str(ignore_duplicate),
            "download": self._bool_str(download)})
        return r.json()["info_hash"]

    def torrents(self, status=True):
        """
        :type status: bool
        :rtype: typing.List[Torrent]
        """
        return [from_dict(t, Torrent, status=lambda v: from_dict(v, TorrentStatus))
                for t in self._get("/torrents", params={"status": self._bool_str(status)}).json()]

    def pause_torrent(self, info_hash):
        self._put("/torrents/{}/pause".format(info_hash))

    def resume_torrent(self, info_hash):
        self._put("/torrents/{}/resume".format(info_hash))

    def download_torrent(self, info_hash):
        self._put("/torrents/{}/download".format(info_hash))

    def stop_torrent(self, info_hash):
        self._put("/torrents/{}/stop".format(info_hash))

    def remove_torrent(self, info_hash, delete=True):
        self._delete("/torrents/{}".format(info_hash), params={"delete": self._bool_str(delete)})

    def torrent_info(self, info_hash):
        """
        :type info_hash: str
        :rtype: TorrentInfo
        """
        return from_dict(self._get("/torrents/{}/info".format(info_hash)).json(), TorrentInfo)

    def torrent_status(self, info_hash):
        """
        :type info_hash: str
        :rtype: TorrentStatus
        """
        return from_dict(self._get("/torrents/{}/status".format(info_hash)).json(), TorrentStatus)

    def files(self, info_hash, status=True):
        """
        :type info_hash: str
        :type status: bool
        :rtype: typing.List[File]
        """
        return [from_dict(f, File, status=lambda v: from_dict(v, FileStatus))
                for f in self._get("/torrents/{}/files".format(info_hash),
                                   params={"status": self._bool_str(status)}).json()]

    def file_info(self, info_hash, file_id):
        """
        :type info_hash: str
        :type file_id: int
        :rtype: FileInfo
        """
        return from_dict(self._get("/torrents/{}/files/{}/info".format(info_hash, file_id)).json(), FileInfo)

    def file_status(self, info_hash, file_id):
        """
        :type info_hash: str
        :type file_id: int
        :rtype: FileStatus
        """
        return from_dict(self._get("/torrents/{}/files/{}/status".format(info_hash, file_id)).json(), FileStatus)

    def download_file(self, info_hash, file_id, buffer=False):
        self._put("/torrents/{}/files/{}/download".format(info_hash, file_id),
                  params={"buffer": self._bool_str(buffer)})

    def stop_file(self, info_hash, file_id):
        self._put("/torrents/{}/files/{}/stop".format(info_hash, file_id))

    def serve_url(self, info_hash, file_id):
        base_url= "{}://{}:{}".format("https" if self.ssl_enabled else "http", f"{self.username}:{self.password}@{self.host}", self.port)
        return "{}/torrents/{}/files/{}/serve".format(base_url, info_hash, file_id)

    @staticmethod
    def _bool_str(value):
        return "true" if value else "false"

    def _post(self, url, **kwargs):
        return self._request("post", url, **kwargs)

    def _put(self, url, **kwargs):
        return self._request("put", url, **kwargs)

    def _get(self, url, **kwargs):
        return self._request("get", url, **kwargs)

    def _delete(self, url, **kwargs):
        return self._request("delete", url, **kwargs)

    def _request(self, method, url, validate=True, **kwargs):
        r = self._session.request(method, self._base_url + url, auth=(self.username, self.password),**kwargs)
        if validate and r.status_code >= 400:
            error = r.json()["error"]
            raise TorrestError(error)
        return r

