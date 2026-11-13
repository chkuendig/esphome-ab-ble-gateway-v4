"""Import credentials from this gateway, never from a public firmware image."""
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
    # Native OTA can load a runtime API key, but its encryption: YAML schema
    # currently only accepts a compiled key. Require the same encrypted path.
    cg.add_define("USE_OTA_ENCRYPTION_REQUIRED")
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
