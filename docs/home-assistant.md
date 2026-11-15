# Home Assistant setup

Use **Home Assistant 2026.11 or newer**, with the core `bluetooth`, `esphome` and `usb` integrations loaded. The USB integration supplies the ESPHome serial-proxy transport; a physical USB connection to HA is not required.

## Add the ESP32 gateway

1. Install the [standard firmware](migrating-from-stock.md) and let it join Wi-Fi.
2. Open **Settings → Devices & services** and add the discovered ESPHome device. If mDNS discovery is unavailable, add **ESPHome** manually using the gateway's IP address.
3. Complete pairing and check that the gateway's buttons and Bluetooth proxy appear.

The gateway uses Wi-Fi or Ethernet, never both. The **Network** select (Automatic, Wi-Fi, Ethernet) chooses which one; changing it restarts the gateway. Automatic uses Ethernet only when no Wi-Fi network is saved. If Ethernet has no link two minutes after boot and a Wi-Fi network is saved, the gateway falls back to Wi-Fi until the next restart.

API encryption is enabled without a compiled key. HA 2026.11 generates and provisions a per-device key automatically through a zero-PSK Noise provisioning session, then reconnects with that private key. Use a trusted LAN for initial pairing. Encrypted OTA on TCP 3232 uses the same per-device key.

The ESP32 proxy scans passively by default and supports active GATT connections with **one connection slot**. Its advertisement subscription must belong to HA's core ESPHome integration: ESPHome allows only one advertisement subscriber, so another API client subscribing to Bluetooth advertisements will conflict with HA.

## Add the nRF52832 scanner

1. In HACS, add `chkuendig/esphome-ab-ble-gateway-v4` as a custom repository of type **Integration**, install it, and restart HA. Alternatively, copy `custom_components/ab_nordic` from this repository into HA's `custom_components` directory and restart.
2. Open **Settings → Devices & services → Add integration** and select **April Brother nRF52832 Scanner**. Use this integration flow, rather than the serial-port **Set up** picker.
3. Select the already-loaded ESPHome gateway exposing the port named `Nordic scanner`.

HA now has two Bluetooth adapters:

| Adapter | Radio | Connections |
| --- | --- | --- |
| Core ESPHome proxy | ESP32 | One GATT connection slot |
| April Brother nRF52832 Scanner (`ab_nordic`) | nRF52832, stock scanner firmware | None; advertisements only |

The custom integration receives raw UART data through ESPHome's encrypted [serial proxy](https://esphome.io/components/serial_proxy/). Each time it connects, **the HA integration** sends `SCAN0 → ACT0 → SCAN2`, with about 600 ms between commands, then decodes advertisements. There is no custom nRF52832 firmware component. Without a serial client connected, nRF52832 data is not forwarded. Devices heard only by that radio cannot be connected to through it; GATT requires ESP32 reception.

## Diagnostics and validation

Download diagnostics from the custom integration's entry to inspect connection state, connection count (`connects`), `bytes_received`, parsed `records`, `malformed`, `discarded_bytes` and `last_error`. Increasing record counts confirm that the stream is being decoded. Discarded bytes can include command replies as well as noise.

Tested on hardware: encrypted onboarding/API/OTA, ESP32 advertisements and GATT, and the separate nRF52832 scanner in HA. The consolidated firmware and the new HA-managed start sequence still need hardware validation; reboot/reconnection behavior, prolonged operation and HA startup with the gateway offline have not been established by those earlier checks.
