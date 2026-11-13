#include "ab_settings.h"
#include "esphome/components/wifi/wifi_component.h"
#include "esphome/components/mqtt/mqtt_client.h"
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
void AbSettings::setup() {
  auto *client = mqtt::global_mqtt_client;
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
    client->mark_failed();
    ESP_LOGI(TAG, "Settings were reset; stock import disabled, Wi-Fi provisioning required");
    return;
  }
  nvs_handle_t stock;
  if (nvs_open("storage", NVS_READONLY, &stock) != ESP_OK) {
    client->mark_failed();
    ESP_LOGW(TAG, "No stock settings; provision Wi-Fi using the configuration button");
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
      } else ESP_LOGI(TAG, "Imported saved Wi-Fi settings from stock NVS");
    } else ESP_LOGW(TAG, "No supported stock Wi-Fi credentials; provisioning required");
  }
  memset(&saved, 0, sizeof(saved));

  char host[256]{}, username[128]{}, password[128]{}, topic[256]{};
  uint32_t port = 0;
  uint8_t tls = 0;
  nvs_get_u8(stock, "mqtts", &tls);
  nvs_get_u32(stock, "mqtt-port", &port);
  bool supported = read_string(stock, "mqtt-host", host, sizeof(host)) && host[0] &&
      read_string(stock, "mqtt-topic", topic, sizeof(topic)) && topic[0] &&
      port > 0 && port <= 65535 && tls == 0;
  if (supported) {
    // Empty credentials are valid; missing keys mean anonymous authentication.
    auto user_ok = read_string(stock, "mqtt-username", username, sizeof(username));
    auto pass_ok = read_string(stock, "mqtt-password", password, sizeof(password));
    if (!user_ok || !pass_ok) supported = false;
  }
  if (supported) {
    client->set_broker_address(host);
    client->set_broker_port(port);
    client->set_username(username);
    client->set_password(password);
    nordic_->set_topic(topic);
    ESP_LOGI(TAG, "Configured Nordic MQTT transport from stock NVS");
  } else {
    client->mark_failed();
    ESP_LOGW(TAG, "Stock MQTT settings unsupported or absent; MQTT transport disabled");
  }
  memset(password, 0, sizeof(password));
  nvs_close(stock);
}
}
