import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

spec = importlib.util.spec_from_file_location(
    "serial_probe", Path(__file__).resolve().parents[1] / "tools/nordic_serial_probe.py")
m = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"aioesphomeapi": types.SimpleNamespace(APIClient=None)}):
    spec.loader.exec_module(m)


def client(status=0):
    button = type("ButtonInfo", (), {"name": "Begin Nordic Diagnostics", "key": 42})()
    return types.SimpleNamespace(
        list_entities_services=AsyncMock(return_value=([button], [])),
        subscribe_serial_proxy_data=Mock(return_value=Mock()), button_command=Mock(),
        serial_proxy_subscribe_await_response=AsyncMock(return_value=types.SimpleNamespace(status=status)),
        serial_proxy_configure_await_response=AsyncMock(return_value=types.SimpleNamespace(status=0)),
        serial_proxy_write=Mock(), serial_proxy_unsubscribe_await_response=AsyncMock())


class SerialProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_paced_queries_and_cleanup(self):
        c = client()
        with patch.object(m.asyncio, "sleep", new=AsyncMock()) as sleep:
            await m.probe(c, ["status", "version"], Mock())
        c.button_command.assert_called_once_with(42)
        self.assertEqual([call.args[1] for call in c.serial_proxy_write.call_args_list],
                         [b"AT\r\n", b"AT+VERS?\r\n"])
        self.assertEqual(sleep.await_count, 4)
        c.serial_proxy_unsubscribe_await_response.assert_awaited_once()
        c.subscribe_serial_proxy_data.return_value.assert_called_once()

    async def test_busy_port_never_transmits(self):
        c = client(2)
        with patch.object(m.asyncio, "sleep", new=AsyncMock()), self.assertRaises(RuntimeError):
            await m.probe(c, ["status"], Mock())
        c.serial_proxy_write.assert_not_called()
        c.serial_proxy_unsubscribe_await_response.assert_awaited_once()

    async def test_missing_firmware_never_arms_or_subscribes(self):
        c = client()
        c.list_entities_services.return_value = ([], [])
        with self.assertRaises(RuntimeError):
            await m.probe(c, ["status"], Mock())
        c.button_command.assert_not_called()
        c.serial_proxy_subscribe_await_response.assert_not_awaited()

    async def test_transmit_failure_still_releases(self):
        c = client()
        c.serial_proxy_write.side_effect = ConnectionError
        with patch.object(m.asyncio, "sleep", new=AsyncMock()), self.assertRaises(ConnectionError):
            await m.probe(c, ["status"], Mock())
        c.serial_proxy_unsubscribe_await_response.assert_awaited_once()
        c.subscribe_serial_proxy_data.return_value.assert_called_once()
