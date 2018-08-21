#!/usr/bin/python3

#
#  Copyright 2018-2020 Intel Corporation
#  Author Tim Orling <timothy.t.orling@linux.intel.com>
#
#  Based on localcmdline.py
#  Copyright 2013 Linaro Limited
#  Author Matt Hart <matthew.hart@linaro.org>
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
from pdudaemon.drivers.localbase import LocalBase
import requests
from requests.auth import HTTPDigestAuth
import uuid

import os
log = logging.getLogger("pdud.drivers." + os.path.basename(__file__))


class DLIWebPowerSwitchPro(LocalBase):

    def __init__(self, hostname, settings):
        self.hostname = hostname
        self.settings = settings
        self.ip = settings.get("ip", self.hostname)
        self.url_base = "http://%s/restapi/" % self.ip
        self.username = "admin"
        self.password = "1234"
        log.debug(self.url_base)

        if "username" in settings:
            self.username = settings["username"]
        if "password" in settings:
            self.password = settings["password"]

    @classmethod
    def accepts(cls, drivername):
        if drivername == "dliwebpowerswitchpro":
            return True
        return False

    def _port_interaction(self, command, port_number):

        outlet = -1
        data = []
        token = ""
        headers = {}
        if port_number in range(1, 8):
            outlet = (port_number - 1)
        else:
            log.debug("Port number out of range")

        if command == "on":
            data = [('value', 'true')]
        elif command == "off":
            data = [('value', 'false')]
        elif command == "reboot":
            data = []
        else:
            log.debug("Unknown command!")

        if outlet in range(0, 7):
            token = str(uuid.uuid1())
            headers = {'X-CSRF': token}
            session = requests.Session()
            log.debug("Attempting control: %s port: %i" %
                      (command, port_number))

            if (command == "on") or (command == "off"):
                url = self.url_base + "relay/outlets/" + str(outlet)
                      + "/state/"
                log.debug("HTTP PUT at %s" % url)
                session.put(url, headers=headers, data=data,
                            auth=HTTPDigestAuth(self.username, self.password))
            elif (command == "reboot"):
                url = self.url_base + "relay/outlets/" + str(outlet)
                      + "/cycle/"
                log.debug("HTTP POST at %s" % url)
                session.post(url, headers=headers,
                             auth=HTTPDigestAuth(self.username, self.password))

        else:
            log.debug("Port number out of range")
