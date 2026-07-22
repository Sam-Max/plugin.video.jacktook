import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


SOURCE_SELECT_XML = (
    Path(__file__).resolve().parents[2]
    / "resources"
    / "skins"
    / "Default"
    / "1080i"
    / "source_select.xml"
)


def _status_control_bounds(layout, property_name):
    status_group = next(
        group
        for group in layout.findall(".//control[@type='group']")
        if group.findtext("top") == "105"
    )
    control = next(
        control
        for control in status_group.findall("control[@type='label']")
        if property_name in (control.findtext("label") or "")
    )
    return int(control.findtext("left")), int(control.findtext("width"))


def _pack_badge_bounds(layout):
    status_group = next(
        group
        for group in layout.findall(".//control[@type='group']")
        if group.findtext("top") == "105"
    )
    control = next(
        control
        for control in status_group.findall("control[@type='label']")
        if control.findtext("label") == "[B]PACK[/B]"
    )
    return int(control.findtext("left")), int(control.findtext("width"))


@pytest.mark.parametrize("layout_name", ("itemlayout", "focusedlayout"))
def test_source_status_row_allocates_non_overlapping_space(layout_name):
    source_list = ET.parse(SOURCE_SELECT_XML).find(".//control[@id='1000']")
    layout = source_list.find(layout_name)

    seeders_left, seeders_width = _status_control_bounds(layout, "Property(seeders)")
    pack_left, pack_width = _pack_badge_bounds(layout)
    status_left, status_width = _status_control_bounds(layout, "Property(status)")

    assert seeders_left + seeders_width <= pack_left
    assert pack_left + pack_width <= status_left
    assert status_left + status_width <= 1250
