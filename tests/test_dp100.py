from unittest.mock import patch

import pytest
from pdudaemon.drivers.driver import FailedRequestException
from pdudaemon.drivers.dp100 import (
    DP100, build_frame, crc16_modbus, parse_frame,
)

# Preset 3, output off, 5000 mV, 1000 mA, OVP 30500 mV, OCP 5050 mA
PRESET = bytes([0x03, 0x00, 0x88, 0x13, 0xE8, 0x03,
                0x24, 0x77, 0xBA, 0x13])


def device_frame(function, data):
    frame = bytes([0xFA, function, 0, len(data)]) + bytes(data)
    crc = crc16_modbus(frame)
    report = frame + bytes([crc & 0xFF, crc >> 8])
    return list(report.ljust(64, b"\x00"))


class FakeHID:
    def __init__(self, replies):
        self.replies = list(replies)
        self.writes = []

    def __enter__(self):
        """Return the fake device."""
        return self

    def __exit__(self, *exc):
        """Close the fake device."""
        return False

    def write(self, buff):
        self.writes.append(bytes(buff))
        return len(buff)

    def read(self, max_length, timeout_ms=0):
        return self.replies.pop(0) if self.replies else []


@pytest.fixture
def pdu():
    return DP100("dummy", {})


def run(pdu, command, replies, port=1):
    dev = FakeHID(replies)
    with patch("pdudaemon.drivers.dp100.HIDDevice",
               return_value=dev) as mock_cls:
        pdu.port_interaction(command, port)
    return mock_cls, dev


class TestProtocol:
    def test_crc16_modbus_check_value(self):
        assert crc16_modbus(b"123456789") == 0x4B37

    def test_build_frame(self):
        assert build_frame(0x35, [0x80]) == bytes(
            [0xFB, 0x35, 0x00, 0x01, 0x80, 0xCE, 0x28])

    def test_parse_frame(self):
        assert parse_frame(device_frame(0x35, PRESET)) == (0x35, PRESET)

    def test_parse_frame_rejects_bad_crc(self):
        report = device_frame(0x35, PRESET)
        report[5] ^= 0xFF
        assert parse_frame(report) is None

    def test_parse_frame_rejects_host_frame(self):
        assert parse_frame(build_frame(0x35, [0x80])) is None


class TestDP100:
    def test_accepts(self):
        assert DP100.accepts("dp100") is True
        assert DP100.accepts("dp1000") is False

    def test_serial_setting(self):
        assert DP100("dummy", {"serial": "ABC"}).serial == "ABC"
        assert DP100("dummy", {}).serial is None

    @pytest.mark.parametrize("command,output", [("on", 1), ("off", 0)])
    def test_switch_output(self, pdu, command, output):
        mock_cls, dev = run(pdu, command, [
            device_frame(0x35, PRESET),
            device_frame(0x35, [0x01]),
        ])
        mock_cls.assert_called_once_with(0x2E3C, 0xAF01, None)
        read, write = dev.writes
        assert read == bytes([0]) + build_frame(0x35, [0x80]).ljust(64, b"\0")
        # Same preset and setpoints, write flag set, output changed
        expected = bytes([0x23, output]) + PRESET[2:]
        assert write == bytes([0]) + build_frame(0x35, expected).ljust(64, b"\0")

    def test_skips_unrelated_reports(self, pdu):
        _, dev = run(pdu, "on", [
            device_frame(0x30, bytes(16)),
            device_frame(0x35, PRESET),
            device_frame(0x35, [0x01]),
        ])
        assert len(dev.writes) == 2

    def test_refused(self, pdu):
        with pytest.raises(FailedRequestException, match="refused"):
            run(pdu, "on", [
                device_frame(0x35, PRESET),
                device_frame(0x35, [0x00]),
            ])

    def test_no_reply(self, pdu):
        with pytest.raises(FailedRequestException, match="No basic-set reply"):
            run(pdu, "on", [])

    def test_short_preset(self, pdu):
        with pytest.raises(FailedRequestException, match="preset length"):
            run(pdu, "on", [device_frame(0x35, [0x01])])

    @pytest.mark.parametrize("port", [0, 2])
    def test_port_out_of_range(self, pdu, port):
        with patch("pdudaemon.drivers.dp100.HIDDevice") as mock_cls:
            with pytest.raises(FailedRequestException, match="out of range"):
                pdu.port_interaction("on", port)
        mock_cls.assert_not_called()

    def test_unknown_command(self, pdu):
        with patch("pdudaemon.drivers.dp100.HIDDevice") as mock_cls:
            with pytest.raises(FailedRequestException, match="Unknown command"):
                pdu.port_interaction("reboot", 1)
        mock_cls.assert_not_called()
