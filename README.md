# ESPHome for the April Brother AB BLE Gateway V4

Turn an AB BLE Gateway V4 into a local Home Assistant Bluetooth gateway. The ESP32 provides a connectable ESPHome Bluetooth proxy, while the nRF52832 supplies a second, listen-only scanner through a small Home Assistant custom integration. The firmware preserves a verified copy of stock for recovery and imports existing personal Wi-Fi settings on first boot.

## Device

| Part | Specification |
| --- | --- |
| Main processor | Classic ESP32, 4 MiB flash |
| Second radio | nRF52832 “side board” running April Brother's stock scanner firmware |
| Radio link | UART: ESP32 RX=GPIO32, TX=GPIO33; 115200 baud, 8N1 |
| Ethernet | LAN8720-family PHY, address 1, MDC GPIO23, MDIO GPIO18, RMII clock out on GPIO17, PHY reset GPIO13 |
| Configuration button | GPIO12, active low |
| Status LED | GPIO5, active low, from the published drawings |

PCB revisions vary; check the [hardware drawings](https://github.com/AprilBrother/ab-hardware/tree/master/ab-ble-gateway-v4) against your board. The nRF52832 firmware is left intact.

## What it exposes

One standard profile: `ab-ble-gateway-v4.yaml`.

| Feature | Behavior |
| --- | --- |
| Wi-Fi | Imports stock personal Wi-Fi; Improv provisioning over UART0 |
| Ethernet | Same image; used instead of Wi-Fi (see below) |
| Network select | **Automatic** (Ethernet only if no Wi-Fi network is saved), **Wi-Fi** or **Ethernet**; a change restarts the gateway |
| ESP32 Bluetooth proxy | Passive scanning by default; active GATT connections, one connection slot |
| nRF52832 UART | ESPHome `serial_proxy` port `Nordic scanner`; the HA integration starts and decodes scanning |
| Native API and OTA | Encrypted, per-device key; OTA on TCP 3232 |
| Software buttons | **Accept firmware**, **Restore stock firmware**, **Restart** |
| Physical button | Binary sensor; a 10-second hold resets ESPHome settings after acceptance |
| LED | Status indication |

Wi-Fi and Ethernet are built into one image but run **one at a time**, as on stock: the board has the ESP32 generate the Ethernet RMII clock, and ESP-IDF warns that Wi-Fi is unstable while it does. In **Automatic** mode a gateway with a saved (or imported) Wi-Fi network uses Wi-Fi, and one without uses Ethernet.

## Guides

- [Build a firmware image](docs/building.md)
- [Migrate from stock and return to it](docs/migrating-from-stock.md)
- [Set up Home Assistant](docs/home-assistant.md)
- [nRF52832 UART protocol](docs/uart-protocol.md)

## Hardware validation

Tested on hardware: app-only OTA from stock 1.5.13, Wi-Fi import, encrypted API/OTA, ESP32 proxy and GATT, timed return to stock, the restore button, and the nRF52832 scanner through the HA integration. These checks cover the existing implementation; the consolidated profile needs its own validation.

Not yet tested: physical button gestures, LED, Improv serial, Ethernet and the network select, power loss during the factory copy, other PCB revisions or stock versions. Only stock 1.5.13 has been tested on hardware. If no verified stock app is found, ESPHome starts without trial or restore protection.

## Vendor firmware

This repository does not redistribute April Brother firmware. Keep flash backups private: they contain Wi-Fi credentials and other device settings.

Vendor references: [quick start](https://wiki.aprbrother.com/en/Quick_Start_For_AB_BLE_Gateway_V4.html), [FAQ](https://wiki.aprbrother.com/en/FAQ_For_AB_BLE_Gateway_V4.html), [software](https://wiki.aprbrother.com/en/Software_AB_BLE_Gateway_V4.html).
