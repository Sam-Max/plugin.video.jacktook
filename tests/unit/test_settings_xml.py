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


def test_addon_version_setting_is_readonly_in_general_category():
    tree = ET.parse(SETTINGS_XML)

    general = tree.find(".//category[@id='general_category']")
    about_group = general.find("group[@id='about']")
    version = tree.find(".//setting[@id='addon_version']")

    assert about_group is not None
    assert version is not None
    assert version.findtext("enable") == "false"
    assert version.find("control[@type='edit'][@format='string']") is not None
    assert _english_label(about_group.get("label")) == "About"
    assert _english_label(version.get("label")) == "Version"


def test_about_strings_are_defined_in_every_supported_catalogue():
    language_root = ENGLISH_STRINGS.parent.parent

    for catalogue in language_root.glob("*/strings.po"):
        content = catalogue.read_text()
        for string_id in (91030, 91031):
            assert content.count(f'msgctxt "#{string_id}"') == 1, catalogue
