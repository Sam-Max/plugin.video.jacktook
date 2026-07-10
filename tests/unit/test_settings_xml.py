import xml.etree.ElementTree as ET
from pathlib import Path

SETTINGS_XML = Path(__file__).resolve().parents[2] / "resources" / "settings.xml"


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
