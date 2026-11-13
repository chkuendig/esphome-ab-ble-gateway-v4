"""Trial/stock recovery and protection of the vendor's NVS partition."""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID

DEPENDENCIES = ["esp32"]
ns = cg.esphome_ns.namespace("stock_recovery")
StockRecovery = ns.class_("StockRecovery", cg.Component)
CONFIG_SCHEMA = cv.Schema({cv.GenerateID(): cv.declare_id(StockRecovery)}).extend(cv.COMPONENT_SCHEMA)

async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add_cmake_arg("CMAKE_EXE_LINKER_FLAGS",
                     "-Wl,--wrap=app_main,--wrap=nvs_flash_erase,--wrap=nvs_flash_erase_partition")
