import base64
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('provision_api', ROOT / 'tools/provision_api.py')
m = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'aioesphomeapi': types.SimpleNamespace(APIClient=None, ZERO_NOISE_PSK='bootstrap')}):
    spec.loader.exec_module(m)


def client(provisionable=False, name='ab-ble-gateway-v4-test'):
    return types.SimpleNamespace(
        connect=AsyncMock(), disconnect=AsyncMock(),
        device_info=AsyncMock(return_value=types.SimpleNamespace(
            name=name, api_encryption_provisionable=provisionable)),
        noise_encryption_set_key=AsyncMock(return_value=True))


class ProvisionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings = Path(self.tmp.name) / 'settings.json'
        self.output = Path(self.tmp.name) / 'connection.json'
        self.key = base64.b64encode(bytes(range(1, 33))).decode()
        self.settings.write_text(json.dumps({'device_mac': '00:11:22:33:44:55', 'records': [
            {'namespace': 'esphome', 'key': '88491486', 'value_base64': self.key}]}))

    async def test_bootstrap_key_is_base64_text_and_verified_privately(self):
        failed, bootstrap, verified = client(), client(True), client()
        failed.connect.side_effect = ConnectionError
        with patch.object(m, 'APIClient', side_effect=[failed, bootstrap, verified]) as factory:
            await m.provision('test.local', self.settings, self.output)
        bootstrap.noise_encryption_set_key.assert_awaited_once_with(self.key.encode('ascii'))
        self.assertEqual([c.kwargs['noise_psk'] for c in factory.call_args_list],
                         [self.key, m.ZERO_NOISE_PSK, self.key])
        self.assertTrue(all(c.kwargs['expected_mac'] == '001122334455' for c in factory.call_args_list))
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(self.output.read_text())['noise_psk'], self.key)
        for c in (failed, bootstrap, verified):
            c.disconnect.assert_awaited()

    async def test_existing_key_is_not_replaced(self):
        first, verified = client(), client()
        with patch.object(m, 'APIClient', side_effect=[first, verified]):
            await m.provision('test.local', self.settings, self.output)
        first.noise_encryption_set_key.assert_not_awaited()

    async def test_unexpected_firmware_cannot_be_provisioned(self):
        wrong = client(True, 'another-device')
        with patch.object(m, 'APIClient', return_value=wrong), self.assertRaises(ValueError):
            await m.provision('test.local', self.settings, self.output)
        wrong.noise_encryption_set_key.assert_not_awaited()
        self.assertFalse(self.output.exists())
        wrong.disconnect.assert_awaited()

    async def test_failed_private_reconnect_does_not_claim_success(self):
        first, failed = client(True), client()
        failed.connect.side_effect = ConnectionError
        with patch.object(m, 'APIClient', side_effect=[first, failed]), self.assertRaises(ConnectionError):
            await m.provision('test.local', self.settings, self.output)
        self.assertFalse(self.output.exists())
        failed.disconnect.assert_awaited()

    async def test_existing_output_prevents_device_changes(self):
        self.output.write_text('keep')
        with patch.object(m, 'APIClient') as factory, self.assertRaises(FileExistsError):
            await m.provision('test.local', self.settings, self.output)
        factory.assert_not_called()
        self.assertEqual(self.output.read_text(), 'keep')


if __name__ == '__main__':
    unittest.main()
