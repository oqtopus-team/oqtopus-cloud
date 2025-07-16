import pytest
from pydantic import ValidationError

from oqtopus_cloud.common.available_devices import parse_available_devices_string

def test_parse_available_devices_string():
    result = parse_available_devices_string('["SC", "SVSim", "Kawasaki"]')
    assert result == ["SC", "SVSim", "Kawasaki"]


def test_parse_available_devices_string_none():
    result = parse_available_devices_string(None)
    assert result is None


def test_parse_available_devices_string_all_devices():
    result = parse_available_devices_string('*')
    assert result == '*'


def test_parse_available_devices_string_invalid_json_format():
    with pytest.raises(ValidationError):
        parse_available_devices_string("invalid json")


def test_parse_available_devices_string_invalid_content_type():
    with pytest.raises(ValidationError):
        parse_available_devices_string('["SVSim", 1234]')