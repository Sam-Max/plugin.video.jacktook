import sqlite3

from lib.utils.torrent import display_metadata


INFO_HASH = "a" * 40


def _use_real_sqlite(monkeypatch):
    monkeypatch.setattr(display_metadata.sqlite3, "connect", sqlite3.dbapi2.connect)


def test_display_metadata_isolated_by_normalized_torrserver_namespace(tmp_path, monkeypatch):
    _use_real_sqlite(monkeypatch)
    database = str(tmp_path / "torrent-display.sqlite")

    assert display_metadata.save_display_metadata(
        "HTTP://Example.COM:8090", INFO_HASH.upper(), "Title", "Plot", "Poster", database
    )
    assert display_metadata.get_display_metadata(
        "http://example.com:8090", INFO_HASH, database
    ) == {"title": "Title", "plot": "Plot", "poster": "Poster"}
    assert display_metadata.get_display_metadata("https://example.com:8090", INFO_HASH, database) == {}
    assert not display_metadata.save_display_metadata(
        "http://example.com:8090", "invalid", "Title", database_path=database
    )
    assert not display_metadata.save_display_metadata(
        "http://example.com:8090", INFO_HASH, database_path=database
    )


def test_display_metadata_expiry_and_corrupt_database_are_safe_noops(tmp_path, monkeypatch):
    _use_real_sqlite(monkeypatch)
    database = str(tmp_path / "torrent-display.sqlite")
    base_url = "http://example.com:8090"

    assert display_metadata.save_display_metadata(base_url, INFO_HASH, "Title", database_path=database)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE torrent_display SET expires_at = 0")
    assert display_metadata.get_display_metadata(base_url, INFO_HASH, database) == {}

    corrupt_database = tmp_path / "corrupt.sqlite"
    corrupt_database.write_bytes(b"not a sqlite database")
    assert not display_metadata.save_display_metadata(
        base_url, INFO_HASH, "Title", database_path=str(corrupt_database)
    )
    assert display_metadata.get_display_metadata(base_url, INFO_HASH, str(corrupt_database)) == {}
