import json
import os
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET

import requests
import xbmcgui

from lib.clients.stremio.constants import (
    STREMIO_ADDONS_CATALOGS_KEY,
    STREMIO_ADDONS_KEY,
    STREMIO_TV_ADDONS_KEY,
    STREMIO_USER_ADDONS,
    decode_selected_ids,
    encode_selected_ids,
)
from lib.api.stremio.addon_manager import build_addon_instance_key
from lib.db.cached import cache
from lib.db.pickle_db import PickleDatabase
from lib.utils.general.utils import (
    clear_all_cache,
    clear_debrid_cache,
    clear_mdblist_cache,
    clear_stremio_cache,
    clear_tmdb_cache,
    clear_trakt_db_cache,
)
from lib.utils.kodi.utils import (
    ADDON,
    ADDON_ID,
    ADDON_PATH,
    ADDON_PROFILE_PATH,
    ADDON_VERSION,
    dialog_ok,
    get_cached_setting_property,
    get_setting,
    notification,
    set_cached_setting_property,
    set_setting,
    translation,
    translatePath,
)


BACKUP_VERSION = 1
CUSTOM_ADDON_EXPIRY = timedelta(days=365 * 20)
SETTINGS_XML_PATH = os.path.join(ADDON_PATH, "resources", "settings.xml")
EXPORT_FILENAME_TEMPLATE = "jacktook-settings-backup-{timestamp}.json"
RESTORE_SOURCE_FILE = "file"
RESTORE_SOURCE_URL = "url"

CUSTOM_SELECTION_KEYS = {
    "stream": STREMIO_ADDONS_KEY,
    "catalog": STREMIO_ADDONS_CATALOGS_KEY,
    "tv": STREMIO_TV_ADDONS_KEY,
}

SENSITIVE_SETTING_IDS = {
    "real_debrid_token",
    "alldebrid_token",
    "debrider_token",
    "torbox_token",
    "premiumize_token",
    "easynews_password",
    "stremio_pass",
    "jackett_apikey",
    "prowlarr_apikey",
    "jackgram_token",
    "deepl_api_key",
    "fanart_client_key",
    "tmdb_api_key",
    "mdblist_api_key",
    "trakt_secret",
    "webdav_password",
}

IDENTITY_SETTING_IDS = {
    "stremio_email",
    "easynews_user",
    "webdav_username",
    "real_debrid_user",
    "alldebrid_user",
    "torbox_user",
    "trakt_user",
}

AUTH_STATE_SETTING_IDS = {
    "real_debid_authorized",
    "alldebrid_authorized",
    "debrider_authorized",
    "stremio_loggedin",
    "is_trakt_auth",
}

SCRUBBED_SETTING_IDS = (
    SENSITIVE_SETTING_IDS | IDENTITY_SETTING_IDS | AUTH_STATE_SETTING_IDS
)

EXTRA_DYNAMIC_SETTINGS = {
    "trakt_token": "",
    "trakt_refresh": "",
    "trakt_expires": "",
}

SENSITIVE_DYNAMIC_SETTING_IDS = set(EXTRA_DYNAMIC_SETTINGS)


def _stringify_setting_value(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _load_settings_schema(settings_xml_path=SETTINGS_XML_PATH):
    root = ET.parse(settings_xml_path).getroot()
    schema = {}
    for setting in root.findall(".//setting"):
        setting_id = setting.get("id")
        setting_type = setting.get("type")
        if not setting_id or setting_type == "action":
            continue
        default_node = setting.find("default")
        default_value = ""
        if default_node is not None:
            default_value = default_node.text or ""
        schema[setting_id] = {
            "type": setting_type or "string",
            "default": default_value,
        }
    return schema


def _setting_clear_value(setting_id, schema_entry):
    if setting_id in AUTH_STATE_SETTING_IDS:
        return "false"
    if setting_id == "trakt_user":
        return schema_entry.get("default") or "unknown_user"
    return schema_entry.get("default", "")


def _custom_addon_key(addon):
    return build_addon_instance_key(addon) or None


def _get_custom_stremio_addons(user_addons=None):
    user_addons = user_addons if user_addons is not None else (cache.get(STREMIO_USER_ADDONS) or [])
    custom_addons = []
    for addon in user_addons:
        if addon.get("transportName") != "custom":
            continue
        if not _custom_addon_key(addon):
            continue
        custom_addons.append(addon)
    return custom_addons


def _get_custom_selection_map(custom_addons):
    custom_keys = {
        addon_key for addon_key in (_custom_addon_key(addon) for addon in custom_addons) if addon_key
    }
    selections = {}
    for label, cache_key in CUSTOM_SELECTION_KEYS.items():
        selected_keys = decode_selected_ids(cache.get(cache_key))
        selections[label] = [key for key in selected_keys if key in custom_keys]
    return selections


def build_backup_payload(strip_sensitive=False, settings_xml_path=SETTINGS_XML_PATH):
    schema = _load_settings_schema(settings_xml_path)
    settings_payload = {}
    for setting_id in schema:
        if strip_sensitive and setting_id in SCRUBBED_SETTING_IDS:
            continue
        settings_payload[setting_id] = ADDON.getSetting(setting_id)

    cache_payload = {}
    if not strip_sensitive:
        custom_addons = _get_custom_stremio_addons()
        cache_payload["custom_stremio_addons"] = custom_addons
        cache_payload["custom_stremio_selections"] = _get_custom_selection_map(custom_addons)

    dynamic_settings_payload = {}
    for setting_id, default_value in EXTRA_DYNAMIC_SETTINGS.items():
        if strip_sensitive and setting_id in SENSITIVE_DYNAMIC_SETTING_IDS:
            continue
        dynamic_settings_payload[setting_id] = (
            get_cached_setting_property(setting_id) or default_value
        )

    return {
        "backup_version": BACKUP_VERSION,
        "addon_id": ADDON_ID,
        "addon_version": ADDON_VERSION,
        "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "strip_sensitive": bool(strip_sensitive),
        "custom_stremio_addons_included": not bool(strip_sensitive),
        "settings": settings_payload,
        "dynamic_settings": dynamic_settings_payload,
        "cache": cache_payload,
    }


def _ensure_backup_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("Backup payload must be an object")

    settings_payload = payload.get("settings")
    dynamic_settings_payload = payload.get("dynamic_settings", {})
    cache_payload = payload.get("cache", {})
    if not isinstance(settings_payload, dict):
        raise ValueError("Backup settings must be an object")
    if not isinstance(dynamic_settings_payload, dict):
        raise ValueError("Backup dynamic settings must be an object")
    if not isinstance(cache_payload, dict):
        raise ValueError("Backup cache must be an object")

    custom_addons = cache_payload.get("custom_stremio_addons", [])
    if not isinstance(custom_addons, list):
        raise ValueError("Custom Stremio addons must be a list")

    custom_selections = cache_payload.get("custom_stremio_selections", {})
    if not isinstance(custom_selections, dict):
        raise ValueError("Custom Stremio selections must be an object")

    return settings_payload, dynamic_settings_payload, cache_payload


def _normalize_custom_addons(custom_addons):
    normalized = []
    seen_keys = set()
    for addon in custom_addons:
        if not isinstance(addon, dict):
            continue
        addon = dict(addon)
        addon["transportName"] = "custom"
        addon_key = _custom_addon_key(addon)
        if not addon_key or addon_key in seen_keys:
            continue
        seen_keys.add(addon_key)
        normalized.append(addon)
    return normalized


def _filtered_custom_selection_map(cache_payload, custom_addons):
    custom_keys = {
        addon_key for addon_key in (_custom_addon_key(addon) for addon in custom_addons) if addon_key
    }
    raw_selections = cache_payload.get("custom_stremio_selections", {})
    filtered = {}
    for label in CUSTOM_SELECTION_KEYS:
        values = raw_selections.get(label, [])
        if not isinstance(values, list):
            values = []
        filtered[label] = [value for value in values if value in custom_keys]
    return filtered


def apply_backup_payload(payload, settings_xml_path=SETTINGS_XML_PATH):
    schema = _load_settings_schema(settings_xml_path)
    settings_payload, dynamic_settings_payload, cache_payload = _ensure_backup_payload(payload)
    strip_sensitive = bool(payload.get("strip_sensitive"))

    for setting_id, value in settings_payload.items():
        if setting_id not in schema:
            continue
        set_setting(setting_id, _stringify_setting_value(value))

    for setting_id, default_value in EXTRA_DYNAMIC_SETTINGS.items():
        if strip_sensitive:
            set_cached_setting_property(setting_id, default_value)
            continue
        set_cached_setting_property(
            setting_id,
            _stringify_setting_value(dynamic_settings_payload.get(setting_id, default_value)),
        )

    if strip_sensitive:
        for setting_id in SCRUBBED_SETTING_IDS:
            schema_entry = schema.get(setting_id)
            if not schema_entry:
                continue
            set_setting(setting_id, _setting_clear_value(setting_id, schema_entry))

    current_user_addons = list(cache.get(STREMIO_USER_ADDONS) or [])
    current_custom_addons = _get_custom_stremio_addons(current_user_addons)
    current_custom_keys = {
        addon_key
        for addon_key in (_custom_addon_key(addon) for addon in current_custom_addons)
        if addon_key
    }
    non_custom_addons = [
        addon for addon in current_user_addons if addon.get("transportName") != "custom"
    ]

    restored_custom_addons = []
    restored_selection_map = {label: [] for label in CUSTOM_SELECTION_KEYS}
    if not strip_sensitive:
        restored_custom_addons = _normalize_custom_addons(
            cache_payload.get("custom_stremio_addons", [])
        )
        restored_selection_map = _filtered_custom_selection_map(
            cache_payload, restored_custom_addons
        )

    cache.set(
        STREMIO_USER_ADDONS,
        non_custom_addons + restored_custom_addons,
        CUSTOM_ADDON_EXPIRY,
    )

    for label, cache_key in CUSTOM_SELECTION_KEYS.items():
        selected_keys = decode_selected_ids(cache.get(cache_key))
        selected_keys = [key for key in selected_keys if key not in current_custom_keys]
        for backup_key in restored_selection_map[label]:
            if backup_key not in selected_keys:
                selected_keys.append(backup_key)
        cache.set(cache_key, encode_selected_ids(selected_keys), CUSTOM_ADDON_EXPIRY)


def reset_all_settings(settings_xml_path=SETTINGS_XML_PATH):
    schema = _load_settings_schema(settings_xml_path)
    for setting_id, schema_entry in schema.items():
        set_setting(setting_id, _setting_clear_value(setting_id, schema_entry))

    for setting_id, default_value in EXTRA_DYNAMIC_SETTINGS.items():
        set_cached_setting_property(setting_id, default_value)

    current_user_addons = list(cache.get(STREMIO_USER_ADDONS) or [])
    current_custom_addons = _get_custom_stremio_addons(current_user_addons)
    current_custom_keys = {
        addon_key
        for addon_key in (_custom_addon_key(addon) for addon in current_custom_addons)
        if addon_key
    }
    non_custom_addons = [
        addon for addon in current_user_addons if addon.get("transportName") != "custom"
    ]
    cache.set(STREMIO_USER_ADDONS, non_custom_addons, CUSTOM_ADDON_EXPIRY)

    for cache_key in CUSTOM_SELECTION_KEYS.values():
        selected_keys = decode_selected_ids(cache.get(cache_key))
        selected_keys = [key for key in selected_keys if key not in current_custom_keys]
        cache.set(cache_key, encode_selected_ids(selected_keys), CUSTOM_ADDON_EXPIRY)


def _clear_factory_reset_database_state():
    pickle_db = PickleDatabase()
    for key in ("jt:watch", "jt:lth", "jt:lfh", "jt:lib"):
        pickle_db.set_key(key, {}, commit=False)
    for key in (
        "search_query",
        "search_catalog_query",
        "anime_query",
        "collection_search_query",
    ):
        pickle_db.set_key(key, "", commit=False)
    pickle_db.commit()


def factory_reset(settings_xml_path=SETTINGS_XML_PATH):
    reset_all_settings(settings_xml_path=settings_xml_path)
    clear_all_cache()
    clear_trakt_db_cache()
    clear_tmdb_cache()
    clear_stremio_cache()
    clear_debrid_cache()
    clear_mdblist_cache()
    cache.clear_list(key="multi")
    cache.clear_list(key="direct")
    _clear_factory_reset_database_state()


def _get_export_path():
    folder = xbmcgui.Dialog().browse(
        0,
        translation(90268),
        "files",
        "",
        False,
        False,
        "",
    )
    if not folder:
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return os.path.join(translatePath(folder), EXPORT_FILENAME_TEMPLATE.format(timestamp=timestamp))


def export_settings_backup(params=None):
    export_path = _get_export_path()
    if not export_path:
        return

    payload = build_backup_payload(bool(get_setting("settings_backup_strip_sensitive", False)))

    try:
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as backup_file:
            json.dump(payload, backup_file, indent=2, sort_keys=True)
        notification(translation(90265))
    except Exception:
        dialog_ok(translation(90267), translation(90273), export_path)


def _get_restore_path():
    restore_path = xbmcgui.Dialog().browse(
        1,
        translation(90269),
        "files",
        ".json",
        False,
        False,
        ADDON_PROFILE_PATH,
    )
    if not restore_path:
        notification(translation(90272))
        return None
    return translatePath(restore_path)


def _get_restore_source():
    selected_index = xbmcgui.Dialog().select(
        translation(90346),
        [translation(90347), translation(90348)],
    )
    if selected_index == 0:
        return RESTORE_SOURCE_FILE
    if selected_index == 1:
        return RESTORE_SOURCE_URL
    notification(translation(90277))
    return None


def _get_restore_url():
    restore_url = xbmcgui.Dialog().input(
        heading=translation(90349),
        type=xbmcgui.INPUT_ALPHANUM,
    )
    restore_url = (restore_url or "").strip()
    if not restore_url:
        notification(translation(90350))
        return None
    return restore_url


def _load_backup_payload_from_file(restore_path):
    with open(restore_path, encoding="utf-8") as backup_file:
        return json.load(backup_file)


def _load_backup_payload_from_url(restore_url):
    response = requests.get(restore_url, timeout=15)
    response.raise_for_status()
    return response.json()


def restore_settings_backup(params=None):
    restore_source = _get_restore_source()
    if not restore_source:
        return

    restore_target = (
        _get_restore_path() if restore_source == RESTORE_SOURCE_FILE else _get_restore_url()
    )
    if not restore_target:
        return

    try:
        confirmed = xbmcgui.Dialog().yesno(
            translation(90275),
            translation(90276),
        )
        if not confirmed:
            notification(translation(90277))
            return

        if restore_source == RESTORE_SOURCE_FILE:
            payload = _load_backup_payload_from_file(restore_target)
        else:
            payload = _load_backup_payload_from_url(restore_target)
        apply_backup_payload(payload)
        notification(translation(90266))
    except ValueError:
        dialog_ok(translation(90267), translation(90270))
    except requests.RequestException:
        dialog_ok(translation(90267), translation(90351), restore_target)
    except Exception:
        dialog_ok(translation(90267), translation(90274), restore_target)


def reset_all_settings_action(params=None):
    confirmed = xbmcgui.Dialog().yesno(
        translation(90278),
        translation(90279),
    )
    if not confirmed:
        notification(translation(90280))
        return

    try:
        reset_all_settings()
        notification(translation(90281))
    except Exception:
        dialog_ok(translation(90282), translation(90283))


def factory_reset_action(params=None):
    confirmed = xbmcgui.Dialog().yesno(
        translation(90285),
        translation(90286),
    )
    if not confirmed:
        notification(translation(90287))
        return

    try:
        factory_reset()
        notification(translation(90288))
    except Exception:
        dialog_ok(translation(90289), translation(90290))
