# Home Assistant setup

Requires **HA 2026.11+** and core `bluetooth`, `esphome`, `usb` integrations. `usb` supplies serial-proxy transport; no physical USB connection to HA is needed.

## Add the ESP32 gateway

1. Install [firmware](migrating-from-stock.md) and let it join Wi-Fi.
2. In **Settings → Devices & services**, add the discovered ESPHome device. Without mDNS, add **ESPHome** manually by gateway IP.
3. Complete pairing; check buttons and Bluetooth proxy.

**Network** selects **Automatic**, **Wi-Fi** or **Ethernet**; changes restart the gateway. Only one interface runs. Automatic uses Ethernet only without saved Wi-Fi. If Ethernet has no link two minutes after boot and Wi-Fi is saved, Wi-Fi takes over until restart.

On a trusted LAN, HA automatically provisions a per-device encryption key through zero-PSK Noise, then reconnects with it. No key is compiled in. Encrypted OTA (TCP 3232) uses the same key.

ESP32 scans passively and supports **one active GATT connection**. Only HA's core ESPHome integration should subscribe to advertisements: ESPHome permits one subscriber, so another API client conflicts.

## Add the nRF52832 scanner

1. In the **Marketplace**, add `chkuendig/esphome-ab-ble-gateway-v4` as a custom repository of category **Integration**; install it and restart HA. Alternatively, copy `custom_components/ab_nordic` into HA's `custom_components` and restart.
2. In **Settings → Devices & services → Add integration**, select **April Brother nRF52832 Scanner**. Do not use the serial-port **Set up** picker.
3. Select the loaded ESPHome gateway with port `Nordic scanner`.

| HA adapter | Radio | Connections |
| --- | --- | --- |
| Core ESPHome proxy | ESP32 | One GATT slot |
| April Brother nRF52832 Scanner (`ab_nordic`) | nRF52832, stock firmware | Advertisements only |

The integration receives UART bytes through encrypted [serial proxy](https://esphome.io/components/serial_proxy/). On each connection, HA sends `SCAN0 → ACT0 → SCAN2`, approximately 600 ms apart, then decodes advertisements. No custom nRF52832 firmware component is needed. Data is forwarded only with a serial client connected. GATT requires ESP32 reception; devices heard only by nRF52832 cannot connect through it.

## Diagnostics

Download diagnostics from the custom integration's entry: connection state, `connects` (connection count), `bytes_received`, `records`, `malformed`, `discarded_bytes`, `last_error`. Increasing `records` confirms decoding; discarded bytes include command replies or noise.
