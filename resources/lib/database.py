#!/usr/bin/env python3
import os
import pickle
from resources.lib.kodi import ID, log
import xbmcvfs


# Source with some modifications
# https://github.com/pikdum/plugin.video.haru/blob/master/resources/lib/database.py
class Database:
    def __init__(self):
        BASE_DATABASE = {
            "jt:watch": {},
            "jt:history": {},
            "jt:fanarttv": {},
            "jt:tmdb": {},
        }

        data_dir = xbmcvfs.translatePath(
            os.path.join("special://profile/addon_data/", ID)
        )
        database_path = os.path.join(data_dir, "database.pickle")
        xbmcvfs.mkdirs(data_dir)

        if os.path.exists(database_path):
            with open(database_path, "rb") as f:
                database = pickle.load(f)
        else:
            database = {}

        database = {**BASE_DATABASE, **database}

        self.database = database
        self.database_path = database_path
        self.addon_xml_path = xbmcvfs.translatePath(
            os.path.join("special://home/addons/", ID, "addon.xml")
        )

    def get_fanarttv(self, dict, id):
        if id in self.database[dict]:
            return self.database[dict][id]
        return None

    def set_fanarttv(self, dict, id, poster, fanart, clear):
        self.database[dict][id] = {
            "poster2": poster,
            "fanart2": fanart,
            "clearlogo2": clear,
        }
        self.commit()
    
    def get_tmdb(self, dict, identifier):
        if identifier in self.database[dict]:
            return self.database[dict][identifier]
        return None

    def set_tmdb(self, dict, identifier, tmdb_data):
        self.database[dict][identifier] = tmdb_data
        self.commit()

    def commit(self):
        with open(self.database_path, "wb") as f:
            pickle.dump(self.database, f)
