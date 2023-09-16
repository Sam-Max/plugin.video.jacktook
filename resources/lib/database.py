#!/usr/bin/env python3
import os
import pickle
from resources.lib.kodi import ID
import xbmcvfs


# Modified from:
# https://github.com/pikdum/plugin.video.haru/blob/master/resources/lib/database.py
class Database:
    def __init__(self):
        BASE_DATABASE = {"jt:watch": {}, "jt:history": {}, "jt:fanarttv": {}}

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

    def commit(self):
        with open(self.database_path, "wb") as f:
            pickle.dump(self.database, f)
