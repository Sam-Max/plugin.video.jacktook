from lib.services.debrid.auth import parse_positive_int, resolve_device_verification_url


def test_prefers_direct_verification_url_when_present():
    response = {
        "device_code": "DEVICE",
        "user_code": "USER",
        "verification_url": "https://real-debrid.com/device",
        "direct_verification_url": "https://real-debrid.com/device?user_code=USER",
    }

    assert (
        resolve_device_verification_url(response) == "https://real-debrid.com/device?user_code=USER"
    )


def test_falls_back_to_the_documented_verification_url():
    response = {
        "device_code": "DEVICE",
        "user_code": "USER",
        "verification_url": "https://real-debrid.com/device",
    }

    assert resolve_device_verification_url(response) == "https://real-debrid.com/device"


def test_ignores_blank_and_non_string_candidates():
    response = {
        "verification_url": "https://real-debrid.com/device",
        "direct_verification_url": "",
    }

    assert resolve_device_verification_url(response) == "https://real-debrid.com/device"


def test_returns_empty_string_when_no_url_is_offered():
    assert resolve_device_verification_url({"device_code": "DEVICE"}) == ""


def test_parse_positive_int_keeps_valid_values():
    assert parse_positive_int(30, 5) == 30
    assert parse_positive_int("30", 5) == 30


def test_parse_positive_int_falls_back_on_bad_input():
    assert parse_positive_int(None, 5) == 5
    assert parse_positive_int("", 5) == 5
    assert parse_positive_int("not-a-number", 900) == 900
    assert parse_positive_int(0, 5) == 5
    assert parse_positive_int(-3, 5) == 5
