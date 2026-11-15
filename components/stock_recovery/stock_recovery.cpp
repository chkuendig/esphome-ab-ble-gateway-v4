#include "stock_recovery.h"
#include "copy.h"
#include "esphome/core/log.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "nvs_flash.h"
#include "rtc_wdt.h"
#include "esp_rom_sys.h"
#include "esp_image_format.h"
#include <cstring>

// Upstream preferences erase all default NVS when opening its namespace fails.
// That partition contains the vendor settings required by stock recovery.
// Fail without erasing; a recovery/install procedure must handle damaged NVS.
extern "C" esp_err_t __wrap_nvs_flash_erase(void) { return ESP_ERR_NOT_SUPPORTED; }
extern "C" esp_err_t __real_nvs_flash_erase_partition(const char *partition_label);
extern "C" esp_err_t __wrap_nvs_flash_erase_partition(const char *partition_label) {
  if (!partition_label || std::strcmp(partition_label, "nvs") == 0) return ESP_ERR_NOT_SUPPORTED;
  return __real_nvs_flash_erase_partition(partition_label);
}

namespace esphome::stock_recovery {
static const char *const TAG = "stock_recovery";
static constexpr uint32_t TRIAL_MS = 900000;
// Bump both values together whenever a build needs a fresh acceptance trial.
static constexpr uint32_t ACCEPTANCE_KEY = 0x58424704;
static constexpr const char *ACCEPTANCE_NVS_KEY = "1480738564";
// Populated before ESPHome creates its loop task or initializes preferences.
// Component setup (including this component) can be skipped in safe mode.
static const esp_partition_t *early_stock;
static uint32_t early_start;
static bool early_guard_active;
// Any intact April Brother application counts as stock: the descriptor names
// the vendor project and ESP-IDF verifies the image checksum and appended
// SHA256. Returns the image length, or 0 when the partition holds no stock.
static size_t verified_stock(const esp_partition_t *partition) {
  esp_app_desc_t desc{};
  if (!partition || esp_ota_get_partition_description(partition, &desc) != ESP_OK ||
      std::strcmp(desc.project_name, "xin-ble-gateway") != 0)
    return 0;
  const esp_partition_pos_t position{partition->address, partition->size};
  esp_image_metadata_t image{};
  if (esp_image_verify(ESP_IMAGE_VERIFY_SILENT, &position, &image) != ESP_OK || !image.image_len ||
      image.image_len > partition->size)
    return 0;
  return image.image_len;
}
struct PartitionCopy {
  const esp_partition_t *source, *factory;
  size_t length;
  bool verify_source() { return verified_stock(source) == length; }
  bool select_source() { return esp_ota_set_boot_partition(source) == ESP_OK; }
  bool erase_factory() { return esp_partition_erase_range(factory, 0, factory->size) == ESP_OK; }
  bool read_source(size_t offset, uint8_t *buffer, size_t count) {
    return esp_partition_read(source, offset, buffer, count) == ESP_OK;
  }
  bool write_factory(size_t offset, const uint8_t *buffer, size_t count) {
    return esp_partition_write(factory, offset, buffer, count) == ESP_OK;
  }
  bool verify_factory() { return verified_stock(factory) == length; }
  bool select_factory() { return esp_ota_set_boot_partition(factory) == ESP_OK; }
};

static void arm_guard(uint32_t ms) {
  rtc_wdt_protect_off();
  rtc_wdt_set_length_of_reset_signal(RTC_WDT_SYS_RESET_SIG, RTC_WDT_LENGTH_3_2us);
  rtc_wdt_set_length_of_reset_signal(RTC_WDT_CPU_RESET_SIG, RTC_WDT_LENGTH_3_2us);
  rtc_wdt_set_time(RTC_WDT_STAGE0, ms);
  rtc_wdt_set_stage(RTC_WDT_STAGE0, RTC_WDT_STAGE_ACTION_RESET_SYSTEM);
  rtc_wdt_set_time(RTC_WDT_STAGE1, 1000);
  rtc_wdt_set_stage(RTC_WDT_STAGE1, RTC_WDT_STAGE_ACTION_RESET_RTC);
  rtc_wdt_set_stage(RTC_WDT_STAGE2, RTC_WDT_STAGE_ACTION_OFF);
  rtc_wdt_set_stage(RTC_WDT_STAGE3, RTC_WDT_STAGE_ACTION_OFF);
  rtc_wdt_enable();
  rtc_wdt_protect_on();
}
static void disable_guard() {
  rtc_wdt_protect_off();
  rtc_wdt_disable();
  rtc_wdt_protect_on();
}
// Returns false only when startup must not continue. Without a stock image the
// application still starts, just without the trial and restore safety net:
// halting here would leave a device that only UART flashing can recover.
bool prepare_early_recovery() {
  const auto *factory = esp_partition_find_first(ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_APP_FACTORY, nullptr);
  const auto *running = esp_ota_get_running_partition();
  if (!factory || !running || running->address == factory->address || factory->address != 0x10000) {
    esp_rom_printf("AB_RECOVERY: unsupported partition layout; starting without stock recovery\n");
    return true;
  }
  size_t length = verified_stock(factory);
  early_stock = length ? factory : nullptr;
  // Right after installation from stock, stock is still in the other OTA slot.
  for (unsigned subtype = ESP_PARTITION_SUBTYPE_APP_OTA_0;
       !early_stock && subtype <= ESP_PARTITION_SUBTYPE_APP_OTA_1; ++subtype) {
    const auto *candidate = esp_partition_find_first(ESP_PARTITION_TYPE_APP,
        static_cast<esp_partition_subtype_t>(subtype), nullptr);
    if (candidate && candidate->address != running->address && (length = verified_stock(candidate)))
      early_stock = candidate;
  }
  if (!early_stock) {
    esp_rom_printf("AB_RECOVERY: no stock image found; starting without stock recovery\n");
    return true;
  }
  if (esp_ota_set_boot_partition(early_stock) != ESP_OK) {
    esp_rom_printf("AB_RECOVERY: cannot select stock; starting without stock recovery\n");
    early_stock = nullptr;
    return true;
  }
  // Use the same clock as loop()/accept(), including its wraparound behavior.
  early_start = millis();
  arm_guard(TRIAL_MS + 10000);
  early_guard_active = true;
  esp_rom_printf("AB_RECOVERY: stock selected; trial watchdog armed before ESPHome\n");
  if (early_stock != factory) {
    // No partition-table, bootloader, NVS, running-app or nRF52832 writes.
    // Static buffer avoids exhausting IDF's small app_main task stack.
    static uint8_t buffer[4096];
    PartitionCopy ops{early_stock, factory, length};
    if (!copy_factory(ops, {running->address, running->size}, {early_stock->address, early_stock->size},
                      {factory->address, factory->size}, length, buffer)) {
      esp_rom_printf("AB_RECOVERY: factory preparation failed; returning to selected stock\n");
      arm_guard(10000);
      esp_restart();
      return false;
    }
    early_stock = factory;
    esp_rom_printf("AB_RECOVERY: stock copied to factory and verified; layout unchanged\n");
  }
  return true;
}
void StockRecovery::setup() {
  this->stock_ = early_stock;
  this->start_ = early_start;
  this->guard_active_ = early_guard_active;
  if (!this->stock_ || !this->guard_active_) {
    ESP_LOGE(TAG, "No stock image or trial guard; Accept/Restore stock unavailable");
    this->mark_failed();
    return;
  }
  // Change this key for every candidate that needs fresh acceptance testing.
  this->preference_ = global_preferences->make_preference<bool>(ACCEPTANCE_KEY);
  this->preference_.load(&this->accepted_);
  ESP_LOGI(TAG, "Stock selected for recovery; candidate accepted previously: %s", YESNO(this->accepted_));
}
bool StockRecovery::select_proxy_() {
  if (esp_ota_set_boot_partition(esp_ota_get_running_partition()) != ESP_OK) return false;
  disable_guard();
  this->guard_active_ = false;
  return true;
}
bool StockRecovery::accept() {
  if (this->is_failed() || !this->stock_ || millis() - this->start_ < 30000) return false;
  const bool accepted = true;
  if (!this->preference_.save(&accepted) || !global_preferences->sync()) {
    ESP_LOGE(TAG, "Could not persist acceptance; leaving stock fallback selected");
    return false;
  }
  if (!this->select_proxy_()) return false;
  this->accepted_ = true;
  ESP_LOGI(TAG, "ESPHome accepted; normal resets now boot the proxy");
  return true;
}
void StockRecovery::restore_stock() { this->restore_requested_ = true; }
bool StockRecovery::reset_settings() {
  // Keep the trial's recovery gate intact until the firmware has been accepted.
  if (!this->accepted_ || this->is_failed() || !this->stock_) {
    ESP_LOGE(TAG, "Settings reset unavailable before candidate acceptance");
    return false;
  }
  nvs_handle_t handle;
  // Preserve stock's own configuration for rollback, but prevent reimport after
  // this deliberate ESPHome settings reset. Commit suppression before erasing.
  if (nvs_open("ab_migration", NVS_READWRITE, &handle) != ESP_OK) return false;
  esp_err_t suppress = nvs_set_u8(handle, "reset", 1);
  if (suppress == ESP_OK) suppress = nvs_commit(handle);
  nvs_close(handle);
  if (suppress != ESP_OK) return false;
  if (nvs_open("esphome", NVS_READWRITE, &handle) != ESP_OK) return false;
  esp_err_t err = nvs_erase_all(handle);
  // The trial acceptance marker is firmware safety metadata, not user settings.
  const bool accepted = true;
  if (err == ESP_OK) err = nvs_set_blob(handle, ACCEPTANCE_NVS_KEY, &accepted, sizeof(accepted));
  if (err == ESP_OK) err = nvs_commit(handle);
  nvs_close(handle);
  if (err != ESP_OK || !this->select_proxy_()) {
    ESP_LOGE(TAG, "Settings reset failed; stock fallback retained");
    return false;
  }
  // Direct restart avoids shutdown hooks restoring preferences we just erased.
  esp_restart();
  return true;
}
void StockRecovery::loop() {
  if (this->is_failed()) return;
  if (this->restore_requested_ || (this->guard_active_ && millis() - this->start_ >= TRIAL_MS)) {
    arm_guard(10000);
    if (esp_ota_set_boot_partition(this->stock_) == ESP_OK) {
      ESP_LOGW(TAG, "Returning to stock firmware");
      esp_restart();
    }
    ESP_LOGE(TAG, "Could not select stock; reset guard remains armed");
    return;
  }
  // A previously accepted build becomes persistent after one minute of a
  // working main loop. HA/broker outages must not force a return to stock.
  if (this->accepted_ && this->guard_active_ && millis() - this->start_ >= 60000) {
    if (!this->select_proxy_()) this->restore_requested_ = true;
  }
}
void StockRecovery::dump_config() {
  ESP_LOGCONFIG(TAG, "Stock recovery: %s; RTC trial guard: %s", this->stock_ ? "present" : "missing",
                YESNO(this->guard_active_));
}
}  // namespace esphome::stock_recovery

extern "C" void __real_app_main();
extern "C" void __wrap_app_main() {
  // IDF startup has completed, but ESPHome preferences, safe mode, network and
  // BLE setup have not begun. This does not cover faults before app_main.
  if (esphome::stock_recovery::prepare_early_recovery()) __real_app_main();
}
