from lib.utils.kodi import settings


def test_migrates_either_legacy_subtitle_setting_to_unified_automation(monkeypatch):
    values = {
        "subtitle_automation_migrated": False,
        "auto_subtitle_selection": False,
        "auto_subtitle_download": True,
    }
    writes = []

    monkeypatch.setattr(settings, "get_setting", lambda key, default=None: values.get(key, default))
    monkeypatch.setattr(
        settings,
        "set_setting",
        lambda key, value: writes.append((key, value)) or values.__setitem__(key, value),
    )

    assert settings.subtitle_automation_enabled() is True
    assert writes == [
        ("subtitle_automation", "true"),
        ("subtitle_automation_migrated", "true"),
    ]


def test_uses_only_unified_setting_after_migration(monkeypatch):
    values = {
        "subtitle_automation_migrated": True,
        "subtitle_automation": False,
        "auto_subtitle_selection": True,
        "auto_subtitle_download": True,
    }

    monkeypatch.setattr(settings, "get_setting", lambda key, default=None: values.get(key, default))
    monkeypatch.setattr(settings, "set_setting", lambda *_args: None)

    assert settings.subtitle_automation_enabled() is False


def test_migration_preserves_enabled_unified_setting_and_writes_strings(monkeypatch):
    values = {
        "subtitle_automation_migrated": False,
        "subtitle_automation": True,
        "auto_subtitle_selection": False,
        "auto_subtitle_download": False,
    }
    writes = []

    monkeypatch.setattr(settings, "get_setting", lambda key, default=None: values.get(key, default))
    monkeypatch.setattr(
        settings,
        "set_setting",
        lambda key, value: writes.append((key, value)) or values.__setitem__(key, value),
    )

    assert settings.subtitle_automation_enabled() is True
    assert writes == [
        ("subtitle_automation", "true"),
        ("subtitle_automation_migrated", "true"),
    ]
    assert all(isinstance(value, str) for _, value in writes)
