import sqlite3
import xbmc
from xbmcvfs import translatePath
import xbmcaddon
import os


class BookmarkDb:
    def __init__(self):
        self.create_paths()
        self.create_bookmarks_table()

    def create_paths(self):
        userdata_path = translatePath(xbmcaddon.Addon().getAddonInfo("profile"))
        database_path_raw = translatePath(os.path.join(userdata_path, "databases"))
        if not os.path.exists(database_path_raw):
            os.makedirs(database_path_raw)
        self.db_path = translatePath(os.path.join(database_path_raw, ".bookmarks.db"))

    def create_bookmarks_table(self):
        try:
            conn = sqlite3.connect(
                self.db_path,
                isolation_level=None,
                check_same_thread=False,
            )
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS bookmarks (
                    url TEXT PRIMARY KEY,
                    bookmark REAL
                )
            """
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            xbmc.log(
                f"Error in BookmarkDb.create_bookmarks_table: {str(e)}",
                level=xbmc.LOGERROR,
            )

    def set_bookmark(self, url, time):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO bookmarks (url, bookmark) VALUES (?, ?)",
                (url, time),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            xbmc.log(f"Error in BookmarkDb.set_bookmark: {str(e)}", level=xbmc.LOGERROR)

    def get_bookmark(self, url):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT bookmark FROM bookmarks WHERE url=?", (url,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else 0.0
        except sqlite3.Error as e:
            xbmc.log(f"Error in BookmarkDb.get_bookmark: {str(e)}", level=xbmc.LOGERROR)
            return 0.0

    def clear_bookmarks(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM bookmarks")
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            xbmc.log(f"Error in BookmarkDb.clear_bookmarks: {str(e)}", level=xbmc.LOGERROR)

