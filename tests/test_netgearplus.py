from unittest.mock import patch

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
def mock_connector():
    with patch("pdudaemon.drivers.netgearplus.py_netgear_plus.NetgearSwitchConnector") as mock_cls:
        sw = mock_cls.return_value
        sw.switch_model.MODEL_NAME = "GS305EPP"
        sw.get_login_cookie.return_value = True
        sw.switch_poe_port.return_value = True
        sw.delete_login_cookie.return_value = True
        yield mock_cls


@pytest.fixture
def mock_switch(mock_connector):
    return mock_connector.return_value


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
        assert pdu.port_count == 5

    def test_port_count_required(self):
        with pytest.raises(KeyError):
            NetgearPlusSwitch("dummy", {"ip": "192.168.1.50"})


class TestPortInteraction:
    @pytest.mark.parametrize("command", ["on", "off"])
    def test_switch_port(self, pdu, mock_connector, mock_switch, command):
        pdu.port_interaction(command, "2")
        mock_connector.assert_called_once_with("192.168.1.50", "secret")
        mock_switch.autodetect_model.assert_called_once()
        mock_switch.get_login_cookie.assert_called_once()
        mock_switch.switch_poe_port.assert_called_once_with(2, command)
        mock_switch.delete_login_cookie.assert_called_once()

    def test_port_at_boundary(self, pdu, mock_switch):
        # port_count is 5, so port 5 should work
        pdu.port_interaction("on", 5)
        mock_switch.switch_poe_port.assert_called_once_with(5, "on")

    @pytest.mark.parametrize("port", [0, 6])
    def test_port_out_of_range(self, pdu, mock_connector, port):
        with pytest.raises(FailedRequestException, match="out of range"):
            pdu.port_interaction("on", port)
        mock_connector.assert_not_called()

    def test_unknown_command(self, pdu, mock_connector):
        with pytest.raises(FailedRequestException, match="Unknown command"):
            pdu.port_interaction("reboot", 1)
        mock_connector.assert_not_called()

    def test_login_failure(self, pdu, mock_switch):
        mock_switch.get_login_cookie.return_value = False
        with pytest.raises(FailedRequestException, match="login cookie"):
            pdu.port_interaction("on", 1)
        mock_switch.switch_poe_port.assert_not_called()

    @pytest.mark.parametrize("command", ["on", "off"])
    def test_switch_failure_logs_out(self, pdu, mock_switch, command):
        mock_switch.switch_poe_port.return_value = False
        with pytest.raises(FailedRequestException,
                           match="Failed to turn PoE power %s" % command):
            pdu.port_interaction(command, 1)
        mock_switch.delete_login_cookie.assert_called_once()

    def test_switch_exception_logs_out(self, pdu, mock_switch):
        mock_switch.switch_poe_port.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            pdu.port_interaction("on", 1)
        mock_switch.delete_login_cookie.assert_called_once()

    def test_logout_failure_is_not_fatal(self, pdu, mock_switch, caplog):
        mock_switch.delete_login_cookie.return_value = False
        pdu.port_interaction("on", 1)
        assert "Failed to log out" in caplog.text
