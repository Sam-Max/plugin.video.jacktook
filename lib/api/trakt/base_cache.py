# -*- coding: utf-8 -*-
import os
import time
import sqlite3 as database
from lib.utils.kodi.utils import (
    delete_file,
    dialog_ok,
    get_property,
    notification,
    set_property,
    clear_property,
)

import xbmcaddon
from xbmcvfs import translatePath


userdata_path = translatePath(xbmcaddon.Addon().getAddonInfo("profile"))
databases_path = os.path.join(userdata_path, "databases/")
database_path_raw = os.path.join(userdata_path, "databases")
trakt_db = translatePath(os.path.join(database_path_raw, "traktcache.db"))
lists_db = translatePath(os.path.join(database_path_raw, "lists.db"))
maincache_db = translatePath(os.path.join(database_path_raw, "maincache.db"))
paginator_db = translatePath(os.path.join(database_path_raw, "paginator.db"))
database_timeout = 20


database_locations = {
    "trakt_db": trakt_db,
    "lists_db": lists_db,
    "maincache_db": maincache_db,
    "paginator_db": paginator_db,
}

integrity_check = {
    "trakt_db": ("trakt_data", "watched_status", "progress"),
    "maincache_db": ("maincache",),
    "lists_db": ("lists",),
}

table_creators = {
    "trakt_db": (
        "CREATE TABLE IF NOT EXISTS trakt_data (id text unique, data text)",
        "CREATE TABLE IF NOT EXISTS watched \
(db_type text not null, media_id text not null, season integer, episode integer, last_played text, title text, unique (db_type, media_id, season, episode))",
        "CREATE TABLE IF NOT EXISTS progress \
(db_type text not null, media_id text not null, season integer, episode integer, resume_point text, curr_time text, \
last_played text, resume_id integer, title text, unique (db_type, media_id, season, episode))",
        "CREATE TABLE IF NOT EXISTS watched_status (db_type text not null, media_id text not null, status text, unique (db_type, media_id))",
    ),
    "lists_db": (
        "CREATE TABLE IF NOT EXISTS lists (id text unique, data text, expires integer)",
    ),
    "maincache_db": (
        "CREATE TABLE IF NOT EXISTS maincache (id text unique, data text, expires integer)",
    ),
    "paginator_db": (
        "CREATE TABLE IF NOT EXISTS paginated_data (id text unique, page_number integer, data text, total_pages integer)",
    ),
}

media_prop = "jacktook.%s"
BASE_GET = "SELECT expires, data FROM %s WHERE id = ?"
BASE_SET = "INSERT OR REPLACE INTO %s(id, data, expires) VALUES (?, ?, ?)"
BASE_DELETE = "DELETE FROM %s WHERE id = ?"


def make_database(database_name):
    dbcon = database.connect(database_locations[database_name])
    for command in table_creators[database_name]:
        dbcon.execute(command)
    dbcon.close()


def setup_databases():
    if not os.path.exists(databases_path):
        os.makedirs(databases_path)
    for database_name, database_location in database_locations.items():
        dbcon = database.connect(database_location)
        for command in table_creators[database_name]:
            dbcon.execute(command)


def connect_database(database_name):
    dbcon = database.connect(
        database_locations[database_name],
        timeout=database_timeout,
        isolation_level=None,
        check_same_thread=False,
    )
    dbcon.execute("PRAGMA synchronous = OFF")
    dbcon.execute("PRAGMA journal_mode = OFF")
    return dbcon


def get_timestamp(offset=0):
    # Offset is in HOURS multiply by 3600 to get seconds
    return int(time.time()) + (offset * 3600)


def check_databases_integrity():
    def _process(database_name, tables):
        database_location = database_locations[database_name]
        try:
            dbcon = database.connect(database_location)
            for db_table in tables:
                dbcon.execute(command_base % db_table)
        except:
            database_errors.append(database_name)
            if os.path.exists(database_location):
                try:
                    dbcon.close()
                except:
                    pass
                delete_file(database_location)

    command_base = "SELECT * FROM %s LIMIT 1"
    database_errors = []
    for database_name, tables in integrity_check.items():
        _process(database_name, tables)
    setup_databases()
    if database_errors:
        dialog_ok(
            heading="Databases Rebuilt",
            line1="[B]Following Databases Rebuilt:[/B][CR][CR]%s"
            % ", ".join(database_errors),
        )
    else:
        notification("No Corrupt or Missing Databases", time=3000)


class BaseCache(object):
    def __init__(self, dbfile, table):
        self.table = table
        self.dbfile = dbfile

    def get(self, string):
        result = None
        try:
            current_time = get_timestamp()
            result = self.get_memory_cache(string, current_time)
            if result is None:
                dbcon = connect_database(self.dbfile)
                cache_data = dbcon.execute(BASE_GET % self.table, (string,)).fetchone()
                if cache_data:
                    if cache_data[0] > current_time:
                        result = eval(cache_data[1])
                        self.set_memory_cache(result, string, cache_data[0])
                    else:
                        self.delete(string)
        except:
            pass
        return result

    def set(self, string, data, expiration=720):
        try:
            dbcon = connect_database(self.dbfile)
            expires = get_timestamp(expiration)
            dbcon.execute(BASE_SET % self.table, (string, repr(data), int(expires)))
            self.set_memory_cache(data, string, int(expires))
        except:
            return None

    def get_memory_cache(self, string, current_time):
        result = None
        try:
            cachedata = get_property(media_prop % string)
            if cachedata:
                cachedata = eval(cachedata)
                if cachedata[0] > current_time:
                    result = cachedata[1]
        except:
            pass
        return result

    def set_memory_cache(self, data, string, expires):
        try:
            cachedata = (expires, data)
            cachedata_repr = repr(cachedata)
            set_property(media_prop % string, cachedata_repr)
        except:
            pass

    def delete(self, string):
        try:
            dbcon = connect_database(self.dbfile)
            dbcon.execute(BASE_DELETE % self.table, (string,))
            self.delete_memory_cache(string)
        except:
            pass

    def delete_memory_cache(self, string):
        clear_property(media_prop % string)

    def manual_connect(self, dbfile):
        return connect_database(dbfile)
