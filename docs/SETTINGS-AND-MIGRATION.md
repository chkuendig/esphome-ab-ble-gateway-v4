# Settings migration and public firmware

## Separation

The application is generic; NVS contains per-device configuration. Stock's
`storage/ssid` and `storage/passcode` strings were verified against the live
read-only `/connection` response and a prior flash backup. No stock reset or
network configuration change was needed. Personal Wi-Fi (`wifi-type = 0`) is
supported by the importer; enterprise authentication is not yet migrated.

ESPHome 2026.10.2 uses these preference records for this credential-free YAML:

| Namespace / key | Type and meaning |
| --- | --- |
| `esphome/88491487` | Blob: SSID[33] followed by password[65], both NUL-terminated; 98 bytes. Used when no STA network is compiled in. |
| `esphome/88491486` | Blob: 32-byte per-device API Noise key. Also used for encrypted OTA, including safe mode. |
| `ab_migration/reset` | u8: 1 prevents stock settings being reimported after a deliberate settings reset. |

The firmware imports stock Wi-Fi only when the normal ESPHome Wi-Fi record is
absent and reset suppression is not set. It never erases stock's namespace.
MQTT has been removed from the target firmware. Stock broker settings stay
untouched for stock rollback, but ESPHome neither imports nor uses them. Both
receivers deliver through the encrypted native Bluetooth API. Native API/OTA
encryption uses Noise. The importer does not reconfigure the network router.

These offsets/types are pinned-source contracts, not a promise about future
ESPHome versions. Recheck the upstream preference layout before upgrading.

## Preferred path: first-boot import

Keep stock's working Wi-Fi settings in place. After a backed-up, recoverable
application migration, `ab_settings` copies them into normal ESPHome
preferences before Wi-Fi starts, commits them and lets Wi-Fi reconnect. Stock credentials and broker settings remain intact for rollback. The only
vendor-settings write restores the standard vendor OTA feed when the stored
URL contains our installer's `/esphome-migration/` marker; unrelated custom
feeds are untouched. Verify reconnection,
persistence and API onboarding before accepting the firmware trial.

This needs no arbitrary NVS write endpoint in stock. The inspected stock HTTP
configuration handler (`0x400db548`) opens the literal `storage` namespace and
walks its supported setting table. Its certificate upload branch also writes
into `storage`. No supported HTTP operation for writing arbitrary ESPHome
preference records has been established.

## Optional pre-staging before switching firmware

1. While stock works, save private copies of `/info`, `/connection` and
   `/config`, plus verified full-flash backups where available. Keep file
   permissions restricted. Do not publish those responses or backups.
2. Prepare a private record bundle:

   ```sh
   python3 tools/prepare_settings.py private/recovery private/recovery/esphome-settings.json
   ```

   The tool reads `stock-info.json` and `stock-connection.json`, generates a
   random per-device API key, and writes a mode-0600 file. It refuses to
   overwrite an existing bundle. It makes no device changes.
3. The current path imports Wi-Fi on first boot instead of applying the bundle
   through an extra NVS writer. The original partition table and NVS remain.
4. On first connection, use ESPHome's reserved encrypted provisioning session
   (`ZERO_NOISE_PSK`), check the expected device identity, and set the random
   per-device key using the API's base64-encoded key payload. Reconnect using
   that private key before treating onboarding as complete.
5. Verify BLE traffic, GATT, network persistence and stock recovery before
   accepting the trial. Keep the key in a restricted local file for HA.

A bounded trial is in progress. No permanent acceptance or HA integration
retirement is claimed yet. The [offline preflight](MIGRATION-PREFLIGHT.md)
validates the backups, app and original geometry, but is not a hardware test.

## Reset and provisioning

A settings reset clears the ESPHome Wi-Fi and API key, preserves firmware
acceptance metadata and records reset suppression first. The stock settings
remain private on the device solely for stock rollback; the replacement does
not reconnect using them after that reset. Reprovision Wi-Fi with the
configuration button's SmartConfig gesture or UART0 Improv. API provisioning
uses ESPHome's runtime-key flow; that flow and SmartConfig need live testing.
OTA explicitly requires encryption: no plaintext OTA fallback is enabled.
No shared API/OTA key is compiled into public firmware.

## Publication

Keep `private/`, `.esphome`, `secrets.yaml`, NVS dumps, ELF/map files and old
personalized builds out of Git. Stage only reviewed source files. Inspect
tracked content and the candidate application against known SSIDs, passwords,
private keys (text and decoded bytes), broker addresses and private identifiers
before publishing. A clean source tree does not prove a cached binary is clean.
Publish a binary only after those checks and identify it honestly as a preview
or validated release. Never publish a raw full-device backup as firmware.
