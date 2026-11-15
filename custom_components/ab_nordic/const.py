"""Constants for the April Brother nRF52832 scanner."""

DOMAIN = "ab_nordic"

CONF_ESPHOME_ENTRY_ID = "esphome_entry_id"
CONF_PORT_NAME = "port_name"
# Canonical serial port URL. Stored under "device" so Home Assistant's usb
# integration attributes the ESPHome port to this entry ("in use").
CONF_DEVICE = "device"

# Must match the serial_proxy name in ab-ble-gateway-v4.yaml (an internal
# identifier; renaming it would need a firmware update).
DEFAULT_PORT_NAME = "Nordic scanner"
BAUD_RATE = 115200

SOURCE_MODEL = "AB BLE Gateway V4 (nRF52832)"
# User-visible suffix for the scanner/entry name. The radio is the nRF52832
# shown in the published V4 schematics (chip marking not inspected on a unit).
RADIO_NAME = "nRF52832"
LEGACY_TITLE_SUFFIX = " Nordic"

# Stop, disable scan-response requests, then stream binary SCAN2 records.
# 100 ms between commands loses the later ones; stock waits about 0.5 s.
START_COMMANDS = (b"\r\nAT+SCAN0\r\n", b"AT+ACT0\r\n", b"AT+SCAN2\r\n")
START_COMMAND_DELAY_SECONDS = 0.6

RECONNECT_MIN_SECONDS = 5
RECONNECT_MAX_SECONDS = 60
