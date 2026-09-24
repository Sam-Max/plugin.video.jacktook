import contextlib
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import xml.etree.ElementTree as ET
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

import requests

from lib.utils.kodi.utils import (
    ADDON_PATH,
    ADDON_VERSION,
    close_all_dialog,
    close_busy_dialog,
    dialog_ok,
    dialog_text,
    dialogyesno,
    execute_builtin,
    kodilog,
    notification,
    show_busy_dialog,
    translate_path,
    translation,
)

# =========================
# Constants
# =========================
ADDON_ID = "plugin.video.jacktook"
ADDON_NAME = "Jacktook"
HEADING = f"{ADDON_NAME} Updater"

CHANGELOG_PATH = f"special://home/addons/{ADDON_ID}/CHANGELOG.md"

BASE_REPO_URL = "https://github.com/Sam-Max/repository.jacktook/raw/main/packages"

VERSION_FILE = f"{BASE_REPO_URL}/jacktook_version"
CHANGELOG_FILE = f"{BASE_REPO_URL}/jacktook_changelog"

PACKAGE_REPO_PATH = f"repo/zips/{ADDON_ID}"
PACKAGE_RAW_URL = (
    f"https://raw.githubusercontent.com/Sam-Max/repository.jacktook/main/{PACKAGE_REPO_PATH}"
)
PACKAGE_API_URL = (
    f"https://api.github.com/repos/Sam-Max/repository.jacktook/contents/{PACKAGE_REPO_PATH}"
)

# Connect/read timeout (seconds) for every updater request.
HTTP_TIMEOUT = (10, 30)
DOWNLOAD_CHUNK_SIZE = 64 * 1024
MAX_METADATA_BYTES = 64 * 1024
MAX_COMPRESSED_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_FILES = 5000
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
WINDOWS_RESERVED_NAMES = {
    "aux",
    "con",
    "nul",
    "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}

UPDATE_ACTION_ASK = 0
UPDATE_ACTION_NOTIFY = 1
UPDATE_ACTION_NONE = 2


# =========================
# Helpers
# =========================
def http_get(url, stream=False):
    """Make a GET request and return text or raw stream."""
    try:
        resp = requests.get(url, stream=stream, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        return resp.text if not stream else resp.raw
    except requests.RequestException as e:
        notification(f"HTTP Error: {e}")
        return None


def get_versions():
    """Return (current_version, online_version) or (None, None) on failure.

    UI-free on purpose: the caller owns any busy dialog so the automatic
    background check never pops a modal window.
    """
    online_version = http_get(VERSION_FILE)
    if not online_version:
        return None, None
    return ADDON_VERSION, online_version.strip()


def _version_parts(version):
    """Return numeric release segments and natural-order prerelease tokens."""
    match = re.fullmatch(
        r"\s*[vV]?(\d+(?:\.\d+)*)(?:[-.]?([A-Za-z][0-9A-Za-z.-]*))?\s*",
        str(version),
    )
    if not match:
        raise ValueError(f"Unparseable version: {version}")
    release = tuple(int(part) for part in match.group(1).split("."))
    prerelease = match.group(2)
    tokens = ()
    if prerelease:
        tokens = tuple(
            (0, int(token)) if token.isdigit() else (1, token.casefold())
            for token in re.findall(r"\d+|[A-Za-z]+", prerelease)
        )
    return release, tokens


def version_less_than(v1, v2):
    """Return True if v1 < v2 using numeric segment comparison.

    Segments compare as zero-padded integers, so "1.9" < "1.10" and "1.0"
    equals "1.0.0" (an update must never be offered between equivalent
    formats). A pre-release ("1.0.0-beta") sorts before its final release.
    Unparseable input falls back to string comparison.
    """
    try:
        release1, prerelease1 = _version_parts(v1)
        release2, prerelease2 = _version_parts(v2)
    except (TypeError, ValueError):
        return v1 < v2
    width = max(len(release1), len(release2))
    release1 += (0,) * (width - len(release1))
    release2 += (0,) * (width - len(release2))
    if release1 != release2:
        return release1 < release2
    if prerelease1 != prerelease2:
        if not prerelease1:
            return False
        if not prerelease2:
            return True
        return prerelease1 < prerelease2
    return False


def get_changes(online_version=None):
    """Display changelog (online if version passed, else local)."""
    if online_version:
        changelog = http_get(CHANGELOG_FILE)
        if changelog:
            dialog_text(translation(90592) % online_version, str(changelog))
    else:
        dialog_text(translation(90577), file=CHANGELOG_PATH)


def _package_name(version):
    """Return the release filename after rejecting path-like versions."""
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*(?:[-+][0-9A-Za-z.-]+)?", str(version)):
        raise ValueError("Invalid release version")
    return f"{ADDON_ID}-{version}.zip"


def _read_bounded_response(response, maximum):
    """Read a streamed response while enforcing an absolute byte limit."""
    data = bytearray()
    for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
        if not chunk:
            continue
        if len(data) + len(chunk) > maximum:
            raise ValueError("Response exceeds size limit")
        data.extend(chunk)
    return bytes(data)


def _fetch_package_metadata(version):
    """Fetch repository-bound size and Git object identity for one package."""
    package_name = _package_name(version)
    url = f"{PACKAGE_API_URL}/{package_name}?ref=main"
    with requests.get(url, stream=True, timeout=HTTP_TIMEOUT) as response:
        response.raise_for_status()
        data = _read_bounded_response(response, MAX_METADATA_BYTES)
    metadata = json.loads(data.decode("utf-8"))
    if not isinstance(metadata, dict) or metadata.get("type") != "file":
        raise ValueError("GitHub metadata does not describe a file")
    if metadata.get("name") != package_name:
        raise ValueError("GitHub metadata filename mismatch")
    size = metadata.get("size")
    sha = metadata.get("sha")
    if not isinstance(size, int) or not 0 < size <= MAX_COMPRESSED_BYTES:
        raise ValueError("Invalid package size in GitHub metadata")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Invalid Git blob SHA in GitHub metadata")
    return {"name": package_name, "size": size, "sha": sha}


def _download_package(version, metadata, destination):
    """Stream an exact-size package to disk and verify its Git blob SHA."""
    url = f"{PACKAGE_RAW_URL}/{metadata['name']}"
    size = metadata["size"]
    digest = hashlib.sha1()
    digest.update(f"blob {size}\0".encode())
    written = 0
    try:
        with requests.get(
            url,
            stream=True,
            timeout=HTTP_TIMEOUT,
            headers={"Accept-Encoding": "identity"},
        ) as response:
            response.raise_for_status()
            content_length = response.headers.get("Content-Length")
            if content_length is not None and int(content_length) != size:
                raise ValueError("Package Content-Length does not match repository metadata")
            with open(destination, "xb") as package_file:
                for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > size or written > MAX_COMPRESSED_BYTES:
                        raise ValueError("Package exceeds declared size")
                    package_file.write(chunk)
                    digest.update(chunk)
        if written != size:
            raise ValueError("Package size does not match repository metadata")
        if digest.hexdigest() != metadata["sha"]:
            raise ValueError("Package Git blob SHA mismatch")
    except Exception:
        with contextlib.suppress(OSError):
            os.remove(destination)
        raise


def _validated_archive_entries(package_path, expected_version):
    """Validate archive structure, limits, entry types, CRCs, and addon identity."""
    try:
        archive = ZipFile(package_path)
    except BadZipFile as exc:
        raise ValueError("Invalid ZIP package") from exc

    with archive:
        entries = archive.infolist()
        if len(entries) > MAX_ARCHIVE_FILES:
            raise ValueError("ZIP contains too many entries")
        seen = set()
        file_count = 0
        total_size = 0
        total_compressed_size = 0
        for entry in entries:
            name = entry.filename
            if not name or "\\" in name or "\x00" in name:
                raise ValueError("ZIP contains an unsafe path")
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("ZIP contains an unsafe path")
            if not path.parts or path.parts[0] != ADDON_ID:
                raise ValueError("ZIP must have exactly one addon top-level directory")
            if any(":" in part or part.endswith((".", " ")) for part in path.parts):
                raise ValueError("ZIP contains a platform-unsafe path")
            if any(
                part.split(".", 1)[0].casefold() in WINDOWS_RESERVED_NAMES for part in path.parts
            ):
                raise ValueError("ZIP contains a Windows reserved device path")
            collision_key = "/".join(path.parts).rstrip("/").casefold()
            if collision_key in seen:
                raise ValueError("ZIP contains duplicate paths")
            seen.add(collision_key)
            if entry.flag_bits & 0x1:
                raise ValueError("Encrypted ZIP entries are not allowed")
            mode = entry.external_attr >> 16
            file_type = stat.S_IFMT(mode)
            is_directory = entry.is_dir()
            if file_type and not (
                (is_directory and stat.S_ISDIR(mode)) or (not is_directory and stat.S_ISREG(mode))
            ):
                raise ValueError("ZIP contains a symlink or special entry")
            if is_directory:
                continue
            file_count += 1
            if entry.file_size > MAX_FILE_BYTES:
                raise ValueError("ZIP entry exceeds the per-file size limit")
            total_size += entry.file_size
            total_compressed_size += entry.compress_size
            if total_size > MAX_UNCOMPRESSED_BYTES:
                raise ValueError("ZIP exceeds the uncompressed size limit")
            if entry.file_size and not entry.compress_size:
                raise ValueError("ZIP entry has an invalid compression size")
            if (
                entry.file_size > 1024 * 1024
                and entry.file_size / entry.compress_size > MAX_COMPRESSION_RATIO
            ):
                raise ValueError("ZIP entry has a suspicious compression ratio")
        if total_size and (
            not total_compressed_size or total_size / total_compressed_size > MAX_COMPRESSION_RATIO
        ):
            raise ValueError("ZIP has a suspicious aggregate compression ratio")
        if not file_count:
            raise ValueError("ZIP contains no files")
        addon_xml_name = f"{ADDON_ID}/addon.xml"
        if addon_xml_name.casefold() not in seen:
            raise ValueError("ZIP is missing addon.xml")
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC validation failed")
        try:
            root = ET.fromstring(archive.read(addon_xml_name))
        except (KeyError, ET.ParseError) as exc:
            raise ValueError("Invalid addon.xml") from exc
        if root.tag != "addon" or root.get("id") != ADDON_ID:
            raise ValueError("Package addon id mismatch")
        if root.get("version") != str(expected_version):
            raise ValueError("Package version mismatch")
        return entries


def _extract_validated_package(package_path, destination, entries):
    """Manually extract previously validated regular files without following links."""
    destination = os.path.realpath(destination)
    os.makedirs(destination, mode=0o700)
    with ZipFile(package_path) as archive:
        for entry in entries:
            relative = PurePosixPath(entry.filename)
            target = os.path.realpath(os.path.join(destination, *relative.parts))
            if os.path.commonpath((destination, target)) != destination:
                raise ValueError("ZIP extraction escaped the staging directory")
            if entry.is_dir():
                os.makedirs(target, mode=0o700, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), mode=0o700, exist_ok=True)
            with archive.open(entry, "r") as source, open(target, "xb") as output:
                shutil.copyfileobj(source, output, DOWNLOAD_CHUNK_SIZE)


def _write_update_plan(staging_root, staged_addon, version, metadata, transaction_id):
    """Copy the standalone helper and write its local handoff plan."""
    if not re.fullmatch(r"[0-9a-f]{32}", transaction_id):
        raise ValueError("Invalid update transaction id")
    temp_dir = translate_path("special://temp")
    os.makedirs(temp_dir, exist_ok=True)
    artifact_prefix = f"{ADDON_ID}-update-{transaction_id}"
    helper_path = os.path.join(temp_dir, f"{artifact_prefix}.py")
    plan_path = os.path.join(temp_dir, f"{artifact_prefix}.json")
    backup_path = os.path.join(
        os.path.dirname(os.path.abspath(ADDON_PATH)),
        f".{ADDON_ID}-backup-{transaction_id}",
    )
    plan = {
        "addon_id": ADDON_ID,
        "transaction_id": transaction_id,
        "current_path": os.path.abspath(ADDON_PATH),
        "staged_path": os.path.abspath(staged_addon),
        "staging_root": os.path.abspath(staging_root),
        "backup_path": backup_path,
        "target_version": str(version),
        "source_version": str(ADDON_VERSION),
        "git_blob_sha": metadata["sha"],
        "helper_path": helper_path,
        "original_enabled": True,
        "status": "staged",
    }
    helper_created = False
    plan_created = False
    try:
        with open(os.path.join(ADDON_PATH, "lib", "update_helper.py"), "rb") as source:
            with open(helper_path, "xb") as helper_file:
                helper_created = True
                shutil.copyfileobj(source, helper_file)
        with open(plan_path, "x", encoding="utf-8") as plan_file:
            plan_created = True
            json.dump(plan, plan_file, sort_keys=True)
    except Exception:
        for path, created in (
            (helper_path, helper_created),
            (plan_path, plan_created),
        ):
            if created:
                with contextlib.suppress(OSError):
                    os.remove(path)
        raise
    return helper_path, plan_path


# =========================
# Entry Point
# =========================
def updates_check_addon(automatic=False):
    kodilog("Checking for updates...")
    action = None
    if automatic:
        from lib.utils.kodi.settings import get_update_action

        action = get_update_action()
        if action == UPDATE_ACTION_NONE:
            kodilog("Automatic update check disabled by settings, skipping.")
            return

    if automatic:
        current_version, online_version = get_versions()
    else:
        show_busy_dialog()
        current_version, online_version = get_versions()
        close_busy_dialog()

    if not current_version or not online_version:
        kodilog("Failed to fetch versions for update check.")
        if not automatic:
            dialog_ok(heading=HEADING, line1=translation(90578))
        return

    kodilog(f"Update check - Current: {current_version}, Online: {online_version}")

    if version_less_than(current_version, online_version):
        kodilog("Newer version available.")
        msg = translation(90580) % (current_version, online_version)
        if not automatic or action == UPDATE_ACTION_ASK:
            if not dialogyesno(
                header=HEADING,
                text=msg + translation(90581),
            ):
                return
            update_addon(online_version)
        elif action == UPDATE_ACTION_NOTIFY:
            notification(
                heading=HEADING,
                message=translation(90582) % online_version,
            )
        return

    if version_less_than(online_version, current_version):
        kodilog("Installed version is newer than the repository version.")
        if not automatic:
            notification(heading=HEADING, message=translation(90964))
        return

    kodilog("No update available.")
    if not automatic:
        notification(heading=HEADING, message=translation(90579))


def update_addon(new_version):
    """Download, verify, and stage an update for an out-of-process handoff.

    The Git blob SHA binds the downloaded bytes to the object reported by the
    repository API. It does not protect against compromise of the repository's
    publishing account or of GitHub itself.
    """
    kodilog(f"Staging update to version: {new_version}")
    close_all_dialog()
    show_busy_dialog()
    staging_root = None
    try:
        addon_path = os.path.abspath(ADDON_PATH)
        addon_parent = os.path.dirname(addon_path)
        if not os.path.isdir(addon_path) or os.path.islink(addon_path):
            raise ValueError("Installed add-on path is not a regular directory")
        transaction_id = secrets.token_hex(16)
        staging_candidate = os.path.join(addon_parent, f".{ADDON_ID}-update-{transaction_id}")
        os.mkdir(staging_candidate, mode=0o700)
        staging_root = staging_candidate
        metadata = _fetch_package_metadata(new_version)
        package_path = os.path.join(staging_root, metadata["name"])
        _download_package(new_version, metadata, package_path)
        entries = _validated_archive_entries(package_path, new_version)
        payload_root = os.path.join(staging_root, "payload")
        _extract_validated_package(package_path, payload_root, entries)
        staged_addon = os.path.join(payload_root, ADDON_ID)
        helper_path, plan_path = _write_update_plan(
            staging_root,
            staged_addon,
            new_version,
            metadata,
            transaction_id,
        )
    except Exception as error:
        kodilog(f"Unable to stage update: {type(error).__name__}: {error}")
        if staging_root:
            with contextlib.suppress(OSError):
                shutil.rmtree(staging_root)
        dialog_ok(
            heading=HEADING,
            line1="Unable to safely stage the update. Please install manually.",
        )
        return False
    finally:
        close_busy_dialog()

    try:
        execute_builtin(f'RunScript("{helper_path}","{plan_path}")')
    except Exception as error:
        kodilog(f"Unable to launch update helper: {type(error).__name__}: {error}")
        for path in (helper_path, plan_path):
            with contextlib.suppress(OSError):
                os.remove(path)
        with contextlib.suppress(OSError):
            shutil.rmtree(staging_root)
        dialog_ok(heading=HEADING, line1="Unable to launch the staged update.")
        return False
    notification(
        heading=HEADING,
        message="Update verified and handed off. Jacktook will restart after replacement.",
    )
    kodilog("Verified update handed off to standalone helper.")
    return True
