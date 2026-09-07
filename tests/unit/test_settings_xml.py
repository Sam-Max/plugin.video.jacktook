import xml.etree.ElementTree as ET
from pathlib import Path

SETTINGS_XML = Path(__file__).resolve().parents[2] / "resources" / "settings.xml"
ENGLISH_STRINGS = (
    Path(__file__).resolve().parents[2] / "resources" / "language" / "English" / "strings.po"
)


def _english_label(label_id):
    entry = f'msgctxt "#{label_id}"\n'
    start = ENGLISH_STRINGS.read_text().index(entry)
    lines = ENGLISH_STRINGS.read_text()[start:].splitlines()
    return lines[1].removeprefix('msgid "').removesuffix('"')


def test_settings_xml_parses():
    ET.parse(SETTINGS_XML)


def test_stremio_enable_does_not_control_settings_visibility():
    tree = ET.parse(SETTINGS_XML)

    conditions = tree.findall(".//condition[@setting='stremio_enabled']")

    assert conditions == []


def test_hidden_stremio_subtitle_settings_have_persistence_controls():
    tree = ET.parse(SETTINGS_XML)

    addons_setting = tree.find(".//setting[@id='stremio_subtitle_addons']")
    migrated_setting = tree.find(".//setting[@id='stremio_subtitle_addons_migrated']")

    assert addons_setting.find("control[@type='edit'][@format='string']") is not None
    assert migrated_setting.find("control[@type='toggle']") is not None


def test_subtitle_automation_exposes_one_visible_setting_and_keeps_legacy_values_hidden():
    tree = ET.parse(SETTINGS_XML)

    automation = tree.find(".//setting[@id='subtitle_automation']")
    legacy_selection = tree.find(".//setting[@id='auto_subtitle_selection']")
    legacy_download = tree.find(".//setting[@id='auto_subtitle_download']")

    assert automation is not None
    assert automation.get("label") == "30878"
    assert legacy_selection.findtext("visible") == "false"
    assert legacy_download.findtext("visible") == "false"


def test_yamtrack_settings_default_disabled_and_hide_token_input():
    tree = ET.parse(SETTINGS_XML)

    enabled = tree.find(".//setting[@id='yamtrack_enabled']")
    token = tree.find(".//setting[@id='yamtrack_token']")

    assert enabled.findtext("default") == "false"
    assert token.find("control[@type='edit']/hidden").text == "true"


def test_simkl_settings_default_disabled_and_persist_hidden_auth():
    tree = ET.parse(SETTINGS_XML)

    enabled = tree.find(".//setting[@id='simkl_enabled']")
    client_id = tree.find(".//setting[@id='simkl_client_id']")
    token = tree.find(".//setting[@id='simkl_access_token']")
    authenticated = tree.find(".//setting[@id='simkl_authenticated']")

    assert enabled.findtext("default") == "false"
    assert client_id.find("control[@type='edit']") is not None
    assert token.findtext("visible") == "false"
    assert token.find("control[@type='edit']/hidden").text == "true"
    assert authenticated.findtext("default") == "false"


def test_simkl_client_id_is_an_empty_optional_advanced_override():
    tree = ET.parse(SETTINGS_XML)

    client_id = tree.find(".//setting[@id='simkl_client_id']")

    assert client_id.findtext("default", "") == ""
    assert client_id.get("label") == "90973"
    assert client_id.get("help") == "90974"


def test_nuvio_settings_hide_session_values_and_expose_only_auth_actions():
    tree = ET.parse(SETTINGS_XML)

    enabled = tree.find(".//setting[@id='nuvio_enabled']")
    auth = tree.find(".//setting[@id='nuvio_auth']")
    logout = tree.find(".//setting[@id='nuvio_logout']")
    hidden = [
        tree.find(f".//setting[@id='{setting_id}']")
        for setting_id in (
            "nuvio_access_token",
            "nuvio_refresh_token",
            "nuvio_expires_at",
            "nuvio_authenticated",
            "nuvio_profile_id",
        )
    ]

    assert enabled.findtext("default") == "false"
    assert auth.findtext("data").endswith("action=nuvio_auth)")
    assert logout.findtext("data").endswith("action=nuvio_logout)")
    assert all(setting.findtext("visible") == "false" for setting in hidden)
    assert all(
        setting.find("control[@type='edit']/hidden").text == "true"
        for setting in hidden
        if setting.get("type") == "string"
    )


def test_nuvio_settings_follow_stremio_in_sources_category():
    tree = ET.parse(SETTINGS_XML)

    sources = tree.find(".//category[@id='sources_category']")
    groups = sources.findall("group")
    nuvio_group = sources.find("group[@id='nuvio']")

    assert tree.findall(".//group[@id='nuvio']") == [nuvio_group]
    assert groups[groups.index(nuvio_group) - 1].get("id") == "stremio_general"


def test_nuvio_settings_describe_qr_account_connection():
    tree = ET.parse(SETTINGS_XML)

    nuvio_group = tree.find(".//group[@id='nuvio']")
    enabled = tree.find(".//setting[@id='nuvio_enabled']")
    auth = tree.find(".//setting[@id='nuvio_auth']")

    assert (nuvio_group.get("label"), _english_label(nuvio_group.get("label"))) == (
        "91002",
        "Nuvio: Account",
    )
    assert (enabled.get("label"), _english_label(enabled.get("label"))) == ("91003", "Enable")
    assert (auth.get("label"), _english_label(auth.get("label"))) == (
        "91005",
        "Connect Nuvio with QR Code",
    )
    assert _english_label(auth.get("help")) == (
        "Scan the QR code with a signed-in Nuvio device, then select the profile "
        "that receives watch-progress updates."
    )


def test_nuvio_strings_are_defined_in_every_supported_catalogue():
    language_root = ENGLISH_STRINGS.parent.parent

    for catalogue in language_root.glob("*/strings.po"):
        content = catalogue.read_text()
        for string_id in range(91002, 91018):
            assert content.count(f'msgctxt "#{string_id}"') == 1, catalogue
