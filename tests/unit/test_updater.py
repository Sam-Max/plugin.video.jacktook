import inspect
from pathlib import Path

from lib import navigation, router, updater
from lib.utils.kodi import settings


def _configure_update_check(
    monkeypatch, action, confirmed=True, current_version="1.0.0", online_version="1.1.0"
):
    builtins = []
    notifications = []

    monkeypatch.setattr(updater, "get_versions", lambda: (current_version, online_version))
    monkeypatch.setattr(settings, "get_update_action", lambda: action)
    monkeypatch.setattr(updater, "dialogyesno", lambda **kwargs: confirmed)
    monkeypatch.setattr(
        updater,
        "execute_builtin",
        lambda command, block=False: builtins.append((command, block)),
    )
    monkeypatch.setattr(
        updater,
        "notification",
        lambda **kwargs: notifications.append(kwargs),
    )
    monkeypatch.setattr(updater, "kodilog", lambda *args, **kwargs: None)
    translations = {
        90580: "%s %s",
        90581: "",
        90582: "Update available: %s",
        90964: "Installed version is newer than the repository version.",
    }
    monkeypatch.setattr(
        updater,
        "translation",
        lambda string_id: translations.get(string_id, f"string-{string_id}"),
    )

    return builtins, notifications


def test_manual_update_refreshes_repositories_before_install(monkeypatch):
    builtins, _ = _configure_update_check(monkeypatch, updater.UPDATE_ACTION_NONE)

    updater.updates_check_addon()

    assert builtins == [
        ("UpdateAddonRepos", True),
        ("InstallAddon(plugin.video.jacktook)", False),
    ]


def test_automatic_ask_installs_only_after_confirmation(monkeypatch):
    builtins, _ = _configure_update_check(monkeypatch, updater.UPDATE_ACTION_ASK)

    updater.updates_check_addon(automatic=True)

    assert builtins == [
        ("UpdateAddonRepos", True),
        ("InstallAddon(plugin.video.jacktook)", False),
    ]


def test_automatic_ask_does_not_install_when_declined(monkeypatch):
    builtins, _ = _configure_update_check(monkeypatch, updater.UPDATE_ACTION_ASK, confirmed=False)

    updater.updates_check_addon(automatic=True)

    assert builtins == []


def test_automatic_notify_announces_update_without_installing(monkeypatch):
    builtins, notifications = _configure_update_check(monkeypatch, updater.UPDATE_ACTION_NOTIFY)

    updater.updates_check_addon(automatic=True)

    assert builtins == []
    assert notifications == [{"heading": updater.HEADING, "message": "Update available: 1.1.0"}]


def test_automatic_none_does_nothing(monkeypatch):
    builtins, notifications = _configure_update_check(monkeypatch, updater.UPDATE_ACTION_NONE)

    updater.updates_check_addon(automatic=True)

    assert builtins == []
    assert notifications == []


def test_manual_check_notifies_when_installed_version_is_newer(monkeypatch):
    builtins, notifications = _configure_update_check(
        monkeypatch,
        updater.UPDATE_ACTION_NONE,
        current_version="1.1.0",
        online_version="1.0.0",
    )

    updater.updates_check_addon()

    assert notifications == [
        {
            "heading": updater.HEADING,
            "message": "Installed version is newer than the repository version.",
        }
    ]
    assert builtins == []


def test_automatic_check_is_silent_when_installed_version_is_newer(monkeypatch):
    builtins, notifications = _configure_update_check(
        monkeypatch,
        updater.UPDATE_ACTION_NONE,
        current_version="1.1.0",
        online_version="1.0.0",
    )

    updater.updates_check_addon(automatic=True)

    assert notifications == []
    assert builtins == []


def test_updater_has_no_custom_install_or_downgrade_mechanism():
    source = inspect.getsource(updater)

    for name in (
        "_safe_remove_path",
        "_validate_downloaded_zip",
        "_validate_installed_version",
        "downgrade_addon_menu",
        "unzip",
        "update_kodi_addons_db",
        "update_local_addons",
        "disable_enable_addon",
    ):
        assert name not in source


def test_downgrade_route_and_setting_are_removed():
    settings_xml = Path(__file__).parents[2] / "resources" / "settings.xml"

    assert "downgrade_addon" not in inspect.getsource(navigation)
    assert "downgrade_addon" not in inspect.getsource(router)
    assert "downgrade_addon" not in settings_xml.read_text(encoding="utf-8")
