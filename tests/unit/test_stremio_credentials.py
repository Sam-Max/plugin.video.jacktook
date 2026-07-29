from unittest.mock import MagicMock

from lib.api.stremio.addon_manager import AddonManager, build_legacy_addon_instance_key
from lib.clients.stremio import authentication
from lib.clients.stremio.protocol import safe_cache_key


def _addon_item(manifest, url="https://example.com/config/manifest.json"):
    return {"manifest": manifest, "transportUrl": url, "transportName": "custom"}


def test_safe_cache_identity_never_contains_token_bearing_url():
    locator = "https://example.com/private-value/catalog"
    key = safe_cache_key("stremio_resource", {"url": locator, "resource": "catalog"})

    assert key.startswith("stremio_resource:")
    assert locator not in key
    assert "private-value" not in key


def test_redacted_addon_key_resolves_legacy_persisted_key():
    manager = AddonManager(
        [_addon_item({"id": "example.addon", "name": "Example", "resources": []})]
    )
    addon = manager.addons[0]

    assert "https://" not in addon.key()
    assert manager.get_addon_by_key(build_legacy_addon_instance_key(addon)) is addon


def test_successful_login_persists_auth_key_and_clears_password(monkeypatch):
    writes = {}
    fake_cache = MagicMock()
    fake_cache.get.return_value = []

    class FakeStremio:
        authKey = None

        def login(self, email, password):
            self.authKey = "session-value"

        def get_my_addons(self):
            return []

    monkeypatch.setattr(authentication, "Stremio", FakeStremio)
    monkeypatch.setattr(authentication, "cache", fake_cache)
    monkeypatch.setattr(authentication, "set_setting", writes.__setitem__)

    authentication.log_in("person@example.com", "password-value", MagicMock())

    assert writes["stremio_auth_key"] == "session-value"
    assert writes["stremio_pass"] == ""
    assert writes["stremio_loggedin"] == "true"


def test_account_update_migrates_password_to_auth_key(monkeypatch):
    settings = {
        "stremio_auth_key": "",
        "stremio_email": "person@example.com",
        "stremio_pass": "legacy-password",
    }
    writes = {}
    fake_cache = MagicMock()
    fake_cache.get.return_value = []

    class FakeStremio:
        def __init__(self, auth_key):
            self.authKey = auth_key

        def login(self, email, password):
            self.authKey = "migrated-session"

        def get_my_addons(self):
            return []

    dialog = MagicMock()
    dialog.yesno.return_value = True
    monkeypatch.setattr(authentication.xbmcgui, "Dialog", lambda: dialog)
    monkeypatch.setattr(authentication, "Stremio", FakeStremio)
    monkeypatch.setattr(authentication, "get_setting", settings.get)
    monkeypatch.setattr(authentication, "set_setting", writes.__setitem__)
    monkeypatch.setattr(authentication, "cache", fake_cache)

    authentication.stremio_update({})

    assert writes == {"stremio_auth_key": "migrated-session", "stremio_pass": ""}
