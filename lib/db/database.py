#!/usr/bin/env python3
import os
import pickle
from lib.utils.kodi import ADDON_ID
import xbmcvfs


# Source with some modifications
# https://github.com/pikdum/plugin.video.haru/blob/master/resources/lib/database.py
class Database:
    def __init__(self):
        BASE_DATABASE = {
            "jt:watch": {},
            "jt:fanarttv": {},
            "jt:tmdb": {},
            "jt:lth": {},
            "jt:lfh": {},
        }

        data_dir = xbmcvfs.translatePath(
            os.path.join("special://profile/addon_data/", ADDON_ID)
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
            os.path.join("special://home/addons/", ADDON_ID, "addon.xml")
        )

    def set_search_string(self, key, value):
        self.database[key] = value
        self.commit()

    def get_search_string(self, key):
        return self.database[key]

    def commit(self):
        with open(self.database_path, "wb") as f:
            pickle.dump(self.database, f)


def get_db():
    return Database()
