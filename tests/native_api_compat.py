"""Optional offline compatibility check using installed HA Bluetooth libraries.

Run in a separate Python process with aioesphomeapi, bleak_esphome and
habluetooth installed. Does not contact HA, register an adapter, call setup(),
or access a network/radio. No running HA state is modified.
"""
import unittest

from aioesphomeapi.api_pb2 import BluetoothLERawAdvertisementsResponse
from bleak_esphome.backend.scanner import ESPHomeScanner
from habluetooth import BluetoothManager
from habluetooth.central_manager import set_manager


class OfflineManager(BluetoothManager):
    def _discover_service_info(self, *args):
        pass


class NativeApiCompatibility(unittest.IsolatedAsyncioTestCase):
    async def test_passive_data_preserves_unknown_and_known_address_types(self):
        set_manager(OfflineManager())
        for address_type in (127, 255, 0, 1):
            with self.subTest(address_type=address_type):
                scanner = ESPHomeScanner("02:00:00:00:00:01", "offline-native-test", connectable=True)
                message = BluetoothLERawAdvertisementsResponse()
                message.advertisements.add(
                    address=0x123456789ABC, rssi=-70, address_type=address_type,
                    data=bytes.fromhex("020106051695fe0102"),
                )
                decoded = BluetoothLERawAdvertisementsResponse.FromString(message.SerializeToString())
                scanner.async_on_raw_advertisements(decoded)
                device, advertisement = scanner.get_discovered_device_advertisement_data("12:34:56:78:9A:BC")
                self.assertEqual(device.details["address_type"], address_type)
                self.assertEqual(advertisement.rssi, -70)
                self.assertEqual(advertisement.service_data["0000fe95-0000-1000-8000-00805f9b34fb"], b"\x01\x02")


if __name__ == "__main__":
    unittest.main()
