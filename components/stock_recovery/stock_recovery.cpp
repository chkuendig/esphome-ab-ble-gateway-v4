#include "stock_recovery.h"
#include "copy.h"
#include "esphome/core/log.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "nvs_flash.h"
#include "rtc_wdt.h"
#include "esp_rom_sys.h"
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
// Populated before ESPHome creates its loop task or initializes preferences.
// Component setup (including this component) can be skipped in safe mode.
static const esp_partition_t *early_stock;
static uint32_t early_start;
static bool early_guard_active;
static constexpr size_t STOCK_SIZE = 944400;
// The verified image's appended SHA256 (excludes the appended hash itself).
static constexpr uint8_t STOCK_DIGEST[32] = {
  0xd2, 0x3a, 0x91, 0xdc, 0x28, 0x19, 0x1a, 0x12, 0x17, 0xc0, 0x33, 0x3e, 0x45, 0x03, 0x03, 0xfc,
  0x26, 0xa5, 0x67, 0x75, 0x5b, 0x51, 0xff, 0x6f, 0x0d, 0xb6, 0xc6, 0x67, 0x5d, 0x1b, 0x76, 0x4a
};
static bool verified_stock(const esp_partition_t *partition) {
  esp_app_desc_t desc{};
  uint8_t digest[32];
  return partition && partition->size >= STOCK_SIZE &&
    esp_ota_get_partition_description(partition, &desc) == ESP_OK &&
    !std::strcmp(desc.project_name, "xin-ble-gateway") &&
    !std::strcmp(desc.version, "v1.5.12-3-gdb55502-dirty") &&
    esp_partition_get_sha256(partition, digest) == ESP_OK && !std::memcmp(digest, STOCK_DIGEST, sizeof(digest));
}
struct PartitionCopy {
  const esp_partition_t *source, *factory;
  bool verify_source() { return verified_stock(source); }
  bool select_source() { return esp_ota_set_boot_partition(source) == ESP_OK; }
  bool erase_factory() { return esp_partition_erase_range(factory, 0, factory->size) == ESP_OK; }
  bool read_source(size_t offset, uint8_t *buffer, size_t count) {
    return esp_partition_read(source, offset, buffer, count) == ESP_OK;
  }
  bool write_factory(size_t offset, const uint8_t *buffer, size_t count) {
    return esp_partition_write(factory, offset, buffer, count) == ESP_OK;
  }
  bool verify_factory() { return verified_stock(factory); }
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
bool prepare_early_recovery() {
  const auto *factory = esp_partition_find_first(ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_APP_FACTORY, nullptr);
  const auto *running = esp_ota_get_running_partition();
  if (!factory || !running || running->address == factory->address || factory->address != 0x10000) return false;
  early_stock = verified_stock(factory) ? factory : nullptr;
  // On the original layout, current stock is still in the other OTA slot.
  for (unsigned subtype = ESP_PARTITION_SUBTYPE_APP_OTA_0;
       !early_stock && subtype <= ESP_PARTITION_SUBTYPE_APP_OTA_1; ++subtype) {
    const auto *candidate = esp_partition_find_first(ESP_PARTITION_TYPE_APP,
        static_cast<esp_partition_subtype_t>(subtype), nullptr);
    if (candidate && candidate->address != running->address && verified_stock(candidate)) early_stock = candidate;
  }
  if (!early_stock) {
    esp_rom_printf("AB_RECOVERY: expected stock image missing; startup stopped\n");
    early_stock = nullptr;
    return false;
  }
  if (esp_ota_set_boot_partition(early_stock) != ESP_OK) {
    esp_rom_printf("AB_RECOVERY: cannot select stock; startup stopped\n");
    return false;
  }
  // Use the same clock as loop()/accept(), including its wraparound behavior.
  early_start = millis();
  arm_guard(TRIAL_MS + 10000);
  early_guard_active = true;
  esp_rom_printf("AB_RECOVERY: stock selected; trial watchdog armed before ESPHome\n");
  if (early_stock != factory) {
    // No partition-table, bootloader, NVS, running-app or Nordic writes.
    // Static buffer avoids exhausting IDF's small app_main task stack.
    static uint8_t buffer[4096];
    PartitionCopy ops{early_stock, factory};
    if (!copy_factory(ops, {running->address, running->size}, {early_stock->address, early_stock->size},
                      {factory->address, factory->size}, STOCK_SIZE, buffer)) {
      esp_rom_printf("AB_RECOVERY: factory preparation failed; returning to selected stock\n");
      arm_guard(10000);
      esp_restart();
      return false;
    }
    early_stock = factory;
    esp_rom_printf("AB_RECOVERY: verified current stock copied to factory; layout unchanged\n");
  }
  return true;
}
void StockRecovery::setup() {
  this->stock_ = early_stock;
  this->start_ = early_start;
  this->guard_active_ = early_guard_active;
  if (!this->stock_ || !this->guard_active_) {
    ESP_LOGE(TAG, "Early recovery guard unavailable");
    this->mark_failed();
    return;
  }
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

extern "C" void __real_app_main();
extern "C" void __wrap_app_main() {
  // IDF startup has completed, but ESPHome preferences, safe mode, network and
  // BLE setup have not begun. This does not cover faults before app_main.
  if (esphome::stock_recovery::prepare_early_recovery()) __real_app_main();
}
