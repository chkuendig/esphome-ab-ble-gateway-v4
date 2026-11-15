# Migrate from stock firmware

This path installs an **app-only** ESPHome image through stock's network updater. It keeps the original bootloader, partition table and stock settings, and preserves a verified stock app for return when one is available.

## Before updating

- Save private copies of stock's `/info`, `/config` and `/connection` JSON responses. They can contain credentials. If you have full-flash backups, keep them private too: they contain Wi-Fi secrets and device settings. This network installer does not require a UART cable or a full-flash backup.
- Keep stock connected to working personal Wi-Fi, or to Ethernet. Enterprise Wi-Fi settings are not imported. With no Wi-Fi network imported, the **Network** select's default (**Automatic**) brings ESPHome up on Ethernet instead. Have Home Assistant 2026.11+ ready for pairing during the trial.
- [Build the app-only image](building.md), confirm it fits **0x100000 = 1,048,576 bytes**, and use a trusted LAN with stable power.

The supported flash layout is in `partitions.csv`: NVS at `0x9000`, OTA metadata at `0xD000`, PHY data at `0xF000`, and three 1 MiB app slots (`factory`, `ota_0`, `ota_1`) at `0x10000`, `0x110000`, `0x210000`. No repartitioning is performed.

## Serve and install the app

Run from the repository root, replacing the example addresses with the LAN server and gateway addresses:

```sh
python3 tools/serve_migration.py build/ab-ble-gateway-v4.ota.bin \
  --bind-ip 192.0.2.10 --gateway-ip 192.0.2.20
```

The helper checks the ESP32 app image and its size, prints a temporary base URL containing `/esphome-migration/<token>/`, and serves downloads only to the specified gateway IP. Keep it running; it exits after 20 minutes. This checks the candidate image, not the gateway's board or installed stock firmware.

Set stock's `ota-url` to the printed base URL, then trigger its updater. The HTTP operations are form-encoded:

```sh
curl --fail --data-urlencode 'ota-url=<base URL printed by the helper>' \
  http://192.0.2.20/config
curl --fail --data 'ota-update=1' http://192.0.2.20/update
```

Stock 1.5.13 requests `<base>/1.5.13/ota.bin`. The helper accepts a version directory beneath its random prefix and supplies the same app-only image. Never serve a merged/factory image or full-flash backup to this endpoint.

## First boot and acceptance

Before normal ESPHome startup, `stock_recovery` looks for stock in the factory slot or the other OTA slot. A stock app must pass ESP-IDF image verification and identify its project as `xin-ble-gateway`. When needed, it is copied into factory **with the header sector written last**, then verified. The source OTA copy stays intact during the operation.

With verified stock available, the firmware starts a **15-minute trial**, retaining stock as the fallback. `ab_settings` imports the personal Wi-Fi SSID and passcode from NVS namespace `storage` into ESPHome's saved Wi-Fi, provided ESPHome has no saved network and a previous settings reset has not disabled import. Stock's own settings remain available for return. The helper's temporary `/esphome-migration/` OTA URL is restored to the vendor feed, `http://ota.bconimg.com/gw4`; unrelated custom feed URLs are left alone.

Add the gateway through [Home Assistant's ESPHome integration](home-assistant.md). HA provisions its per-device encryption key automatically. Confirm network reconnection and the Bluetooth functions you need, then press **Accept firmware** before the trial expires. Otherwise it returns to stock. Acceptance persists; subsequent updates using the same acceptance metadata do not necessarily start a fresh trial.

**If no verified stock app is found, ESPHome boots without the trial or restore safety net.** A successful ESPHome connection alone does not confirm that recovery is available; check the startup recovery messages before relying on it.

## Return to stock or reset settings

Press **Restore stock firmware** to select the preserved stock app and restart. It needs no download and keeps stock's settings. After return, the ESPHome connection disappears because stock does not speak the ESPHome API.

Alternatively, upload a compatible **stock app-only image** through ESPHome's encrypted OTA service on TCP 3232, using the provisioned per-device key. Prefer the stock app from your own backup. Do not upload a complete backup, a padded slot dump or a merged image. Stock-payload upload through this path has not been tested on hardware; the restore button is the tested return path.

After accepting ESPHome, holding the physical configuration button (GPIO12, active low) for **10 seconds** clears ESPHome settings, including Wi-Fi and its API key. It preserves stock settings and firmware acceptance, and records that stock Wi-Fi must not be re-imported. Provision Wi-Fi again with Improv over UART0 (or use Ethernet: with no Wi-Fi network saved, **Automatic** mode starts Ethernet) and pair HA again. This reset is disabled during an unaccepted trial.

## Vendor downloads and physical recovery

The standard vendor feed follows `http://ota.bconimg.com/gw4/<starting-version>/ota.bin`. The directory names the **starting version**, not necessarily the version downloaded. The [1.5.13 feed URL](http://ota.bconimg.com/gw4/1.5.13/ota.bin) is an update feed, not a guaranteed download of stock 1.5.13; contents can change. See the vendor [software page](https://wiki.aprbrother.com/en/Software_AB_BLE_Gateway_V4.html) and [update FAQ](https://wiki.aprbrother.com/en/FAQ_For_AB_BLE_Gateway_V4.html). This repository does not redistribute vendor firmware.

If network recovery is unavailable, the last resort is UART/esptool recovery. The [published hardware drawings](https://github.com/AprilBrother/ab-hardware/tree/master/ab-ble-gateway-v4) show a header with GND, UART0, GPIO0, EN and 3.3 V. Check its orientation and your actual PCB before connecting a 3.3 V UART adapter; firmware recovery cannot repair incorrect wiring. An ESP32 backup does not contain the nRF52832 firmware.

## Validation scope

Tested on hardware with stock **1.5.13**: app-only migration, personal Wi-Fi import, encrypted API/OTA, timed return and the restore button. The generalized stock recognition and consolidated profile need fresh hardware validation. Other stock versions and PCB revisions, physical button reset, Improv, physical UART recovery and power loss during factory copying remain untested.
