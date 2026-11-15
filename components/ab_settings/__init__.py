"""Import the stock firmware's saved Wi-Fi network into ESPHome on first boot."""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID

DEPENDENCIES = ["esp32", "wifi"]
ns = cg.esphome_ns.namespace("ab_settings")
AbSettings = ns.class_("AbSettings", cg.Component)
CONFIG_SCHEMA = cv.Schema({
    cv.GenerateID(): cv.declare_id(AbSettings),
}).extend(cv.COMPONENT_SCHEMA)

async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
