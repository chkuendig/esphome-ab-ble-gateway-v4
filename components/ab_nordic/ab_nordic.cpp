#include "ab_nordic.h"
#include "esphome/components/mqtt/mqtt_client.h"
#include "esphome/core/log.h"
#include "esp_mac.h"

namespace esphome::ab_nordic {
static const char *const TAG = "ab_nordic";
void AbNordic::setup() {
  if (esp_read_mac(this->source_, ESP_MAC_WIFI_STA) != ESP_OK) { mark_failed(); return; }
  this->write_str("AT+SCAN0\r\n");
  this->start_time_ = millis();
}
void AbNordic::loop() {
  const uint32_t now = millis();
  if (this->start_stage_ < 2) {
    if (now - this->start_time_ >= 100) {
      this->write_str(this->start_stage_ == 0 ? "AT+ACT0\r\n" : "AT+SCAN2\r\n");
      this->start_time_ = now;
      this->start_stage_++;
    }
  }
  uint8_t byte;
  xbg_ad ad;
  char line[160];
  // Yield frequently to Wi-Fi, ESP32 BLE, the encrypted API and OTA.
  for (unsigned i = 0; i < 2048 && this->available(); i++) {
    if (!this->read_byte(&byte)) break;
    if (xbg_feed(&this->parser_, byte, &ad, line, sizeof(line)) == XBG_AD) {
      this->adverts_++;
      if (this->count_ < 128) this->batch_[this->count_++] = ad;
      else this->dropped_++;
    }
  }
  if (now - this->last_publish_ >= 1000) {
    this->last_publish_ = now;
    if (this->count_) {
      const size_t n = xbg_pack(this->packet_, sizeof(this->packet_), this->source_,
                              this->message_id_++, now / 1000, this->batch_, this->count_);
      auto *client = mqtt::global_mqtt_client;
      if (!n || this->topic_.empty() || !client || !client->is_connected() ||
          !client->publish(this->topic_, reinterpret_cast<const char *>(this->packet_), n, 0, false))
        this->dropped_ += this->count_;
      this->count_ = 0;
    }
  }
  if (now - this->last_stats_ >= 60000) {
    this->last_stats_ = now;
    ESP_LOGI(TAG, "Nordic adverts=%u dropped=%u malformed=%u",
             static_cast<unsigned>(this->adverts_), static_cast<unsigned>(this->dropped_),
             static_cast<unsigned>(this->parser_.malformed));
  }
}
void AbNordic::dump_config() {
  ESP_LOGCONFIG(TAG, "April Brother Nordic scanner: RX32 TX33, passive, device-configured MQTT topic");
}
}  // namespace esphome::ab_nordic
