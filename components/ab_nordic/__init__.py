"""Preserve the April Brother Nordic scanner while ESP32 provides the BLE proxy."""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import uart, bluetooth_proxy
from esphome.const import CONF_ID
from esphome.components import serial_proxy

DEPENDENCIES = ["uart", "bluetooth_proxy", "esp32"]
ns = cg.esphome_ns.namespace("ab_nordic")
AbNordic = ns.class_("AbNordic", cg.Component, uart.UARTDevice)
CONFIG_SCHEMA = cv.Schema({
    cv.GenerateID(): cv.declare_id(AbNordic),
    cv.Required("proxy_id"): cv.use_id(bluetooth_proxy.BluetoothProxy),
    cv.Optional("serial_proxy_id"): cv.use_id(serial_proxy.SerialProxy),
    # diagnostic: 60 s leased raw access, Nordic merged into the ESP32 proxy.
    # split: permanent raw stream for the HA ab_nordic scanner; dropped without it.
    cv.Optional("serial_mode", default="diagnostic"): cv.one_of("diagnostic", "split", lower=True),
}).extend(
    cv.COMPONENT_SCHEMA
).extend(uart.UART_DEVICE_SCHEMA)
FINAL_VALIDATE_SCHEMA = uart.final_validate_device_schema(
    "ab_nordic", baud_rate=115200, require_tx=True, require_rx=True,
    data_bits=8, parity="NONE", stop_bits=1,
)

async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await uart.register_uart_device(var, config)
    cg.add(var.set_proxy(await cg.get_variable(config["proxy_id"])))
    if "serial_proxy_id" in config:
        cg.add_define("AB_NORDIC_SERIAL_SPLIT" if config["serial_mode"] == "split"
                      else "AB_NORDIC_SERIAL_DIAGNOSTICS")
        cg.add(var.set_serial_proxy(await cg.get_variable(config["serial_proxy_id"])))
    bluetooth_proxy.enable_advertisement_filter()
    # Unknown address types from Nordic-only advertisements must never reach
    # Bluedroid as a guessed public/random address. Keep upstream error handling.
    cg.add_build_flag("-Wl,--wrap=esp_ble_gattc_open")
