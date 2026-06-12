from pathlib import Path
import xml.etree.ElementTree as ET


SETTINGS_XML = Path(__file__).resolve().parents[2] / "resources" / "settings.xml"


def test_settings_xml_parses():
    ET.parse(SETTINGS_XML)


def test_stremio_enable_does_not_control_settings_visibility():
    tree = ET.parse(SETTINGS_XML)

    conditions = tree.findall(".//condition[@setting='stremio_enabled']")

    assert conditions == []
