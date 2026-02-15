from unittest.mock import MagicMock, patch

import pytest
from pdudaemon.drivers.driver import FailedRequestException
from pdudaemon.drivers.netgearplus import NetgearPlusSwitch


SETTINGS = {
    "ip": "192.168.1.50",
    "password": "secret",
    "port_count": "5",
}


@pytest.fixture
def pdu():
    return NetgearPlusSwitch("dummy", SETTINGS)


@pytest.fixture
def mock_switch():
    with patch("pdudaemon.drivers.netgearplus.py_netgear_plus.NetgearSwitchConnector") as mock_cls:
        sw = MagicMock()
        sw.switch_model.MODEL_NAME = "GS305EPP"
        sw.get_login_cookie.return_value = True
        sw.get_switch_infos.return_value = {"model": "GS305EPP"}
        sw.turn_on_poe_port.return_value = True
        sw.turn_off_poe_port.return_value = True
        mock_cls.return_value = sw
        yield sw


class TestAccepts:
    def test_accepts_netgearplus(self):
        assert NetgearPlusSwitch.accepts("netgearplus") is True

    def test_rejects_unknown(self):
        assert NetgearPlusSwitch.accepts("netgear") is False
        assert NetgearPlusSwitch.accepts("snmpv1") is False


class TestInit:
    def test_settings_parsed(self, pdu):
        assert pdu.hostname == "dummy"
        assert pdu.ip == "192.168.1.50"
        assert pdu.password == "secret"
        assert pdu.port_count == "5"


class TestPortInteraction:
    def test_turn_on(self, pdu, mock_switch):
        pdu.port_interaction("on", 1)
        mock_switch.autodetect_model.assert_called_once()
        mock_switch.get_login_cookie.assert_called_once()
        mock_switch.turn_on_poe_port.assert_called_once_with(1)

    def test_turn_off(self, pdu, mock_switch):
        pdu.port_interaction("off", 2)
        mock_switch.turn_off_poe_port.assert_called_once_with(2)

    def test_port_out_of_range(self, pdu, mock_switch):
        with pytest.raises(FailedRequestException, match="out of range"):
            pdu.port_interaction("on", 6)

    def test_port_at_boundary(self, pdu, mock_switch):
        # port_count is "5", so port 5 should work
        pdu.port_interaction("on", 5)
        mock_switch.turn_on_poe_port.assert_called_once_with(5)

    def test_unknown_command(self, pdu, mock_switch):
        with pytest.raises(FailedRequestException, match="Unknown command"):
            pdu.port_interaction("reboot", 1)

    def test_login_failure(self, pdu, mock_switch):
        mock_switch.get_login_cookie.return_value = False
        with pytest.raises(FailedRequestException, match="login cookie"):
            pdu.port_interaction("on", 1)

    def test_turn_on_failure(self, pdu, mock_switch):
        mock_switch.turn_on_poe_port.return_value = False
        with pytest.raises(FailedRequestException, match="Failed to turn PoE power on"):
            pdu.port_interaction("on", 1)

    def test_turn_off_failure(self, pdu, mock_switch):
        mock_switch.turn_off_poe_port.return_value = False
        with pytest.raises(FailedRequestException, match="Failed to turn PoE power off"):
            pdu.port_interaction("off", 1)
