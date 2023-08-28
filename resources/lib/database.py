#!/usr/bin/env python3
import os
import pickle

import xbmcaddon
import xbmcvfs


class Database:
    def __init__(self):
        BASE_DATABASE = {
            "sp:watch": {},
            "sp:history": {},
            "sp:art_cache": {},
            "nt:watch": {},
            "nt:history": {},
        }

        addon = xbmcaddon.Addon()
        data_dir = xbmcvfs.translatePath(
            os.path.join("special://profile/addon_data/", addon.getAddonInfo("id"))
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
            os.path.join(
                "special://home/addons/", addon.getAddonInfo("id"), "addon.xml"
            )
        )

    def commit(self):
        with open(self.database_path, "wb") as f:
            pickle.dump(self.database, f)
