import json
import os
from pathlib import Path

import pytest

from lib import update_helper


def _plan(tmp_path):
    transaction_id = "a" * 32
    current = tmp_path / "plugin.video.jacktook"
    staging_root = tmp_path / f".plugin.video.jacktook-update-{transaction_id}"
    staged = staging_root / "payload" / "plugin.video.jacktook"
    backup = tmp_path / f".plugin.video.jacktook-backup-{transaction_id}"
    temp_dir = tmp_path / "kodi-temp"
    current.mkdir()
    staged.mkdir(parents=True)
    temp_dir.mkdir()
    (current / "marker").write_text("old")
    (staged / "marker").write_text("new")
    artifact_prefix = f"plugin.video.jacktook-update-{transaction_id}"
    helper_path = temp_dir / f"{artifact_prefix}.py"
    helper_path.write_text("# copied helper\n")
    plan_path = temp_dir / f"{artifact_prefix}.json"
    plan = {
        "addon_id": "plugin.video.jacktook",
        "transaction_id": transaction_id,
        "current_path": str(current),
        "staged_path": str(staged),
        "staging_root": str(staging_root),
        "backup_path": str(backup),
        "helper_path": str(helper_path),
        "source_version": "1.0.0",
        "target_version": "1.2.3",
        "original_enabled": True,
        "status": "staged",
    }
    plan_path.write_text(json.dumps(plan))
    return plan_path, plan, current, staging_root, backup, helper_path, temp_dir


def _fake_kodi(monkeypatch, current):
    state = {"enabled": True, "version": "1.0.0"}
    events = []

    monkeypatch.setattr(update_helper.xbmc, "sleep", lambda milliseconds: None)
    monkeypatch.setattr(update_helper, "_details", lambda addon_id: dict(state))

    def set_enabled(addon_id, enabled):
        events.append(("enabled", enabled))
        state["enabled"] = enabled

    def execute(command, block=None):
        marker = current / "marker"
        state["version"] = "1.2.3" if marker.exists() and marker.read_text() == "new" else "1.0.0"
        events.append((command, state["version"]))

    monkeypatch.setattr(update_helper, "_set_enabled", set_enabled)
    monkeypatch.setattr(update_helper.xbmc, "executebuiltin", execute)
    monkeypatch.setattr(update_helper.xbmc, "getCondVisibility", lambda condition: True)
    return state, events


@pytest.fixture(autouse=True)
def trusted_temp(monkeypatch, tmp_path):
    monkeypatch.setattr(
        update_helper.xbmcvfs,
        "translatePath",
        lambda path: str(tmp_path / "kodi-temp"),
    )


def test_apply_update_keeps_backup_until_kodi_confirms_and_reenables(monkeypatch, tmp_path):
    plan_path, _, current, staging_root, backup, helper_path, _ = _plan(tmp_path)
    _, events = _fake_kodi(monkeypatch, current)

    assert update_helper.apply_update(str(plan_path)) is True

    assert (current / "marker").read_text() == "new"
    assert ("UpdateLocalAddons", "1.2.3") in events
    assert events[0] == ("enabled", False)
    assert events[-2] == ("enabled", True)
    assert events[-1] == (
        'Container.Update("plugin://plugin.video.jacktook/",replace)',
        "1.2.3",
    )
    assert not backup.exists()
    assert not staging_root.exists()
    assert not plan_path.exists()
    assert not helper_path.exists()


def test_apply_update_opens_video_window_when_it_is_not_active(monkeypatch, tmp_path):
    plan_path, _, current, staging_root, backup, helper_path, _ = _plan(tmp_path)
    _, events = _fake_kodi(monkeypatch, current)
    monkeypatch.setattr(update_helper.xbmc, "getCondVisibility", lambda condition: False)

    assert update_helper.apply_update(str(plan_path)) is True

    assert events[-1] == (
        'ActivateWindow(10025,"plugin://plugin.video.jacktook/",return)',
        "1.2.3",
    )
    assert not backup.exists()
    assert not staging_root.exists()
    assert not plan_path.exists()
    assert not helper_path.exists()


@pytest.mark.parametrize("symlink_target", ["root", "ancestor"])
def test_validate_plan_rejects_symlinked_staging_path(tmp_path, symlink_target):
    plan_path, plan, _, staging_root, _, _, _ = _plan(tmp_path)
    outside = tmp_path / "outside"
    outside_staged = outside / "payload" / "plugin.video.jacktook"
    outside_staged.mkdir(parents=True)
    if symlink_target == "root":
        for child in sorted(staging_root.rglob("*"), reverse=True):
            child.rmdir() if child.is_dir() else child.unlink()
        staging_root.rmdir()
        staging_root.symlink_to(outside, target_is_directory=True)
    else:
        linked_parent = staging_root / "linked"
        linked_parent.symlink_to(outside / "payload", target_is_directory=True)
        plan["staged_path"] = str(linked_parent / "plugin.video.jacktook")
        plan_path.write_text(json.dumps(plan))

    with pytest.raises(ValueError, match="symlink"):
        update_helper._validate_plan(str(plan_path), plan)


@pytest.mark.parametrize("helper_variant", ["outside", "symlink"])
def test_validate_plan_confines_helper_cleanup(tmp_path, helper_variant):
    plan_path, plan, _, _, _, helper_path, _ = _plan(tmp_path)
    outside = tmp_path / "outside-helper.py"
    outside.write_text("# do not remove\n")
    if helper_variant == "outside":
        plan["helper_path"] = str(outside)
    else:
        helper_path.unlink()
        helper_path.symlink_to(outside)

    with pytest.raises(ValueError, match="helper"):
        update_helper._validate_plan(str(plan_path), plan)

    assert outside.exists()


def test_validate_plan_rejects_unrelated_canonical_staging_sibling(tmp_path):
    plan_path, plan, _, _, _, _, _ = _plan(tmp_path)
    unrelated_root = tmp_path / f".plugin.video.jacktook-update-{'b' * 32}"
    unrelated_staged = unrelated_root / "payload" / "plugin.video.jacktook"
    unrelated_staged.mkdir(parents=True)
    plan["staging_root"] = str(unrelated_root)
    plan["staged_path"] = str(unrelated_staged)

    with pytest.raises(ValueError, match="staging root"):
        update_helper._validate_plan(str(plan_path), plan)


def test_validate_plan_rejects_unrelated_canonical_temp_file(tmp_path):
    plan_path, plan, _, _, _, _, temp_dir = _plan(tmp_path)
    unrelated = temp_dir / "plugin.video.jacktook-update-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.py.bak"
    unrelated.write_text("# unrelated\n")
    plan["helper_path"] = str(unrelated)

    with pytest.raises(ValueError, match="helper"):
        update_helper._validate_plan(str(plan_path), plan)

    assert unrelated.exists()


@pytest.mark.parametrize("artifact_kind", ["helper", "plan"])
def test_validate_plan_rejects_mismatched_transaction_artifacts(tmp_path, artifact_kind):
    plan_path, plan, _, _, _, _, temp_dir = _plan(tmp_path)
    mismatched_prefix = f"plugin.video.jacktook-update-{'b' * 32}"
    if artifact_kind == "helper":
        mismatched_helper = temp_dir / f"{mismatched_prefix}.py"
        mismatched_helper.write_text("# wrong transaction\n")
        plan["helper_path"] = str(mismatched_helper)
    else:
        mismatched_plan = temp_dir / f"{mismatched_prefix}.json"
        plan_path.rename(mismatched_plan)
        plan_path = mismatched_plan

    with pytest.raises(ValueError, match="transaction"):
        update_helper._validate_plan(str(plan_path), plan)


@pytest.mark.parametrize("transaction_id", ["a" * 31, "A" * 32, "g" * 32, "../" + "a" * 29])
def test_validate_plan_rejects_invalid_transaction_format(tmp_path, transaction_id):
    plan_path, plan, _, _, _, _, _ = _plan(tmp_path)
    plan["transaction_id"] = transaction_id

    with pytest.raises(ValueError, match="transaction id"):
        update_helper._validate_plan(str(plan_path), plan)


def test_validate_plan_requires_fixed_jacktook_addon_id(tmp_path):
    plan_path, plan, _, _, _, _, _ = _plan(tmp_path)
    plan["addon_id"] = "plugin.video.other"

    with pytest.raises(ValueError, match="add-on id"):
        update_helper._validate_plan(str(plan_path), plan)


def test_disable_failure_leaves_source_enabled_and_confirmed(monkeypatch, tmp_path):
    plan_path, _, current, _, _, _, _ = _plan(tmp_path)
    state, _ = _fake_kodi(monkeypatch, current)
    calls = []

    def fail_disable(addon_id, enabled):
        calls.append(enabled)
        if not enabled:
            raise RuntimeError("disable failed")
        state["enabled"] = True

    monkeypatch.setattr(update_helper, "_set_enabled", fail_disable)

    assert update_helper.apply_update(str(plan_path)) is False
    assert (current / "marker").read_text() == "old"
    assert calls == [False, True]
    assert json.loads(plan_path.read_text())["rollback_complete"] is True


def test_second_rename_failure_restores_and_confirms_source(monkeypatch, tmp_path):
    plan_path, _, current, _, backup, _, _ = _plan(tmp_path)
    state, events = _fake_kodi(monkeypatch, current)
    messages = []
    real_rename = os.rename

    class Dialog:
        def ok(self, heading, message):
            messages.append(message)

    def fail_staged_rename(source, destination):
        if "payload" in str(source):
            raise OSError("second rename failed")
        real_rename(source, destination)

    monkeypatch.setattr(update_helper.os, "rename", fail_staged_rename)
    monkeypatch.setattr(update_helper.xbmcgui, "Dialog", Dialog)

    assert update_helper.apply_update(str(plan_path)) is False
    failure = json.loads(plan_path.read_text())
    assert failure["rollback_complete"] is True
    assert (current / "marker").read_text() == "old"
    assert not backup.exists()
    assert state == {"enabled": True, "version": "1.0.0"}
    assert ("UpdateLocalAddons", "1.0.0") in events
    assert messages == ["Update failed and the previous version was restored and confirmed."]


def test_target_version_timeout_rolls_back_and_confirms_source(monkeypatch, tmp_path):
    plan_path, _, current, _, _, _, _ = _plan(tmp_path)
    state, _ = _fake_kodi(monkeypatch, current)
    real_wait = update_helper._wait_for
    target_waits = 0

    def fail_target_wait(addon_id, predicate, timeout):
        nonlocal target_waits
        if timeout == update_helper.VERSION_TIMEOUT_SECONDS and state["version"] == "1.2.3":
            target_waits += 1
            raise RuntimeError("target version timeout")
        return real_wait(addon_id, predicate, timeout)

    monkeypatch.setattr(update_helper, "_wait_for", fail_target_wait)

    assert update_helper.apply_update(str(plan_path)) is False
    assert target_waits == 1
    assert (current / "marker").read_text() == "old"
    assert json.loads(plan_path.read_text())["rollback_complete"] is True


def test_target_reenable_failure_rolls_back_and_reenables_source(monkeypatch, tmp_path):
    plan_path, _, current, _, _, _, _ = _plan(tmp_path)
    state, _ = _fake_kodi(monkeypatch, current)
    enable_calls = 0

    def fail_first_enable(addon_id, enabled):
        nonlocal enable_calls
        if enabled:
            enable_calls += 1
            if enable_calls == 1:
                raise RuntimeError("re-enable failed")
        state["enabled"] = enabled

    monkeypatch.setattr(update_helper, "_set_enabled", fail_first_enable)

    assert update_helper.apply_update(str(plan_path)) is False
    assert enable_calls == 2
    assert state == {"enabled": True, "version": "1.0.0"}
    assert json.loads(plan_path.read_text())["rollback_complete"] is True


def test_cleanup_failure_after_confirmation_does_not_rollback(monkeypatch, tmp_path):
    plan_path, _, current, staging_root, backup, _, _ = _plan(tmp_path)
    state, _ = _fake_kodi(monkeypatch, current)
    real_remove_tree = update_helper._remove_tree

    def fail_staging_cleanup(path):
        if path == str(staging_root):
            raise OSError("cleanup failed")
        real_remove_tree(path)

    monkeypatch.setattr(update_helper, "_remove_tree", fail_staging_cleanup)

    assert update_helper.apply_update(str(plan_path)) is True
    assert (current / "marker").read_text() == "new"
    assert state == {"enabled": True, "version": "1.2.3"}
    assert not backup.exists()


def test_rollback_failure_is_reported_incomplete(monkeypatch, tmp_path):
    plan_path, _, current, _, backup, _, _ = _plan(tmp_path)
    _fake_kodi(monkeypatch, current)
    messages = []
    real_rename = os.rename

    class Dialog:
        def ok(self, heading, message):
            messages.append(message)

    def fail_install_and_restore(source, destination):
        if "payload" in str(source):
            raise OSError("install failed")
        if str(source) == str(backup):
            raise OSError("restore failed")
        real_rename(source, destination)

    monkeypatch.setattr(update_helper.os, "rename", fail_install_and_restore)
    monkeypatch.setattr(update_helper.xbmcgui, "Dialog", Dialog)

    assert update_helper.apply_update(str(plan_path)) is False
    failure = json.loads(plan_path.read_text())
    assert failure["rollback_complete"] is False
    assert "restore failed" in " ".join(failure["rollback_errors"])
    assert backup.exists()
    assert messages == ["Update failed and rollback is incomplete. Check the Kodi log."]


def test_helper_is_standalone():
    source = Path(update_helper.__file__).read_text()

    assert "from lib" not in source
    assert "import lib" not in source
    assert "LoadProfile" not in source
    assert "Addons.db" not in source
