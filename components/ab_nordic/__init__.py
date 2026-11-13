"""Preserve the April Brother Nordic scanner while ESP32 provides the BLE proxy."""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import uart
from esphome.const import CONF_ID

DEPENDENCIES = ["uart", "mqtt", "esp32"]
ns = cg.esphome_ns.namespace("ab_nordic")
AbNordic = ns.class_("AbNordic", cg.Component, uart.UARTDevice)
CONFIG_SCHEMA = cv.Schema({cv.GenerateID(): cv.declare_id(AbNordic)}).extend(
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
