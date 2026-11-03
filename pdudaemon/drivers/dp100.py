#!/usr/bin/python3
#
#  Copyright 2026 Tim Orling <tim DOT orling AT konsulko DOT com>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.

import logging
import os
from pdudaemon.drivers.driver import PDUDriver, FailedRequestException
from pdudaemon.drivers.hiddevice import HIDDevice

log = logging.getLogger("pdud.drivers." + os.path.basename(__file__))

# Alientek DP100 USB-C digital power supply, controlled over USB HID.
# The DP100 must be in USBD mode (double-tap the left button to switch).
#
# Frames are [address, function, sequence, length, data..., CRC-16/MODBUS]
# in 64-byte HID reports. The basic-set function reads or writes the active
# preset: [index | flag, output, Vset, Iset, OVP, OCP], 16-bit little-endian.
DP100_VID = 0x2E3C
DP100_PID = 0xAF01
REPORT_SIZE = 64
READ_TIMEOUT_MS = 1000
MAX_READS = 10

ADDR_HOST = 0xFB
ADDR_DEVICE = 0xFA
FUNC_BASIC_SET = 0x35
BASIC_SET_WRITE = 0x20
BASIC_SET_READ = 0x80
BASIC_SET_LEN = 10


def crc16_modbus(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def build_frame(function, data):
    frame = bytes([ADDR_HOST, function, 0, len(data)]) + bytes(data)
    crc = crc16_modbus(frame)
    return frame + bytes([crc & 0xFF, crc >> 8])


def parse_frame(report):
    """Return (function, data) of a device frame, or None if invalid."""
    report = bytes(report)
    if len(report) < 6 or report[0] != ADDR_DEVICE:
        return None
    end = 4 + report[3]
    if len(report) < end + 2 or crc16_modbus(report[:end + 2]) != 0:
        return None
    return report[1], report[4:end]


class DP100(PDUDriver):
    port_count = 1

    def __init__(self, hostname, settings):
        self.hostname = hostname
        self.serial = settings.get("serial")
        super().__init__()

    def port_interaction(self, command, port_number):
        if command not in ("on", "off"):
            raise FailedRequestException("Unknown command %s" % command)
        if int(port_number) != 1:
            raise FailedRequestException(
                "port_number %s is out of range, the DP100 has one output"
                % port_number)

        with HIDDevice(DP100_VID, DP100_PID, self.serial) as dev:
            # Keep the active preset and only change the output state
            preset = self._basic_set(dev, [BASIC_SET_READ])
            if len(preset) != BASIC_SET_LEN:
                raise FailedRequestException(
                    "Unexpected DP100 preset length %d" % len(preset))
            output = 1 if command == "on" else 0
            request = [preset[0] | BASIC_SET_WRITE, output] + list(preset[2:])
            if self._basic_set(dev, request) != b"\x01":
                raise FailedRequestException(
                    "DP100 refused to turn output %s" % command)
        log.debug("Turned DP100 output %s", command)

    @staticmethod
    def _basic_set(dev, data):
        frame = build_frame(FUNC_BASIC_SET, data)
        # Prefix report ID 0 and pad to the full report size
        report = bytes([0]) + frame.ljust(REPORT_SIZE, b"\x00")
        if dev.write(report) < 0:
            raise FailedRequestException("Failed to write to DP100")
        for _ in range(MAX_READS):
            reply = dev.read(REPORT_SIZE, READ_TIMEOUT_MS)
            if not reply:
                break
            parsed = parse_frame(reply)
            if parsed and parsed[0] == FUNC_BASIC_SET:
                return parsed[1]
        raise FailedRequestException("No basic-set reply from DP100")

    @classmethod
    def accepts(cls, drivername):
        return drivername == "dp100"
