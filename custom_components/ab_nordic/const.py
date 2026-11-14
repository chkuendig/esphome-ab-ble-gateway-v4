"""Constants for the April Brother Nordic scanner."""

DOMAIN = "ab_nordic"

CONF_ESPHOME_ENTRY_ID = "esphome_entry_id"
CONF_PORT_NAME = "port_name"

# Must match the serial_proxy name in xbg-proxy-split.yaml. The diagnostic
# profile's port has a different name, so this integration never claims it.
DEFAULT_PORT_NAME = "Nordic scanner"
BAUD_RATE = 115200

SOURCE_MODEL = "AB BLE Gateway V4 (Nordic)"

RECONNECT_MIN_SECONDS = 5
RECONNECT_MAX_SECONDS = 60
