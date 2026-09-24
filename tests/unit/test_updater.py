import hashlib
import inspect
import io
import json
import os
import stat
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lib import navigation, router, update_helper, updater
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
    monkeypatch.setattr(
        updater,
        "update_addon",
        lambda version: builtins.append(("stage_update", version)),
    )
    translations = {
        90579: "No update available.",
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


def test_manual_update_stages_exact_version_after_confirmation(monkeypatch):
    builtins, _ = _configure_update_check(monkeypatch, updater.UPDATE_ACTION_NONE)

    updater.updates_check_addon()

    assert builtins == [("stage_update", "1.1.0")]


def test_automatic_ask_installs_only_after_confirmation(monkeypatch):
    builtins, _ = _configure_update_check(monkeypatch, updater.UPDATE_ACTION_ASK)

    updater.updates_check_addon(automatic=True)

    assert builtins == [("stage_update", "1.1.0")]


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


def test_updater_does_not_modify_kodi_database_or_reload_profile():
    source = inspect.getsource(updater)

    assert "Addons.db" not in source
    assert "LoadProfile" not in source


def test_downgrade_route_and_setting_are_removed():
    settings_xml = Path(__file__).parents[2] / "resources" / "settings.xml"

    assert "downgrade_addon" not in inspect.getsource(navigation)
    assert "downgrade_addon" not in inspect.getsource(router)
    assert "downgrade_addon" not in settings_xml.read_text(encoding="utf-8")


def test_version_less_than_compares_numeric_segments():
    assert updater.version_less_than("1.9.0", "1.10.0") is True
    assert updater.version_less_than("1.10.0", "1.9.0") is False


def test_version_less_than_equal_versions():
    assert updater.version_less_than("1.0.0", "1.0.0") is False


def test_equivalent_version_formats_are_not_ordered():
    # "1.0" and "1.0.0" are the same release: never offer an update between them.
    assert updater.version_less_than("1.0", "1.0.0") is False
    assert updater.version_less_than("1.0.0", "1.0") is False


def test_prerelease_sorts_before_its_final_release():
    assert updater.version_less_than("1.0.0-beta", "1.0.0") is True
    assert updater.version_less_than("1.0.0", "1.0.0-beta") is False


def test_numbered_release_candidates_use_natural_prerelease_order():
    assert updater.version_less_than("1.0.0-rc1", "1.0.0") is True
    assert updater.version_less_than("1.0.0", "1.0.0-rc1") is False
    assert updater.version_less_than("1.0.0-rc2", "1.0.0-rc10") is True
    assert updater.version_less_than("1.0.0-rc10", "1.0.0-rc2") is False


def test_equivalent_versions_report_no_update(monkeypatch):
    builtins, notifications = _configure_update_check(
        monkeypatch,
        updater.UPDATE_ACTION_NONE,
        current_version="1.0",
        online_version="1.0.0",
    )

    updater.updates_check_addon()

    assert builtins == []
    assert notifications == [{"heading": updater.HEADING, "message": "No update available."}]


def test_http_get_uses_timeout(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        resp = MagicMock()
        resp.text = "1.2.3"
        return resp

    monkeypatch.setattr(updater.requests, "get", fake_get)

    assert updater.http_get("https://example.test/version") == "1.2.3"
    assert calls[0][1]["timeout"] == updater.HTTP_TIMEOUT


def test_automatic_none_skips_network_entirely(monkeypatch):
    fetched = []

    def fake_versions():
        fetched.append(True)
        return "1.0.0", "1.1.0"

    monkeypatch.setattr(settings, "get_update_action", lambda: updater.UPDATE_ACTION_NONE)
    monkeypatch.setattr(updater, "get_versions", fake_versions)
    monkeypatch.setattr(updater, "kodilog", lambda *args, **kwargs: None)

    updater.updates_check_addon(automatic=True)

    assert fetched == []


def test_automatic_check_shows_no_busy_dialog(monkeypatch):
    dialogs = []
    monkeypatch.setattr(settings, "get_update_action", lambda: updater.UPDATE_ACTION_NOTIFY)
    monkeypatch.setattr(updater, "get_versions", lambda: ("1.0.0", "1.0.0"))
    monkeypatch.setattr(updater, "show_busy_dialog", lambda: dialogs.append("show"))
    monkeypatch.setattr(updater, "close_busy_dialog", lambda: dialogs.append("close"))
    monkeypatch.setattr(updater, "kodilog", lambda *args, **kwargs: None)

    updater.updates_check_addon(automatic=True)

    assert dialogs == []


def test_manual_check_shows_busy_dialog(monkeypatch):
    dialogs = []
    monkeypatch.setattr(updater, "get_versions", lambda: ("1.0.0", "1.0.0"))
    monkeypatch.setattr(updater, "show_busy_dialog", lambda: dialogs.append("show"))
    monkeypatch.setattr(updater, "close_busy_dialog", lambda: dialogs.append("close"))
    monkeypatch.setattr(updater, "kodilog", lambda *args, **kwargs: None)
    monkeypatch.setattr(updater, "notification", lambda **kwargs: None)

    updater.updates_check_addon()

    assert dialogs == ["show", "close"]


def _zip_bytes(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    return output.getvalue()


def _valid_package(version="1.2.3"):
    return _zip_bytes(
        [
            (
                f"{updater.ADDON_ID}/addon.xml",
                f'<addon id="{updater.ADDON_ID}" version="{version}"/>',
            ),
            (f"{updater.ADDON_ID}/lib/module.py", "value = 1\n"),
        ]
    )


def test_validated_archive_extracts_only_valid_package(tmp_path):
    package = tmp_path / "package.zip"
    package.write_bytes(_valid_package())

    entries = updater._validated_archive_entries(package, "1.2.3")
    destination = tmp_path / "payload"
    updater._extract_validated_package(package, destination, entries)

    addon_xml = destination / updater.ADDON_ID / "addon.xml"
    assert addon_xml.is_file()
    assert 'version="1.2.3"' in addon_xml.read_text()


@pytest.mark.parametrize(
    "name",
    [
        "outside.txt",
        f"{updater.ADDON_ID}/../outside.txt",
        f"{updater.ADDON_ID}\\outside.txt",
        f"/{updater.ADDON_ID}/outside.txt",
    ],
)
def test_validated_archive_rejects_unsafe_paths(tmp_path, name):
    package = tmp_path / "unsafe.zip"
    package.write_bytes(
        _zip_bytes(
            [
                (
                    f"{updater.ADDON_ID}/addon.xml",
                    f'<addon id="{updater.ADDON_ID}" version="1.2.3"/>',
                ),
                (name, "unsafe"),
            ]
        )
    )

    with pytest.raises(ValueError):
        updater._validated_archive_entries(package, "1.2.3")


def test_validated_archive_rejects_duplicate_names(tmp_path):
    package = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(
            f"{updater.ADDON_ID}/addon.xml",
            f'<addon id="{updater.ADDON_ID}" version="1.2.3"/>',
        )
        archive.writestr(f"{updater.ADDON_ID}/file.txt", "first")
        archive.writestr(f"{updater.ADDON_ID}/FILE.txt", "second")

    with pytest.raises(ValueError, match="duplicate"):
        updater._validated_archive_entries(package, "1.2.3")


def test_validated_archive_rejects_symlink(tmp_path):
    package = tmp_path / "symlink.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(
            f"{updater.ADDON_ID}/addon.xml",
            f'<addon id="{updater.ADDON_ID}" version="1.2.3"/>',
        )
        link = zipfile.ZipInfo(f"{updater.ADDON_ID}/link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(link, "target")

    with pytest.raises(ValueError, match="symlink"):
        updater._validated_archive_entries(package, "1.2.3")


def test_validated_archive_rejects_non_regular_special_entry(tmp_path):
    package = tmp_path / "special.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(
            f"{updater.ADDON_ID}/addon.xml",
            f'<addon id="{updater.ADDON_ID}" version="1.2.3"/>',
        )
        special = zipfile.ZipInfo(f"{updater.ADDON_ID}/pipe")
        special.create_system = 3
        special.external_attr = (stat.S_IFIFO | 0o600) << 16
        archive.writestr(special, "")

    with pytest.raises(ValueError, match="special"):
        updater._validated_archive_entries(package, "1.2.3")


def test_validated_archive_rejects_encrypted_entry(tmp_path):
    package = tmp_path / "encrypted.zip"
    data = bytearray(_valid_package())
    for signature, flag_offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        offset = 0
        while True:
            offset = data.find(signature, offset)
            if offset < 0:
                break
            flags_at = offset + flag_offset
            flags = int.from_bytes(data[flags_at : flags_at + 2], "little") | 1
            data[flags_at : flags_at + 2] = flags.to_bytes(2, "little")
            offset += 4
    package.write_bytes(data)

    with pytest.raises(ValueError, match="Encrypted"):
        updater._validated_archive_entries(package, "1.2.3")


@pytest.mark.parametrize(
    "reserved_name",
    ["CON", "nul.txt", "Aux.JSON", "prn", "COM1.py", "com9", "LPT1.xml", "lpt9"],
)
def test_validated_archive_rejects_windows_reserved_device_names(tmp_path, reserved_name):
    package = tmp_path / "reserved.zip"
    package.write_bytes(
        _zip_bytes(
            [
                (
                    f"{updater.ADDON_ID}/addon.xml",
                    f'<addon id="{updater.ADDON_ID}" version="1.2.3"/>',
                ),
                (f"{updater.ADDON_ID}/{reserved_name}", "unsafe"),
            ]
        )
    )

    with pytest.raises(ValueError, match="reserved"):
        updater._validated_archive_entries(package, "1.2.3")


@pytest.mark.parametrize(
    ("limit_name", "limit", "extra_data", "error"),
    [
        ("MAX_FILE_BYTES", 20, b"x" * 21, "per-file"),
        ("MAX_UNCOMPRESSED_BYTES", 80, b"x" * 50, "uncompressed"),
    ],
)
def test_validated_archive_enforces_size_limits(
    monkeypatch, tmp_path, limit_name, limit, extra_data, error
):
    package = tmp_path / "limited.zip"
    package.write_bytes(
        _zip_bytes(
            [
                (
                    f"{updater.ADDON_ID}/addon.xml",
                    f'<addon id="{updater.ADDON_ID}" version="1.2.3"/>',
                ),
                (f"{updater.ADDON_ID}/data.bin", extra_data),
            ]
        )
    )
    monkeypatch.setattr(updater, limit_name, limit)

    with pytest.raises(ValueError, match=error):
        updater._validated_archive_entries(package, "1.2.3")


def test_validated_archive_rejects_suspicious_aggregate_compression(tmp_path):
    package = tmp_path / "ratio.zip"
    package.write_bytes(
        _zip_bytes(
            [
                (
                    f"{updater.ADDON_ID}/addon.xml",
                    f'<addon id="{updater.ADDON_ID}" version="1.2.3"/>',
                ),
                (f"{updater.ADDON_ID}/one.txt", "a" * 200_000),
                (f"{updater.ADDON_ID}/two.txt", "b" * 200_000),
            ]
        )
    )

    with pytest.raises(ValueError, match="aggregate compression"):
        updater._validated_archive_entries(package, "1.2.3")


@pytest.mark.parametrize(
    ("addon_id", "version"),
    [("plugin.video.other", "1.2.3"), (updater.ADDON_ID, "9.9.9")],
)
def test_validated_archive_rejects_addon_identity_mismatch(tmp_path, addon_id, version):
    package = tmp_path / "identity.zip"
    package.write_bytes(
        _zip_bytes(
            [
                (
                    f"{updater.ADDON_ID}/addon.xml",
                    f'<addon id="{addon_id}" version="{version}"/>',
                )
            ]
        )
    )

    with pytest.raises(ValueError, match="mismatch"):
        updater._validated_archive_entries(package, "1.2.3")


class _StreamResponse:
    def __init__(self, data, content_length=None):
        self.data = data
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        for offset in range(0, len(self.data), chunk_size):
            yield self.data[offset : offset + chunk_size]


def test_fetch_metadata_requires_exact_repository_object(monkeypatch):
    metadata = {
        "type": "file",
        "name": f"{updater.ADDON_ID}-1.2.3.zip",
        "size": 123,
        "sha": "a" * 40,
    }
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return _StreamResponse(json.dumps(metadata).encode())

    monkeypatch.setattr(updater.requests, "get", fake_get)

    assert updater._fetch_package_metadata("1.2.3") == {
        "name": metadata["name"],
        "size": 123,
        "sha": "a" * 40,
    }
    assert calls[0][0].endswith(f"/{metadata['name']}?ref=main")
    assert calls[0][1]["timeout"] == updater.HTTP_TIMEOUT


def test_fetch_metadata_rejects_bounded_response_overflow(monkeypatch):
    monkeypatch.setattr(updater, "MAX_METADATA_BYTES", 16)
    monkeypatch.setattr(
        updater.requests,
        "get",
        lambda *args, **kwargs: _StreamResponse(b"{" + b"x" * 32),
    )

    with pytest.raises(ValueError, match="size limit"):
        updater._fetch_package_metadata("1.2.3")


def test_download_package_verifies_git_blob_and_exact_size(monkeypatch, tmp_path):
    data = b"verified package bytes"
    digest = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    metadata = {"name": "package.zip", "size": len(data), "sha": digest}
    monkeypatch.setattr(
        updater.requests,
        "get",
        lambda *args, **kwargs: _StreamResponse(data, len(data)),
    )
    destination = tmp_path / "package.zip"

    updater._download_package("1.2.3", metadata, destination)

    assert destination.read_bytes() == data


def test_download_package_removes_partial_on_size_mismatch(monkeypatch, tmp_path):
    data = b"too long"
    metadata = {"name": "package.zip", "size": 2, "sha": "a" * 40}
    monkeypatch.setattr(
        updater.requests,
        "get",
        lambda *args, **kwargs: _StreamResponse(data),
    )
    destination = tmp_path / "partial.zip"

    with pytest.raises(ValueError, match="exceeds"):
        updater._download_package("1.2.3", metadata, destination)

    assert not destination.exists()


@pytest.mark.parametrize(
    ("data", "declared_size", "sha", "content_length", "error"),
    [
        (b"short", 10, "a" * 40, None, "size does not match"),
        (b"wrong digest", 12, "a" * 40, 12, "SHA mismatch"),
        (b"content", 7, "a" * 40, "not-a-number", "invalid literal"),
    ],
)
def test_download_package_cleans_up_on_integrity_failures(
    monkeypatch, tmp_path, data, declared_size, sha, content_length, error
):
    metadata = {"name": "package.zip", "size": declared_size, "sha": sha}
    monkeypatch.setattr(
        updater.requests,
        "get",
        lambda *args, **kwargs: _StreamResponse(data, content_length),
    )
    destination = tmp_path / "failed.zip"

    with pytest.raises(ValueError, match=error):
        updater._download_package("1.2.3", metadata, destination)

    assert not destination.exists()


def test_update_addon_launches_copied_helper_after_staging(monkeypatch, tmp_path):
    installed = tmp_path / updater.ADDON_ID
    (installed / "lib").mkdir(parents=True)
    (installed / "lib" / "update_helper.py").write_text("# helper\n")
    package_data = _valid_package()
    package_sha = hashlib.sha1(f"blob {len(package_data)}\0".encode() + package_data).hexdigest()
    metadata = {
        "name": f"{updater.ADDON_ID}-1.2.3.zip",
        "size": len(package_data),
        "sha": package_sha,
    }
    temp_dir = tmp_path / "kodi-temp"
    calls = []
    monkeypatch.setattr(updater, "ADDON_PATH", str(installed))
    monkeypatch.setattr(updater, "ADDON_VERSION", "1.0.0")
    monkeypatch.setattr(updater.secrets, "token_hex", lambda size: "c" * 32)
    monkeypatch.setattr(updater, "translate_path", lambda path: str(temp_dir))
    monkeypatch.setattr(update_helper.xbmcvfs, "translatePath", lambda path: str(temp_dir))
    monkeypatch.setattr(updater, "_fetch_package_metadata", lambda version: metadata)
    monkeypatch.setattr(
        updater,
        "_download_package",
        lambda version, meta, path: Path(path).write_bytes(package_data),
    )
    monkeypatch.setattr(updater, "close_all_dialog", lambda: calls.append("close_all"))
    monkeypatch.setattr(updater, "show_busy_dialog", lambda: calls.append("show_busy"))
    monkeypatch.setattr(updater, "close_busy_dialog", lambda: calls.append("close_busy"))
    monkeypatch.setattr(updater, "execute_builtin", lambda command: calls.append(command))
    monkeypatch.setattr(updater, "notification", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(updater, "kodilog", lambda message: None)

    assert updater.update_addon("1.2.3") is True

    run_script = next(
        call for call in calls if isinstance(call, str) and call.startswith("RunScript")
    )
    plans = list(temp_dir.glob("*.json"))
    assert len(plans) == 1
    plan = json.loads(plans[0].read_text())
    assert plan["target_version"] == "1.2.3"
    assert plan["source_version"] == "1.0.0"
    assert plan["transaction_id"] == "c" * 32
    assert plan["original_enabled"] is True
    assert os.path.dirname(plan["staging_root"]) == str(tmp_path)
    assert calls[:2] == ["close_all", "show_busy"]
    assert "close_busy" in calls
    assert run_script == f'RunScript("{plan["helper_path"]}","{plans[0]}")'
    canonical_plan, validated = update_helper._validate_plan(str(plans[0]), plan)
    assert canonical_plan == str(plans[0])
    assert validated["staging_root"] == plan["staging_root"]


@pytest.mark.parametrize("existing_artifact", ["helper", "plan"])
def test_write_update_plan_never_overwrites_transaction_artifacts(
    monkeypatch, tmp_path, existing_artifact
):
    transaction_id = "d" * 32
    installed = tmp_path / updater.ADDON_ID
    staged = (
        tmp_path / f".{updater.ADDON_ID}-update-{transaction_id}" / "payload" / updater.ADDON_ID
    )
    temp_dir = tmp_path / "kodi-temp"
    (installed / "lib").mkdir(parents=True)
    staged.mkdir(parents=True)
    temp_dir.mkdir()
    (installed / "lib" / "update_helper.py").write_text("# helper source\n")
    prefix = f"{updater.ADDON_ID}-update-{transaction_id}"
    artifact = temp_dir / f"{prefix}.{'py' if existing_artifact == 'helper' else 'json'}"
    artifact.write_text("unrelated")
    monkeypatch.setattr(updater, "ADDON_PATH", str(installed))
    monkeypatch.setattr(updater, "ADDON_VERSION", "1.0.0")
    monkeypatch.setattr(updater, "translate_path", lambda path: str(temp_dir))

    with pytest.raises(FileExistsError):
        updater._write_update_plan(
            str(staged.parents[1]),
            str(staged),
            "1.2.3",
            {"sha": "a" * 40},
            transaction_id,
        )

    assert artifact.read_text() == "unrelated"
    assert sorted(path.name for path in temp_dir.iterdir()) == [artifact.name]


def test_update_addon_does_not_remove_colliding_transaction_directory(monkeypatch, tmp_path):
    transaction_id = "e" * 32
    installed = tmp_path / updater.ADDON_ID
    (installed / "lib").mkdir(parents=True)
    (installed / "lib" / "update_helper.py").write_text("# helper\n")
    collision = tmp_path / f".{updater.ADDON_ID}-update-{transaction_id}"
    collision.mkdir()
    marker = collision / "unrelated"
    marker.write_text("preserve")
    fetched = []
    monkeypatch.setattr(updater, "ADDON_PATH", str(installed))
    monkeypatch.setattr(updater.secrets, "token_hex", lambda size: transaction_id)
    monkeypatch.setattr(updater, "_fetch_package_metadata", lambda version: fetched.append(version))
    monkeypatch.setattr(updater, "close_all_dialog", lambda: None)
    monkeypatch.setattr(updater, "show_busy_dialog", lambda: None)
    monkeypatch.setattr(updater, "close_busy_dialog", lambda: None)
    monkeypatch.setattr(updater, "dialog_ok", lambda **kwargs: None)
    monkeypatch.setattr(updater, "kodilog", lambda message: None)

    assert updater.update_addon("1.2.3") is False
    assert marker.read_text() == "preserve"
    assert fetched == []


@pytest.mark.parametrize("failure_phase", ["staging", "launch"])
def test_update_addon_cleans_all_artifacts_on_pre_handoff_failure(
    monkeypatch, tmp_path, failure_phase
):
    installed = tmp_path / updater.ADDON_ID
    (installed / "lib").mkdir(parents=True)
    (installed / "lib" / "update_helper.py").write_text("# helper\n")
    package_data = _valid_package()
    metadata = {
        "name": f"{updater.ADDON_ID}-1.2.3.zip",
        "size": len(package_data),
        "sha": hashlib.sha1(f"blob {len(package_data)}\0".encode() + package_data).hexdigest(),
    }
    temp_dir = tmp_path / "kodi-temp"
    monkeypatch.setattr(updater, "ADDON_PATH", str(installed))
    monkeypatch.setattr(updater, "ADDON_VERSION", "1.0.0")
    monkeypatch.setattr(updater, "translate_path", lambda path: str(temp_dir))
    monkeypatch.setattr(updater, "_fetch_package_metadata", lambda version: metadata)
    monkeypatch.setattr(updater, "close_all_dialog", lambda: None)
    monkeypatch.setattr(updater, "show_busy_dialog", lambda: None)
    monkeypatch.setattr(updater, "close_busy_dialog", lambda: None)
    monkeypatch.setattr(updater, "notification", lambda **kwargs: None)
    monkeypatch.setattr(updater, "dialog_ok", lambda **kwargs: None)
    monkeypatch.setattr(updater, "kodilog", lambda message: None)

    if failure_phase == "staging":

        def fail_download(version, package_metadata, path):
            Path(path).write_bytes(b"partial")
            raise OSError("download failed")

        monkeypatch.setattr(updater, "_download_package", fail_download)
        monkeypatch.setattr(updater, "execute_builtin", lambda command: None)
    else:
        monkeypatch.setattr(
            updater,
            "_download_package",
            lambda version, package_metadata, path: Path(path).write_bytes(package_data),
        )
        monkeypatch.setattr(
            updater,
            "execute_builtin",
            lambda command: (_ for _ in ()).throw(RuntimeError("launch failed")),
        )

    assert updater.update_addon("1.2.3") is False
    assert list(tmp_path.glob(f".{updater.ADDON_ID}-update-*")) == []
    assert not temp_dir.exists() or list(temp_dir.iterdir()) == []
