#include "ab_button.h"
#include "esphome/components/wifi/wifi_component.h"
#include "esphome/core/log.h"
#include "driver/gpio.h"
#include "esp_smartconfig.h"
#include "esp_wifi.h"
#include <cstring>

namespace esphome::ab_button {
static const char *const TAG = "ab_button";
void AbButton::setup() {
  gpio_config_t config{};
  config.pin_bit_mask = 1ULL << 12;
  config.mode = GPIO_MODE_INPUT;
  config.pull_up_en = GPIO_PULLUP_ENABLE;
  if (gpio_config(&config) != ESP_OK) { mark_failed(); return; }
  events_ = xQueueCreate(4, sizeof(Event));
  if (!events_ || esp_event_handler_instance_register(SC_EVENT, ESP_EVENT_ANY_ID,
      on_smartconfig_, this, &handler_) != ESP_OK) { mark_failed(); return; }
  gesture_.update(gpio_get_level(GPIO_NUM_12) == 0, millis());
}
void AbButton::on_smartconfig_(void *arg, esp_event_base_t, int32_t id, void *data) {
  auto *self = static_cast<AbButton *>(arg);
  Event event{};
  event.type = id;
  if (id == SC_EVENT_GOT_SSID_PSWD) {
    auto *received = static_cast<smartconfig_event_got_ssid_pswd_t *>(data);
    memcpy(event.ssid, received->ssid, 32);
    memcpy(event.password, received->password, 64);
  } else if (id != SC_EVENT_SEND_ACK_DONE) return;
  // All Wi-Fi and preferences changes occur in the main loop, never IDF's callback.
  xQueueSend(self->events_, &event, 0);
}
void AbButton::start_smartconfig_() {
  if (provisioning_) return;
  xQueueReset(events_);
  wifi::global_wifi_component->disable();
  esp_err_t error = esp_wifi_set_mode(WIFI_MODE_STA);
  if (error == ESP_OK) error = esp_wifi_start();
  if (error == ESP_OK) error = esp_smartconfig_set_type(SC_TYPE_ESPTOUCH_AIRKISS);
  smartconfig_start_config_t config = SMARTCONFIG_START_CONFIG_DEFAULT();
  if (error == ESP_OK) error = esp_smartconfig_start(&config);
  if (error != ESP_OK) {
    ESP_LOGE(TAG, "SmartConfig start failed: %s", esp_err_to_name(error));
    esp_wifi_stop();
    wifi::global_wifi_component->clear_sta();
    wifi::global_wifi_component->enable();
    return;
  }
  provisioning_ = true;
  credentials_applied_ = false;
  provision_started_ = millis();
  ESP_LOGI(TAG, "Wi-Fi SmartConfig started; existing settings retained until credentials arrive");
}
void AbButton::stop_smartconfig_() {
  if (!provisioning_) return;
  esp_smartconfig_stop();
  provisioning_ = false;
  if (!credentials_applied_) {
    esp_wifi_stop();
    wifi::global_wifi_component->clear_sta();
    wifi::global_wifi_component->enable();
  }
}
void AbButton::loop() {
  const uint32_t now = millis();
  if (reset_pending_) {
    if (uint32_t(now - reset_started_) >= 2010) {
      reset_pending_ = false;
      recovery_->reset_settings();
    }
    return;
  }
  const Action action = gesture_.update(gpio_get_level(GPIO_NUM_12) == 0, now);
  if (action == Action::RESET_SETTINGS) {
    stop_smartconfig_();
    reset_pending_ = true;
    reset_started_ = now;
    ESP_LOGW(TAG, "10-second hold: reset saved ESPHome settings and restart");
  } else if (action == Action::SMARTCONFIG) start_smartconfig_();

  Event event{};
  while (xQueueReceive(events_, &event, 0) == pdTRUE) {
    if (provisioning_ && event.type == SC_EVENT_GOT_SSID_PSWD && event.ssid[0]) {
      // disable/enable calls start() again; once a runtime STA is present,
      // start() changes its preference hash. Persist the credential-free YAML's
      // stable boot key explicitly, including after repeated provisioning.
      wifi::SavedWifiSettings saved{};
      memcpy(saved.ssid, event.ssid, sizeof(saved.ssid));
      memcpy(saved.password, event.password, sizeof(saved.password));
      auto pref = global_preferences->make_preference<wifi::SavedWifiSettings>(88491487UL, true);
      const bool persisted = pref.save(&saved) && global_preferences->sync();
      memset(&saved, 0, sizeof(saved));
      if (!persisted) {
        ESP_LOGE(TAG, "Could not save SmartConfig credentials");
        memset(&event, 0, sizeof(event));
        stop_smartconfig_();
        continue;
      }
      // Clear in-memory STAs before start(), so it reloads that same boot key.
      wifi::global_wifi_component->clear_sta();
      credentials_applied_ = true;
      wifi::global_wifi_component->enable();
      ESP_LOGI(TAG, "SmartConfig credentials received; connecting");
    } else if (provisioning_ && event.type == SC_EVENT_SEND_ACK_DONE) {
      stop_smartconfig_();
      ESP_LOGI(TAG, "SmartConfig completed");
    }
    memset(&event, 0, sizeof(event));
  }
  // A bounded provisioning session must not strand the gateway indefinitely.
  if (provisioning_ && uint32_t(now - provision_started_) >= 180000) {
    stop_smartconfig_();
    ESP_LOGW(TAG, "SmartConfig session ended after three minutes");
  }
}
void AbButton::dump_config() {
  ESP_LOGCONFIG(TAG, "GPIO12: hold 10s resets settings; triple-click starts Wi-Fi SmartConfig");
}
}
