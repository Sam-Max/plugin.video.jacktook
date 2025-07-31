import os
import pickle
import xbmcvfs

from lib.jacktook.utils import kodilog
from lib.utils.kodi.utils import ADDON_ID


class PickleDatabase:
    def __init__(self):
        BASE_DATABASE = {
            "jt:watch": {},
            "jt:lth": {},
            "jt:lfh": {},
        }

        data_dir = xbmcvfs.translatePath(
            os.path.join("special://profile/addon_data/", ADDON_ID)
        )
        self._database_path = os.path.join(data_dir, "database.pickle")
        xbmcvfs.mkdirs(data_dir)

        try:
            if os.path.exists(self._database_path):
                with open(self._database_path, "rb") as f:
                    database = pickle.load(f)
            else:
                database = {}
        except Exception as e:
            kodilog(f"Failed to load database: {e}")
            database = {}

        self._database = {**BASE_DATABASE, **database}
        self.addon_xml_path = xbmcvfs.translatePath(
            os.path.join("special://home/addons/", ADDON_ID, "addon.xml")
        )

    def set_item(self, key: str, subkey: str, value, commit: bool = True):
        self._database[key][subkey] = value
        if commit:
            self.commit()

    def get_item(self, key: str, subkey: str):
        return self._database[key].get(subkey, None)

    def delete_item(self, key: str, subkey: str, commit: bool = True):
        try:
            if subkey in self._database[key]:
                del self._database[key][subkey]
                if commit:
                    self.commit()
        except KeyError:
            pass

    def set_key(self, key: str, value, commit: bool = True):
        self._database[key] = value
        if commit:
            self.commit()

    def get_key(self, key: str):
        return self._database[key]

    def commit(self):
        try:
            with open(self._database_path, "wb") as f:
                pickle.dump(self._database, f)
        except Exception as e:
            kodilog(f"Failed to save database: {e}")

    @property
    def database(self):
        """Expose internal database dict as read-only property."""
        return self._database


