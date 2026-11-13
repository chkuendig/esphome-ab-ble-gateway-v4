#include "stock_recovery.h"
#include "esphome/core/log.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "nvs_flash.h"
#include "rtc_wdt.h"
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
void StockRecovery::setup() {
  this->stock_ = esp_partition_find_first(ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_APP_FACTORY, nullptr);
  esp_app_desc_t desc{};
  if (!this->stock_ || this->stock_->address != 0x10000 ||
      esp_ota_get_partition_description(this->stock_, &desc) != ESP_OK ||
      std::strcmp(desc.project_name, "xin-ble-gateway") ||
      std::strcmp(desc.version, "v1.5.12-3-gdb55502-dirty")) {
    ESP_LOGE(TAG, "Expected stock 1.5.13 recovery image missing; candidate is not accepted");
    this->stock_ = nullptr;
    this->mark_failed();
    return;
  }
  if (esp_ota_set_boot_partition(this->stock_) != ESP_OK) {
    ESP_LOGE(TAG, "Could not validate/select stock recovery");
    this->mark_failed();
    return;
  }
  this->start_ = millis();
  arm_guard(TRIAL_MS + 10000);
  this->guard_active_ = true;
  // Change this key for every candidate that needs fresh acceptance testing.
  this->preference_ = global_preferences->make_preference<bool>(0x58424701);
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
  if (err == ESP_OK) err = nvs_set_blob(handle, "1480738561", &accepted, sizeof(accepted));
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
