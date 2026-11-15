#include "ab_settings.h"
#include "esphome/components/wifi/wifi_component.h"
#include "esphome/core/preferences.h"
#include "esphome/core/log.h"
#include "nvs.h"
#include <cstring>

namespace esphome::ab_settings {
static const char *const TAG = "ab_settings";
static bool read_string(nvs_handle_t h, const char *key, char *out, size_t capacity) {
  size_t size = capacity;
  const auto err = nvs_get_str(h, key, out, &size);
  if (err != ESP_OK || size == 0 || size > capacity || out[size - 1] != '\0') {
    memset(out, 0, capacity);
    return false;
  }
  return true;
}
static bool restore_migration_feed() {
  // Only undo our installer's temporary feed. Other custom vendor feeds stay
  // untouched, and this never changes credentials or the Nordic firmware.
  nvs_handle_t handle;
  if (nvs_open("storage", NVS_READONLY, &handle) != ESP_OK) return true;
  char url[192]{};
  const bool ours = read_string(handle, "ota-url", url, sizeof(url)) &&
                    std::strstr(url, "/esphome-migration/") != nullptr;
  nvs_close(handle);
  if (!ours) return true;
  if (nvs_open("storage", NVS_READWRITE, &handle) != ESP_OK) return false;
  static constexpr const char *FEED = "http://ota.bconimg.com/gw4";
  const bool restored = nvs_set_str(handle, "ota-url", FEED) == ESP_OK && nvs_commit(handle) == ESP_OK &&
                        read_string(handle, "ota-url", url, sizeof(url)) && !std::strcmp(url, FEED);
  nvs_close(handle);
  return restored;
}
void AbSettings::setup() {
  if (!restore_migration_feed()) {
    ESP_LOGE(TAG, "Could not restore the stock update feed");
    mark_failed();
    return;
  }
  // A deliberate settings reset must not silently resurrect stock credentials.
  nvs_handle_t state;
  uint8_t reset = 0;
  auto err = nvs_open("ab_migration", NVS_READONLY, &state);
  if (err == ESP_OK) {
    err = nvs_get_u8(state, "reset", &reset);
    nvs_close(state);
    if (err != ESP_OK && err != ESP_ERR_NVS_NOT_FOUND) reset = 1;
  } else if (err != ESP_ERR_NVS_NOT_FOUND) reset = 1;
  if (reset) {
    ESP_LOGI(TAG, "Settings were reset; stock import disabled, Wi-Fi provisioning required");
    return;
  }
  nvs_handle_t stock;
  if (nvs_open("storage", NVS_READONLY, &stock) != ESP_OK) {
    ESP_LOGW(TAG, "No stock settings; provision Wi-Fi over Improv serial");
    return;
  }
  // This hash is ESPHome's stable preference key when YAML has no STA network.
  // Keep YAML free of credentials; a configured network selects a different key.
  auto pref = global_preferences->make_preference<wifi::SavedWifiSettings>(88491487UL, true);
  wifi::SavedWifiSettings saved{};
  if (!pref.load(&saved)) {
    uint8_t wifi_type = 255;
    nvs_get_u8(stock, "wifi-type", &wifi_type);
    // Stock config tool: 0 = personal Wi-Fi; enterprise needs a separate path.
    if (wifi_type == 0 && read_string(stock, "ssid", saved.ssid, sizeof(saved.ssid)) &&
        saved.ssid[0] && read_string(stock, "passcode", saved.password, sizeof(saved.password))) {
      if (!pref.save(&saved) || !global_preferences->sync()) {
        ESP_LOGE(TAG, "Could not persist imported Wi-Fi settings");
        mark_failed();
      } else {
        ESP_LOGI(TAG, "Imported saved Wi-Fi settings from stock NVS");
      }
    } else {
      ESP_LOGW(TAG, "No supported stock Wi-Fi credentials; provisioning required");
    }
  }
  memset(&saved, 0, sizeof(saved));

  nvs_close(stock);
}
}
