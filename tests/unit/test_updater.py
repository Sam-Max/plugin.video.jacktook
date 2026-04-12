import io
import os
import shutil
import zipfile

from lib import updater


def _write_addon_xml(path, version):
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "addon.xml"), "w", encoding="utf-8") as handle:
        handle.write(
            "<?xml version='1.0' encoding='utf-8'?>\n"
            f"<addon id='plugin.video.jacktook' name='Jacktook' version='{version}' provider-name='Sam-Max'>\n"
            "</addon>\n"
        )


def _build_release_zip_bytes(version):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "plugin.video.jacktook/addon.xml",
            "<?xml version='1.0' encoding='utf-8'?>\n"
            f"<addon id='plugin.video.jacktook' name='Jacktook' version='{version}' provider-name='Sam-Max'>\n"
            "</addon>\n",
        )
        archive.writestr("plugin.video.jacktook/resources/readme.txt", "ok")
    buffer.seek(0)
    return buffer.getvalue()


def _configure_updater_paths(monkeypatch, tmp_path):
    packages_dir = tmp_path / "packages"
    destination_dir = tmp_path / "addons" / updater.ADDON_ID
    packages_dir.mkdir(parents=True)
    destination_dir.parent.mkdir(parents=True)

    monkeypatch.setattr(updater, "PACKAGES_DIR", str(packages_dir))
    monkeypatch.setattr(updater, "HOME_ADDONS_DIR", str(destination_dir.parent))
    monkeypatch.setattr(updater, "DESTINATION_DIR", str(destination_dir))
    monkeypatch.setattr(
        updater,
        "delete_file",
        lambda path: os.path.exists(path) and os.remove(path),
    )
    monkeypatch.setattr(updater, "close_all_dialog", lambda: None)
    monkeypatch.setattr(updater, "execute_builtin", lambda *args, **kwargs: None)
    monkeypatch.setattr(updater, "notification", lambda *args, **kwargs: None)
    monkeypatch.setattr(updater, "show_busy_dialog", lambda: None)
    monkeypatch.setattr(updater, "close_busy_dialog", lambda: None)
    monkeypatch.setattr(updater, "dialogyesno", lambda *args, **kwargs: False)
    monkeypatch.setattr(updater, "update_local_addons", lambda: None)
    monkeypatch.setattr(updater, "disable_enable_addon", lambda: None)
    monkeypatch.setattr(updater, "update_kodi_addons_db", lambda: None)
    monkeypatch.setattr(updater, "kodilog", lambda *args, **kwargs: None)
    monkeypatch.setattr(updater, "translation", lambda string_id: f"string-{string_id}")
    monkeypatch.setattr(updater.xbmc, "getInfoLabel", lambda *args, **kwargs: "Default")

    return packages_dir, destination_dir


def test_downgrade_menu_only_lists_versions_older_than_current(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"name": "plugin.video.jacktook-1.8.0.zip"},
                {"name": "plugin.video.jacktook-1.7.2.zip"},
                {"name": "plugin.video.jacktook-1.6.0.zip"},
                {"name": "plugin.video.jacktook-1.9.0.zip"},
            ]

    selections = []

    monkeypatch.setattr(updater, "ADDON_VERSION", "1.8.0")
    monkeypatch.setattr(updater.requests, "get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(
        updater,
        "dialog_select",
        lambda heading, _list: selections.append((heading, _list)) or -1,
    )
    monkeypatch.setattr(updater, "dialog_ok", lambda *args, **kwargs: None)
    monkeypatch.setattr(updater, "kodilog", lambda *args, **kwargs: None)
    monkeypatch.setattr(updater, "translation", lambda string_id: f"string-{string_id}")

    updater.downgrade_addon_menu()

    assert selections == [("string-90585", ["1.7.2", "1.6.0"])]


def test_update_addon_keeps_current_install_when_zip_is_invalid(monkeypatch, tmp_path):
    _, destination_dir = _configure_updater_paths(monkeypatch, tmp_path)
    _write_addon_xml(destination_dir, "1.8.0")

    dialog_calls = []
    monkeypatch.setattr(updater, "dialog_ok", lambda *args, **kwargs: dialog_calls.append(kwargs))
    monkeypatch.setattr(updater, "http_get", lambda *args, **kwargs: io.BytesIO(b"not-a-zip"))

    updater.update_addon("1.7.2")

    assert updater._read_addon_version_from_xml(os.path.join(destination_dir, "addon.xml")) == "1.8.0"
    assert dialog_calls


def test_update_addon_restores_backup_when_install_move_fails(monkeypatch, tmp_path):
    packages_dir, destination_dir = _configure_updater_paths(monkeypatch, tmp_path)
    _write_addon_xml(destination_dir, "1.8.0")

    monkeypatch.setattr(
        updater,
        "http_get",
        lambda *args, **kwargs: io.BytesIO(_build_release_zip_bytes("1.7.2")),
    )
    monkeypatch.setattr(updater, "dialog_ok", lambda *args, **kwargs: None)

    real_move = shutil.move

    def failing_move(src, dst, *args, **kwargs):
        staging_addon_dir = os.path.join(
            str(packages_dir), f"{updater.ADDON_ID}-staging", updater.ADDON_ID
        )
        if src == staging_addon_dir and dst == str(destination_dir):
            raise OSError("install failed")
        return real_move(src, dst, *args, **kwargs)

    monkeypatch.setattr(updater.shutil, "move", failing_move)

    updater.update_addon("1.7.2")

    assert updater._read_addon_version_from_xml(os.path.join(destination_dir, "addon.xml")) == "1.8.0"
    assert not os.path.exists(os.path.join(str(packages_dir), f"{updater.ADDON_ID}-backup"))


def test_update_addon_installs_valid_downgrade(monkeypatch, tmp_path):
    packages_dir, destination_dir = _configure_updater_paths(monkeypatch, tmp_path)
    _write_addon_xml(destination_dir, "1.8.0")

    monkeypatch.setattr(
        updater,
        "http_get",
        lambda *args, **kwargs: io.BytesIO(_build_release_zip_bytes("1.7.2")),
    )
    monkeypatch.setattr(updater, "dialog_ok", lambda *args, **kwargs: None)

    updater.update_addon("1.7.2")

    assert updater._read_addon_version_from_xml(os.path.join(destination_dir, "addon.xml")) == "1.7.2"
    assert not os.path.exists(os.path.join(str(packages_dir), f"{updater.ADDON_ID}-backup"))
    assert not os.path.exists(os.path.join(str(packages_dir), f"{updater.ADDON_ID}-staging"))
