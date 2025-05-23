import os
import pickle
from lib.utils.kodi.utils import ADDON_ID
import xbmcvfs


class MainDatabase:
    def __init__(self):
        BASE_DATABASE = {
            "jt:watch": {},
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

    def set_data(self, key, subkey, value):
        if subkey in self.database[key]:
            del self.database[key][subkey]
        self.database[key][subkey]= value
        self.commit()

    def set_query(self, key, value):
        self.database[key]= value
        self.commit()

    def get_query(self, key):
        return self.database[key]

    def commit(self):
        with open(self.database_path, "wb") as f:
            pickle.dump(self.database, f)


main_db = MainDatabase()
