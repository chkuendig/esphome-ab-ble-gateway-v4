"""Keep the stock firmware as a fallback: factory copy, trial, restore, NVS protection."""
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
    # OTA would otherwise accept plaintext uploads until (and, for old clients,
    # after) the API key is provisioned, while `ota: encryption:` cannot be set
    # with a runtime-provisioned key. Recovery depends on trusted images only.
    cg.add_define("USE_OTA_ENCRYPTION_REQUIRED")
    cg.add_cmake_arg("CMAKE_EXE_LINKER_FLAGS",
                     "-Wl,--wrap=app_main,--wrap=nvs_flash_erase,--wrap=nvs_flash_erase_partition")
