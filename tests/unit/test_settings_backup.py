from lib.utils.kodi import settings_backup


class FakeCache:
    def __init__(self, initial=None):
        self.store = dict(initial or {})

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, expires=None):
        self.store[key] = value

    def clear_list(self, key):
        self.store[key] = None


def _write_settings_xml(tmp_path, body):
    settings_path = tmp_path / "settings.xml"
    settings_path.write_text(
        "<?xml version='1.0' encoding='utf-8'?>\n"
        "<settings version='1'>\n"
        "  <section id='plugin.video.jacktook'>\n"
        f"{body}\n"
        "  </section>\n"
        "</settings>\n",
        encoding="utf-8",
    )
    return str(settings_path)


def test_build_backup_payload_skips_action_settings_and_scrubs_sensitive_data(
    monkeypatch, tmp_path
):
    settings_path = _write_settings_xml(
        tmp_path,
        """
    <category id='general'>
      <group id='backup'>
        <setting id='safe_value' type='string'><default /></setting>
        <setting id='jackett_apikey' type='string'><default /></setting>
        <setting id='stremio_email' type='string'><default /></setting>
        <setting id='is_trakt_auth' type='boolean'><default>false</default></setting>
        <setting id='some_action' type='action' />
      </group>
    </category>
    """,
    )
    values = {
        "safe_value": "safe",
        "jackett_apikey": "secret",
        "stremio_email": "user@example.com",
        "is_trakt_auth": "true",
    }

    monkeypatch.setattr(
        settings_backup.ADDON,
        "getSetting",
        lambda setting_id: values.get(setting_id, ""),
    )
    monkeypatch.setattr(settings_backup, "cache", FakeCache())
    monkeypatch.setattr(
        settings_backup,
        "get_cached_setting_property",
        lambda setting_id: {
            "trakt_token": "tok",
            "trakt_refresh": "ref",
            "trakt_expires": "123",
        }.get(setting_id, ""),
    )

    payload = settings_backup.build_backup_payload(
        strip_sensitive=True,
        settings_xml_path=settings_path,
    )

    assert payload["settings"] == {"safe_value": "safe"}
    assert payload["dynamic_settings"] == {}
    assert payload["cache"] == {}
    assert payload["strip_sensitive"] is True
    assert payload["custom_stremio_addons_included"] is False


def test_build_backup_payload_includes_custom_stremio_addons(monkeypatch, tmp_path):
    settings_path = _write_settings_xml(
        tmp_path,
        """
    <category id='general'>
      <group id='backup'>
        <setting id='safe_value' type='string'><default /></setting>
      </group>
    </category>
    """,
    )
    custom_addon = {
        "manifest": {"id": "custom.one", "name": "Custom One"},
        "transportName": "custom",
        "transportUrl": "https://example.com/manifest.json",
    }
    another_addon = {
        "manifest": {"id": "builtin.one", "name": "Builtin"},
        "transportName": "stremio-account",
        "transportUrl": "https://account.example/manifest.json",
    }
    custom_key = "custom.one|https://example.com"
    fake_cache = FakeCache(
        {
            settings_backup.STREMIO_USER_ADDONS: [custom_addon, another_addon],
            settings_backup.STREMIO_ADDONS_KEY: settings_backup.encode_selected_ids(
                [custom_key, "builtin.one|https://account.example"]
            ),
            settings_backup.STREMIO_ADDONS_CATALOGS_KEY: settings_backup.encode_selected_ids(
                [custom_key]
            ),
            settings_backup.STREMIO_TV_ADDONS_KEY: settings_backup.encode_selected_ids(
                ["builtin.one|https://account.example"]
            ),
        }
    )

    monkeypatch.setattr(settings_backup, "cache", fake_cache)
    monkeypatch.setattr(settings_backup.ADDON, "getSetting", lambda setting_id: "value")
    monkeypatch.setattr(
        settings_backup,
        "get_cached_setting_property",
        lambda setting_id: {
            "trakt_token": "tok",
            "trakt_refresh": "ref",
            "trakt_expires": "123",
        }.get(setting_id, ""),
    )

    payload = settings_backup.build_backup_payload(
        strip_sensitive=False,
        settings_xml_path=settings_path,
    )

    assert payload["settings"] == {"safe_value": "value"}
    assert payload["dynamic_settings"] == {
        "trakt_token": "tok",
        "trakt_refresh": "ref",
        "trakt_expires": "123",
    }
    assert payload["cache"]["custom_stremio_addons"] == [custom_addon]
    assert payload["cache"]["custom_stremio_selections"] == {
        "stream": [custom_key],
        "catalog": [custom_key],
        "tv": [],
    }


def test_apply_backup_payload_replaces_custom_stremio_addons(monkeypatch, tmp_path):
    settings_path = _write_settings_xml(
        tmp_path,
        """
    <category id='general'>
      <group id='backup'>
        <setting id='safe_value' type='string'><default /></setting>
      </group>
    </category>
    """,
    )
    old_custom = {
        "manifest": {"id": "custom.old", "name": "Old Custom"},
        "transportName": "custom",
        "transportUrl": "https://old.example/manifest.json",
    }
    new_custom = {
        "manifest": {"id": "custom.new", "name": "New Custom"},
        "transportName": "custom",
        "transportUrl": "https://new.example/manifest.json",
    }
    account_addon = {
        "manifest": {"id": "account.one", "name": "Account"},
        "transportName": "stremio-account",
        "transportUrl": "https://account.example/manifest.json",
    }
    old_key = "custom.old|https://old.example"
    new_key = "custom.new|https://new.example"
    account_key = "account.one|https://account.example"
    fake_cache = FakeCache(
        {
            settings_backup.STREMIO_USER_ADDONS: [old_custom, account_addon],
            settings_backup.STREMIO_ADDONS_KEY: settings_backup.encode_selected_ids(
                [old_key, account_key]
            ),
            settings_backup.STREMIO_ADDONS_CATALOGS_KEY: settings_backup.encode_selected_ids(
                [old_key]
            ),
            settings_backup.STREMIO_TV_ADDONS_KEY: settings_backup.encode_selected_ids([]),
        }
    )
    set_calls = []
    property_calls = []

    monkeypatch.setattr(settings_backup, "cache", fake_cache)
    monkeypatch.setattr(
        settings_backup,
        "set_setting",
        lambda setting_id, value: set_calls.append((setting_id, value)),
    )
    monkeypatch.setattr(
        settings_backup,
        "set_cached_setting_property",
        lambda setting_id, value: property_calls.append((setting_id, value)),
    )

    payload = {
        "settings": {"safe_value": "restored", "unknown": "ignored"},
        "dynamic_settings": {
            "trakt_token": "tok",
            "trakt_refresh": "ref",
            "trakt_expires": "123",
        },
        "cache": {
            "custom_stremio_addons": [new_custom],
            "custom_stremio_selections": {
                "stream": [new_key],
                "catalog": [new_key],
                "tv": ["invalid"],
            },
        },
        "strip_sensitive": False,
    }

    settings_backup.apply_backup_payload(payload, settings_xml_path=settings_path)

    assert ("safe_value", "restored") in set_calls
    assert ("trakt_token", "tok") in property_calls
    assert ("trakt_refresh", "ref") in property_calls
    assert ("trakt_expires", "123") in property_calls
    assert fake_cache.store[settings_backup.STREMIO_USER_ADDONS] == [account_addon, new_custom]
    assert settings_backup.decode_selected_ids(
        fake_cache.store[settings_backup.STREMIO_ADDONS_KEY]
    ) == [account_key, new_key]
    assert settings_backup.decode_selected_ids(
        fake_cache.store[settings_backup.STREMIO_ADDONS_CATALOGS_KEY]
    ) == [new_key]
    assert settings_backup.decode_selected_ids(
        fake_cache.store[settings_backup.STREMIO_TV_ADDONS_KEY]
    ) == []


def test_apply_backup_payload_clears_scrubbed_fields_and_custom_addons(
    monkeypatch, tmp_path
):
    settings_path = _write_settings_xml(
        tmp_path,
        """
    <category id='general'>
      <group id='backup'>
        <setting id='safe_value' type='string'><default /></setting>
        <setting id='jackett_apikey' type='string'><default /></setting>
        <setting id='stremio_email' type='string'><default /></setting>
        <setting id='is_trakt_auth' type='boolean'><default>false</default></setting>
        <setting id='trakt_user' type='string'><default /></setting>
      </group>
    </category>
    """,
    )
    old_custom = {
        "manifest": {"id": "custom.old", "name": "Old Custom"},
        "transportName": "custom",
        "transportUrl": "https://old.example/manifest.json",
    }
    account_addon = {
        "manifest": {"id": "account.one", "name": "Account"},
        "transportName": "stremio-account",
        "transportUrl": "https://account.example/manifest.json",
    }
    old_key = "custom.old|https://old.example"
    account_key = "account.one|https://account.example"
    fake_cache = FakeCache(
        {
            settings_backup.STREMIO_USER_ADDONS: [old_custom, account_addon],
            settings_backup.STREMIO_ADDONS_KEY: settings_backup.encode_selected_ids(
                [old_key, account_key]
            ),
            settings_backup.STREMIO_ADDONS_CATALOGS_KEY: settings_backup.encode_selected_ids(
                [old_key]
            ),
            settings_backup.STREMIO_TV_ADDONS_KEY: settings_backup.encode_selected_ids([]),
        }
    )
    set_calls = []
    property_calls = []

    monkeypatch.setattr(settings_backup, "cache", fake_cache)
    monkeypatch.setattr(
        settings_backup,
        "set_setting",
        lambda setting_id, value: set_calls.append((setting_id, value)),
    )
    monkeypatch.setattr(
        settings_backup,
        "set_cached_setting_property",
        lambda setting_id, value: property_calls.append((setting_id, value)),
    )

    settings_backup.apply_backup_payload(
        {
            "settings": {"safe_value": "restored"},
            "dynamic_settings": {"trakt_token": "tok"},
            "cache": {},
            "strip_sensitive": True,
        },
        settings_xml_path=settings_path,
    )

    assert ("safe_value", "restored") in set_calls
    assert ("jackett_apikey", "") in set_calls
    assert ("stremio_email", "") in set_calls
    assert ("is_trakt_auth", "false") in set_calls
    assert ("trakt_user", "unknown_user") in set_calls
    assert ("trakt_token", "") in property_calls
    assert ("trakt_refresh", "") in property_calls
    assert ("trakt_expires", "") in property_calls
    assert fake_cache.store[settings_backup.STREMIO_USER_ADDONS] == [account_addon]
    assert settings_backup.decode_selected_ids(
        fake_cache.store[settings_backup.STREMIO_ADDONS_KEY]
    ) == [account_key]
    assert settings_backup.decode_selected_ids(
        fake_cache.store[settings_backup.STREMIO_ADDONS_CATALOGS_KEY]
    ) == []


def test_reset_all_settings_restores_defaults_and_clears_custom_addons(
    monkeypatch, tmp_path
):
    settings_path = _write_settings_xml(
        tmp_path,
        """
    <category id='general'>
      <group id='backup'>
        <setting id='safe_value' type='string'><default>default-safe</default></setting>
        <setting id='is_trakt_auth' type='boolean'><default>false</default></setting>
        <setting id='trakt_user' type='string'><default /></setting>
      </group>
    </category>
    """,
    )
    old_custom = {
        "manifest": {"id": "custom.old", "name": "Old Custom"},
        "transportName": "custom",
        "transportUrl": "https://old.example/manifest.json",
    }
    account_addon = {
        "manifest": {"id": "account.one", "name": "Account"},
        "transportName": "stremio-account",
        "transportUrl": "https://account.example/manifest.json",
    }
    old_key = "custom.old|https://old.example"
    account_key = "account.one|https://account.example"
    fake_cache = FakeCache(
        {
            settings_backup.STREMIO_USER_ADDONS: [old_custom, account_addon],
            settings_backup.STREMIO_ADDONS_KEY: settings_backup.encode_selected_ids(
                [old_key, account_key]
            ),
            settings_backup.STREMIO_ADDONS_CATALOGS_KEY: settings_backup.encode_selected_ids(
                [old_key]
            ),
            settings_backup.STREMIO_TV_ADDONS_KEY: settings_backup.encode_selected_ids([]),
        }
    )
    set_calls = []
    property_calls = []

    monkeypatch.setattr(settings_backup, "cache", fake_cache)
    monkeypatch.setattr(
        settings_backup,
        "set_setting",
        lambda setting_id, value: set_calls.append((setting_id, value)),
    )
    monkeypatch.setattr(
        settings_backup,
        "set_cached_setting_property",
        lambda setting_id, value: property_calls.append((setting_id, value)),
    )

    settings_backup.reset_all_settings(settings_xml_path=settings_path)

    assert ("safe_value", "default-safe") in set_calls
    assert ("is_trakt_auth", "false") in set_calls
    assert ("trakt_user", "unknown_user") in set_calls
    assert ("trakt_token", "") in property_calls
    assert ("trakt_refresh", "") in property_calls
    assert ("trakt_expires", "") in property_calls
    assert fake_cache.store[settings_backup.STREMIO_USER_ADDONS] == [account_addon]
    assert settings_backup.decode_selected_ids(
        fake_cache.store[settings_backup.STREMIO_ADDONS_KEY]
    ) == [account_key]
    assert settings_backup.decode_selected_ids(
        fake_cache.store[settings_backup.STREMIO_ADDONS_CATALOGS_KEY]
    ) == []


def test_factory_reset_clears_settings_caches_and_local_database(monkeypatch, tmp_path):
    settings_path = _write_settings_xml(
        tmp_path,
        """
    <category id='general'>
      <group id='backup'>
        <setting id='safe_value' type='string'><default>default-safe</default></setting>
      </group>
    </category>
    """,
    )
    fake_cache = FakeCache()
    set_calls = []
    helper_calls = []
    property_calls = []

    class FakePickleDatabase:
        def __init__(self):
            self.calls = []

        def set_key(self, key, value, commit=True):
            self.calls.append((key, value, commit))

        def commit(self):
            self.calls.append(("commit", None, None))

    fake_pickle_db = FakePickleDatabase()

    monkeypatch.setattr(settings_backup, "cache", fake_cache)
    monkeypatch.setattr(
        settings_backup,
        "set_setting",
        lambda setting_id, value: set_calls.append((setting_id, value)),
    )
    monkeypatch.setattr(
        settings_backup,
        "set_cached_setting_property",
        lambda setting_id, value: property_calls.append((setting_id, value)),
    )
    monkeypatch.setattr(settings_backup, "clear_all_cache", lambda: helper_calls.append("all"))
    monkeypatch.setattr(settings_backup, "clear_trakt_db_cache", lambda: helper_calls.append("trakt"))
    monkeypatch.setattr(settings_backup, "clear_tmdb_cache", lambda: helper_calls.append("tmdb"))
    monkeypatch.setattr(settings_backup, "clear_stremio_cache", lambda: helper_calls.append("stremio"))
    monkeypatch.setattr(settings_backup, "clear_debrid_cache", lambda: helper_calls.append("debrid"))
    monkeypatch.setattr(settings_backup, "clear_mdblist_cache", lambda: helper_calls.append("mdblist"))
    monkeypatch.setattr(settings_backup, "PickleDatabase", lambda: fake_pickle_db)

    settings_backup.factory_reset(settings_xml_path=settings_path)

    assert ("safe_value", "default-safe") in set_calls
    assert ("trakt_token", "") in property_calls
    assert ("trakt_refresh", "") in property_calls
    assert ("trakt_expires", "") in property_calls
    assert helper_calls == ["all", "trakt", "tmdb", "stremio", "debrid", "mdblist"]
    assert fake_cache.store["multi"] is None
    assert fake_cache.store["direct"] is None
    assert ("jt:watch", {}, False) in fake_pickle_db.calls
    assert ("jt:lth", {}, False) in fake_pickle_db.calls
    assert ("jt:lfh", {}, False) in fake_pickle_db.calls
    assert ("jt:lib", {}, False) in fake_pickle_db.calls
    assert ("search_query", "", False) in fake_pickle_db.calls
    assert ("search_catalog_query", "", False) in fake_pickle_db.calls
    assert ("anime_query", "", False) in fake_pickle_db.calls
    assert ("collection_search_query", "", False) in fake_pickle_db.calls
    assert ("commit", None, None) in fake_pickle_db.calls


def test_export_settings_backup_returns_silently_when_dialog_is_cancelled(monkeypatch):
    notifications = []
    build_calls = []

    monkeypatch.setattr(settings_backup, "_get_export_path", lambda: None)
    monkeypatch.setattr(
        settings_backup,
        "notification",
        lambda message: notifications.append(message),
    )
    monkeypatch.setattr(
        settings_backup,
        "build_backup_payload",
        lambda *args, **kwargs: build_calls.append(True),
    )

    settings_backup.export_settings_backup()

    assert notifications == []
    assert build_calls == []
