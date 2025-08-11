import os
import threading
from sqlite3 import dbapi2 as db
from lib.utils.kodi.utils import notification

import xbmcaddon
from xbmcvfs import translatePath


try:
    OTAKU_ADDON = xbmcaddon.Addon("script.otaku.mappings")
    TRANSLATEPATH = translatePath
    mappingPath = TRANSLATEPATH(OTAKU_ADDON.getAddonInfo("path"))
    mappingDB = os.path.join(mappingPath, "resources", "data", "anime_mappings.db")
except:
    OTAKU_ADDON = None

mappingDB_lock = threading.Lock()


def get_all_ids(anilist_id):
    if OTAKU_ADDON is None:
        notification("Otaku (script.otaku.mappings) not found")
        return
    mappingDB_lock.acquire()
    conn = db.connect(mappingDB, timeout=60.0)
    conn.row_factory = _dict_factory
    conn.execute("PRAGMA FOREIGN_KEYS = 1")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM anime WHERE anilist_id IN ({0})".format(anilist_id))
    mapping = cursor.fetchone()
    cursor.close()
    try_release_lock(mappingDB_lock)
    all_ids = {}
    if mapping:
        if mapping["thetvdb_id"] is not None:
            all_ids.update({"tvdb": str(mapping["thetvdb_id"])})
        if mapping["themoviedb_id"] is not None:
            all_ids.update({"tmdb": str(mapping["themoviedb_id"])})
        if mapping["anidb_id"] is not None:
            all_ids.update({"anidb": str(mapping["anidb_id"])})
        if mapping["imdb_id"] is not None:
            all_ids.update({"imdb": str(mapping["imdb_id"])})
        if mapping["trakt_id"] is not None:
            all_ids.update({"trakt": str(mapping["trakt_id"])})
    return all_ids


def try_release_lock(lock):
    if lock.locked():
        lock.release()


def _dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d
