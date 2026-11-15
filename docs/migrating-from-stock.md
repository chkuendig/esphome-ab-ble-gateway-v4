# Migrate from stock firmware

Stock's network updater installs an **app-only** ESPHome image, retaining the bootloader, partitions, settings and a verified stock app when available. No UART cable or full-flash backup is required.

## Prepare

- Save stock's `/info`, `/config` and `/connection` JSON responses. Keep these and flash backups private: they contain credentials and device settings.
- Connect stock to personal Wi-Fi or Ethernet. Enterprise Wi-Fi is not imported; without imported Wi-Fi, **Network → Automatic** starts Ethernet. Have HA 2026.11+ ready for trial pairing.
- [Build the app-only image](building.md); confirm it fits **0x100000 = 1,048,576 bytes**. Use a trusted LAN and stable power.

Retained layout (`partitions.csv`):

| Partition | Address | Size |
| --- | --- | --- |
| NVS | `0x9000` | 16 KiB |
| OTA metadata | `0xD000` | 8 KiB |
| PHY data | `0xF000` | 4 KiB |
| `factory` | `0x10000` | 1 MiB |
| `ota_0` | `0x110000` | 1 MiB |
| `ota_1` | `0x210000` | 1 MiB |

## Serve and install

From the repository root, substitute your LAN server and gateway addresses:

```sh
python3 tools/serve_migration.py build/ab-ble-gateway-v4.ota.bin \
  --bind-ip 192.0.2.10 --gateway-ip 192.0.2.20
```

The helper checks image format/size, prints a base URL containing `/esphome-migration/<token>/`, and restricts downloads to the gateway IP. Keep it running; it exits after 20 minutes.

Set `ota-url` and trigger the updater with form-encoded requests:

```sh
curl --fail --data-urlencode 'ota-url=<base URL printed by the helper>' \
  http://192.0.2.20/config
curl --fail --data 'ota-update=1' http://192.0.2.20/update
```

Stock 1.5.13 requests `<base>/1.5.13/ota.bin`. The helper accepts version directories under its random prefix, serving the same image. **Never serve a merged/factory image or full-flash backup here.**

## First boot: accept within 15 minutes

`stock_recovery` searches factory and the other OTA slot for an ESP-IDF-verified app identifying as `xin-ble-gateway`. If needed, it copies stock into factory **header sector last**, verifies it, and retains the source OTA copy.

With verified stock, ESPHome starts a **15-minute trial**. `ab_settings` imports personal Wi-Fi SSID/passcode from NVS `storage` only if no ESPHome network is saved and no previous settings reset disabled import. Stock settings remain intact. Temporary `/esphome-migration/` OTA URLs revert to `http://ota.bconimg.com/gw4`; other custom feeds remain unchanged.

[Pair with HA](home-assistant.md), which provisions encryption automatically. Check network reconnection and Bluetooth, then press **Accept firmware** before expiry or the gateway returns to stock. Acceptance persists: later ESPHome updates don't start a new trial.

**Without verified stock, there is no trial or restore safety net.** Check startup recovery messages before relying on recovery.

## Restore stock or reset settings

- **Restore stock firmware** restarts into preserved stock without downloading, retaining stock settings. The ESPHome connection disappears: stock has no ESPHome API.
- Alternatively, upload a compatible **stock app-only image**, preferably from your backup, through encrypted OTA on TCP 3232 using the provisioned per-device key. Never upload a complete backup, padded slot dump or merged image.
- **After acceptance only**, hold GPIO12 (active low) for **10 seconds** to clear ESPHome settings, including Wi-Fi/API key. Stock settings and acceptance persist; stock Wi-Fi re-import is disabled. Reprovision using Improv over UART0 or Ethernet (**Automatic** uses Ethernet without saved Wi-Fi), then pair HA again. Reset is disabled during an unaccepted trial.

## Vendor downloads and UART recovery

Vendor feed: `http://ota.bconimg.com/gw4/<starting-version>/ota.bin`. The directory identifies the starting version, not the download: [the 1.5.13 feed](http://ota.bconimg.com/gw4/1.5.13/ota.bin) can change. See [vendor software](https://wiki.aprbrother.com/en/Software_AB_BLE_Gateway_V4.html) and [update FAQ](https://wiki.aprbrother.com/en/FAQ_For_AB_BLE_Gateway_V4.html).

If network recovery fails, use UART/esptool. The [drawings](https://github.com/AprilBrother/ab-hardware/tree/master/ab-ble-gateway-v4) show GND, UART0, GPIO0, EN and 3.3 V. **Check header orientation against your PCB before attaching a 3.3 V UART adapter.** ESP32 backups exclude nRF52832 firmware.
