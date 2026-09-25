"""Standalone Kodi-side helper that replaces a staged Jacktook installation.

This file is copied to ``special://temp`` before execution. Keep it limited to
the standard library and Kodi modules: the installed add-on is moved while this
script runs, so importing ``lib`` here would make rollback unreliable.
"""

import contextlib
import json
import os
import re
import shutil
import sys
import time

import xbmc
import xbmcgui
import xbmcvfs

DISABLE_TIMEOUT_SECONDS = 10
VERSION_TIMEOUT_SECONDS = 20
POLL_INTERVAL_SECONDS = 0.25
ADDON_ID = "plugin.video.jacktook"
TRANSACTION_PATTERN = re.compile(r"[0-9a-f]{32}")


def _json_rpc(method, params):
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    response = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    if "error" in response:
        raise RuntimeError(f"Kodi JSON-RPC failed: {response['error'].get('message', 'error')}")
    return response.get("result", {})


def _details(addon_id):
    result = _json_rpc(
        "Addons.GetAddonDetails",
        {"addonid": addon_id, "properties": ["enabled", "version"]},
    )
    return result.get("addon", {})


def _set_enabled(addon_id, enabled):
    _json_rpc("Addons.SetAddonEnabled", {"addonid": addon_id, "enabled": enabled})


def _wait_for(addon_id, predicate, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            details = _details(addon_id)
            if predicate(details):
                return details
        except Exception:
            pass
        xbmc.sleep(int(POLL_INTERVAL_SECONDS * 1000))
    raise RuntimeError("Timed out waiting for Kodi add-on state")


def _remove_tree(path):
    if os.path.lexists(path):
        if os.path.islink(path) or not os.path.isdir(path):
            os.remove(path)
        else:
            shutil.rmtree(path)


def _remove_canonical_tree(path, kind):
    if not os.path.lexists(path):
        return
    if _canonical_existing(path, kind) != path:
        raise ValueError(f"Update {kind} path changed after validation")
    _remove_tree(path)


def _remove_canonical_file(path, kind):
    if not os.path.lexists(path):
        return
    if _canonical_existing(path, kind) != path or not os.path.isfile(path):
        raise ValueError(f"Update {kind} file changed after validation")
    os.remove(path)


def _save_failure(plan_path, plan, phase, error, rollback_complete, rollback_errors):
    plan["status"] = "failed"
    plan["phase"] = phase
    plan["error"] = f"{type(error).__name__}: {str(error)[:500]}"
    plan["rollback_complete"] = rollback_complete
    if rollback_errors:
        plan["rollback_errors"] = [
            f"{type(item).__name__}: {str(item)[:500]}" for item in rollback_errors
        ]
    with open(plan_path, "w", encoding="utf-8") as plan_file:
        json.dump(plan, plan_file, sort_keys=True)


def _canonical_existing(path, kind):
    absolute = os.path.abspath(path)
    canonical = os.path.realpath(absolute)
    if absolute != canonical or os.path.islink(absolute):
        raise ValueError(f"Update plan {kind} path uses a symlink")
    return canonical


def _validate_plan(plan_path, plan):
    """Validate and canonicalize every path used for rename or cleanup."""
    canonical_plan = _canonical_existing(plan_path, "plan")
    trusted_temp = os.path.realpath(xbmcvfs.translatePath("special://temp"))
    if os.path.dirname(canonical_plan) != trusted_temp or not os.path.isfile(canonical_plan):
        raise ValueError("Update plan is outside the trusted Kodi temp directory")

    addon_id = plan["addon_id"]
    if addon_id != ADDON_ID:
        raise ValueError("Update plan add-on id mismatch")
    transaction_id = plan.get("transaction_id")
    if not isinstance(transaction_id, str) or not TRANSACTION_PATTERN.fullmatch(transaction_id):
        raise ValueError("Update plan transaction id is invalid")
    current = _canonical_existing(plan["current_path"], "installed add-on")
    staging_root = _canonical_existing(plan["staging_root"], "staging root")
    staged = _canonical_existing(plan["staged_path"], "staged add-on")
    backup = os.path.realpath(os.path.abspath(plan["backup_path"]))
    helper = _canonical_existing(plan["helper_path"], "helper")
    current_parent = os.path.dirname(current)
    expected_staging_root = os.path.join(current_parent, f".{ADDON_ID}-update-{transaction_id}")
    expected_staged = os.path.join(expected_staging_root, "payload", ADDON_ID)
    expected_backup = os.path.join(current_parent, f".{ADDON_ID}-backup-{transaction_id}")
    artifact_prefix = f"{ADDON_ID}-update-{transaction_id}"
    expected_helper = os.path.join(trusted_temp, f"{artifact_prefix}.py")
    expected_plan = os.path.join(trusted_temp, f"{artifact_prefix}.json")
    if os.path.basename(current) != ADDON_ID:
        raise ValueError("Update plan add-on path mismatch")
    if not os.path.isdir(current) or not os.path.isdir(staging_root) or not os.path.isdir(staged):
        raise ValueError("Update plan add-on directories are unavailable")
    if staging_root != expected_staging_root:
        raise ValueError("Update staging root does not match the transaction")
    if staged != expected_staged:
        raise ValueError("Staged add-on path does not match the transaction")
    if backup != expected_backup:
        raise ValueError("Update plan backup path mismatch")
    if helper != expected_helper or not os.path.isfile(helper):
        raise ValueError("Update helper does not match the transaction")
    if canonical_plan != expected_plan:
        raise ValueError("Update plan path does not match the transaction")
    if os.path.lexists(backup):
        raise ValueError("Update backup path already exists")
    source_version = plan.get("source_version")
    target_version = plan.get("target_version")
    if not isinstance(source_version, str) or not source_version:
        raise ValueError("Update plan source version is invalid")
    if not isinstance(target_version, str) or not target_version:
        raise ValueError("Update plan target version is invalid")
    if plan.get("original_enabled") is not True:
        raise ValueError("Update plan must preserve the enabled state")

    validated = dict(plan)
    validated.update(
        {
            "current_path": current,
            "staged_path": staged,
            "staging_root": staging_root,
            "backup_path": backup,
            "helper_path": helper,
        }
    )
    return canonical_plan, validated


def _restore_previous_version(plan, addon_id, current_path, backup_path):
    """Restore files and wait until Kodi confirms source version and enabled state."""
    errors = []
    filesystem_restored = False
    version_restored = False
    enabled_restored = False
    try:
        if (
            not os.path.isdir(backup_path)
            or _canonical_existing(backup_path, "backup") != backup_path
        ):
            raise RuntimeError("Update backup is unavailable")
        _remove_canonical_tree(current_path, "replacement")
        os.rename(backup_path, current_path)
        filesystem_restored = True
        xbmc.executebuiltin("UpdateLocalAddons", True)
        _wait_for(
            addon_id,
            lambda details: details.get("version") == plan["source_version"],
            VERSION_TIMEOUT_SECONDS,
        )
        version_restored = True
    except Exception as error:
        errors.append(error)
    try:
        _set_enabled(addon_id, plan["original_enabled"])
        _wait_for(
            addon_id,
            lambda details: details.get("enabled") is plan["original_enabled"],
            DISABLE_TIMEOUT_SECONDS,
        )
        enabled_restored = True
    except Exception as error:
        errors.append(error)
    complete = filesystem_restored and version_restored and enabled_restored
    return complete, errors


def apply_update(plan_path):
    """Apply one update plan, rolling back any failure after backup creation."""
    try:
        with open(plan_path, encoding="utf-8") as plan_file:
            plan = json.load(plan_file)
        plan_path, plan = _validate_plan(plan_path, plan)
    except Exception as error:
        xbmc.log(
            f"Jacktook update plan validation failed: {type(error).__name__}: {error}",
            xbmc.LOGERROR,
        )
        xbmcgui.Dialog().ok("Jacktook Updater", "Update plan validation failed.")
        return False
    addon_id = plan["addon_id"]
    current_path = plan["current_path"]
    staged_path = plan["staged_path"]
    backup_path = plan["backup_path"]
    original_enabled = plan.get("original_enabled", True)
    phase = "waiting_for_invocation"
    backed_up = False

    try:
        xbmc.sleep(2000)
        phase = "validating_source"
        source_details = _details(addon_id)
        if source_details.get("version") != plan["source_version"]:
            raise RuntimeError("Installed add-on version changed before update")
        if source_details.get("enabled") is not original_enabled or not original_enabled:
            raise RuntimeError("Update plan expected the running add-on to be enabled")
        phase = "disabling"
        _set_enabled(addon_id, False)
        _wait_for(
            addon_id,
            lambda details: details.get("enabled") is False,
            DISABLE_TIMEOUT_SECONDS,
        )
        xbmc.sleep(500)

        phase = "backing_up"
        if _canonical_existing(current_path, "installed add-on") != current_path:
            raise RuntimeError("Installed add-on path changed after validation")
        if _canonical_existing(staged_path, "staged add-on") != staged_path:
            raise RuntimeError("Staged add-on path changed after validation")
        if os.path.lexists(backup_path):
            raise RuntimeError("Update backup path appeared after validation")
        os.rename(current_path, backup_path)
        backed_up = True

        phase = "installing"
        os.rename(staged_path, current_path)
        phase = "rescanning"
        xbmc.executebuiltin("UpdateLocalAddons", True)
        _wait_for(
            addon_id,
            lambda details: details.get("version") == plan["target_version"],
            VERSION_TIMEOUT_SECONDS,
        )

        phase = "enabling"
        _set_enabled(addon_id, original_enabled)
        _wait_for(
            addon_id,
            lambda details: details.get("enabled") is original_enabled,
            DISABLE_TIMEOUT_SECONDS,
        )

        # Replacement is committed once Kodi confirms and re-enables the new
        # version. Cleanup is deliberately outside the rollback transaction:
        # a cleanup error must never delete a confirmed install after its
        # backup has already been removed.
        phase = "cleanup"
        cleanup_errors = []
        plan["status"] = "applied"
        try:
            if _canonical_existing(plan_path, "plan") != plan_path:
                raise ValueError("Update plan path changed after validation")
            with open(plan_path, "w", encoding="utf-8") as plan_file:
                json.dump(plan, plan_file, sort_keys=True)
        except Exception as cleanup_error:
            cleanup_errors.append(cleanup_error)
        cleanup_paths = [plan["staging_root"], backup_path]
        for cleanup_path in cleanup_paths:
            try:
                _remove_canonical_tree(cleanup_path, "cleanup")
            except Exception as cleanup_error:
                cleanup_errors.append(cleanup_error)
        for cleanup_file, kind in (
            (plan_path, "plan"),
            (plan["helper_path"], "helper"),
        ):
            try:
                _remove_canonical_file(cleanup_file, kind)
            except Exception as cleanup_error:
                cleanup_errors.append(cleanup_error)
        if cleanup_errors:
            xbmc.log(
                "Jacktook update succeeded but temporary file cleanup was incomplete",
                xbmc.LOGWARNING,
            )
        xbmcgui.Dialog().notification("Jacktook Updater", "Update complete.")
        xbmc.log("Jacktook update completed", xbmc.LOGINFO)
        # Land on the add-on's main menu. ActivateWindow is a no-op while
        # MyVideoNav is already the active window (the common case: the addon
        # settings dialog closes back onto it after the disable/enable swap),
        # so the active container is navigated in that case and the window is
        # opened otherwise.
        if xbmc.getCondVisibility("Window.IsActive(10025)"):
            xbmc.executebuiltin(f'Container.Update("plugin://{ADDON_ID}/",replace)')
        else:
            xbmc.executebuiltin(f'ActivateWindow(10025,"plugin://{ADDON_ID}/",return)')
        return True
    except Exception as error:
        rollback_complete = False
        rollback_errors = []
        if backed_up:
            phase = f"rollback_after_{phase}"
            rollback_complete, rollback_errors = _restore_previous_version(
                plan, addon_id, current_path, backup_path
            )
        else:
            try:
                _set_enabled(addon_id, original_enabled)
                _wait_for(
                    addon_id,
                    lambda details: (
                        details.get("enabled") is original_enabled
                        and details.get("version") == plan["source_version"]
                    ),
                    DISABLE_TIMEOUT_SECONDS,
                )
                rollback_complete = True
            except Exception as restore_error:
                rollback_errors.append(restore_error)
        with contextlib.suppress(OSError):
            _save_failure(
                plan_path,
                plan,
                phase,
                error,
                rollback_complete,
                rollback_errors,
            )
        xbmc.log(
            f"Jacktook update failed during {phase}: {type(error).__name__}: {error}",
            xbmc.LOGERROR,
        )
        message = "Update failed and the previous version was restored and confirmed."
        if not rollback_complete:
            message = "Update failed and rollback is incomplete. Check the Kodi log."
        xbmcgui.Dialog().ok("Jacktook Updater", message)
        return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("An update plan path is required")
    apply_update(sys.argv[1])
