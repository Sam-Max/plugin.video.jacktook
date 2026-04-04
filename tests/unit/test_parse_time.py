from datetime import datetime

from lib.utils.general.utils import parse_time


def test_parse_time_accepts_english_rfc822_style_timestamp():
    parsed = parse_time(("Title", {"timestamp": "Fri, 03 Apr 2026 03:38 AM"}))

    assert parsed == datetime(2026, 4, 3, 3, 38)


def test_parse_time_accepts_spanish_localized_timestamp():
    parsed = parse_time(("Title", {"timestamp": "vie, 03 abr 2026 05:18 p. m."}))

    assert parsed == datetime(2026, 4, 3, 17, 18)
