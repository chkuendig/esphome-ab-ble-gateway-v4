"""April Brother stock GPIO12 configuration-button gestures."""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import stock_recovery
from esphome.const import CONF_ID

DEPENDENCIES = ["esp32", "wifi", "stock_recovery"]
ns = cg.esphome_ns.namespace("ab_button")
AbButton = ns.class_("AbButton", cg.Component)
CONFIG_SCHEMA = cv.Schema({
    cv.GenerateID(): cv.declare_id(AbButton),
    cv.Required("recovery_id"): cv.use_id(stock_recovery.StockRecovery),
}).extend(cv.COMPONENT_SCHEMA)

async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_recovery(await cg.get_variable(config["recovery_id"])))
