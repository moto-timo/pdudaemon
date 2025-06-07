#!/usr/bin/python3
#
#  Copyright 2025 Tim Orling <tim DOT orling AT konsulko DOT com>
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
import py_netgear_plus

log = logging.getLogger("pdud.drivers." + os.path.basename(__file__))


# The following driver has been tested with the hardware:
#   Model No          GS305EPP
#   Firmware Version  v1.0.1.4
# (Settings > Firmware in the web interface)
#
class NetgearPlusSwitch(PDUDriver):
    def __init__(self, hostname, settings):
        self.hostname = hostname
        self.ip = settings.get('ip')
        self.password = settings.get("password")
        self.port_count = settings.get('port_count')

        super(NeatgearPlusSwitch, self).__init__()

    def port_interaction(self, command, port_number):
        sw = py_netgear_plus.NetgearSwitchConnector(self.ip, self.password)
        sw.autodetect_model()
        sw.get_login_cookie()
        log.debug('Netgear switch model: %s' % sw.switch_model.MODEL_NAME)
        if port_number <= self.port_count:
            if command == "on":
                sw.turn_on_poe_port(port_number)
            elif command == "off":
                sw.turn_on_poe_port(port_number)
            else:
                raise FailedRequestException('Unknown command %s' % (command))
        else:
            raise FailedRequestException('port_number %s is out of range' % (port_number))

    @classmethod
    def accepts(cls, drivername):
        return drivername == "netgearplus"
