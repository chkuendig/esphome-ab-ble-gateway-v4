#include "ab_nordic.h"
#include "esphome/core/log.h"
#include "esp_gattc_api.h"
#include <cstring>

namespace esphome::ab_nordic {
static const char *const TAG = "ab_nordic";
#ifdef AB_NORDIC_SERIAL_DIAGNOSTICS
// SCAN0 restarts Nordic's scanner. A 100 ms restart sequence loses the later
// commands; the stock firmware waits ~510 ms. Live UART A/B verified 600 ms.
static constexpr uint32_t SCAN_COMMAND_DELAY_MS = 600;
#else
static constexpr uint32_t SCAN_COMMAND_DELAY_MS = 100;
#endif
static AbNordic *gateway;
void AbNordic::setup() {
  gateway = this;
  // This callback receives only the ESP32's actual scan results; Nordic UART
  // data is sent directly to the subscribed API connection, never fed here.
  this->proxy_->set_advertisement_filter({this, [](void *self, const ble_device_base::RawAdvertisement &ad) {
    static_cast<AbNordic *>(self)->types_.observe(ad.address, ad.addr_type, millis());
    return true;  // Keep normal ESP32 native proxy delivery unchanged.
  }});
  this->write_str("AT+SCAN0\r\n");
  this->start_time_ = millis();
}
void AbNordic::loop() {
  const uint32_t now = millis();
#ifdef AB_NORDIC_SERIAL_DIAGNOSTICS
  if (this->diagnostics_loop_(now)) return;
#endif
  if (this->start_stage_ < 2) {
    if (now - this->start_time_ >= SCAN_COMMAND_DELAY_MS) {
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
      this->queue_(ad);
    }
  }
  if (now - this->last_publish_ >= 250) {
    this->last_publish_ = now;
    this->flush_();
  }
  if (now - this->last_stats_ >= 60000) {
    this->last_stats_ = now;
    ESP_LOGI(TAG, "Nordic adverts=%u dropped=%u unknown_type=%u malformed=%u",
             static_cast<unsigned>(this->adverts_), static_cast<unsigned>(this->dropped_),
             static_cast<unsigned>(this->unknown_type_),
             static_cast<unsigned>(this->parser_.malformed));
  }
}
#ifdef AB_NORDIC_SERIAL_DIAGNOSTICS
bool AbNordic::begin_diagnostics() {
  if (!this->serial_ || this->start_stage_ < 2 || !this->lease_.begin(millis())) return false;
  // The supported client arms before subscribing. Do not inject bytes if a raw
  // subscriber already owns the wire; that client controls scan pause itself.
  if (!this->serial_->get_api_connection()) this->write_str("AT+SCAN0\r\n");
  this->dropped_ += this->batch_.advertisements_len;
  this->batch_.advertisements_len = 0;
  this->parser_ = {};
  return true;
}
bool AbNordic::diagnostics_loop_(uint32_t now) {
  if (!this->serial_) return false;
  auto *owner = this->serial_->get_api_connection();
  // Also yield immediately to third-party subscribers. The supplied client
  // always arms first, so even a subscribe/unsubscribe within one loop pass
  // has a timeout and cannot leave scanning stopped indefinitely.
  if (owner && !this->lease_.active()) this->lease_.begin(now);
  if (this->lease_.finished(now, owner != nullptr)) {
    if (owner) this->serial_->serial_proxy_request(owner, api::enums::SERIAL_PROXY_REQUEST_TYPE_UNSUBSCRIBE);
    this->resume_scanning_(now);
    return true;
  }
  return this->lease_.active() || owner != nullptr;
}
void AbNordic::resume_scanning_(uint32_t now) {
  // Restore host framing only; diagnostic clients must not change Nordic's
  // persistent baud/firmware/configuration. No reset/DFU/SWD pins are driven.
  this->parent_->set_baud_rate(115200);
  this->parent_->set_data_bits(8);
  this->parent_->set_stop_bits(1);
  this->parent_->set_parity(uart::UART_CONFIG_PARITY_NONE);
  this->parent_->load_settings(false);
  uint8_t discard;
  for (unsigned i = 0; i < 4096 && this->available(); ++i) this->read_byte(&discard);
  this->parser_ = {};
  this->dropped_ += this->batch_.advertisements_len;
  this->batch_.advertisements_len = 0;
  this->write_str("\r\nAT+SCAN0\r\n");
  this->start_stage_ = 0;
  this->start_time_ = now;
}
#endif
void AbNordic::queue_(const xbg_ad &ad) {
  auto *client = this->proxy_->get_api_connection();
  if (client != this->batch_client_) {
    this->dropped_ += this->batch_.advertisements_len;
    this->batch_.advertisements_len = 0;
    this->batch_client_ = client;
  }
  if (!client || ad.len < 8 || ad.len > XBG_MAX_RECORD) { this->dropped_++; return; }
  auto &out = this->batch_.advertisements[this->batch_.advertisements_len];
  out.address = address_from_bytes(ad.data + 1);
  out.rssi = static_cast<int8_t>(ad.data[7]);
  out.address_type = this->address_type(out.address);
  if (out.address_type == UNKNOWN_ADDRESS_TYPE) this->unknown_type_++;
  out.data_len = ad.len - 8;
  std::memcpy(out.data, ad.data + 8, out.data_len);
  this->batch_.advertisements_len++;
  if (this->batch_.advertisements_len == this->batch_.advertisements.size()) this->flush_();
}
void AbNordic::flush_() {
  if (!this->batch_.advertisements_len) return;
  auto *client = this->proxy_->get_api_connection();
  if (!client || client != this->batch_client_ || !client->send_message(this->batch_))
    this->dropped_ += this->batch_.advertisements_len;
  // Bound memory and latency under network backpressure. Never retry stale
  // advertisements or block Wi-Fi, OTA, the ESP32 scan loop or a GATT read.
  this->batch_.advertisements_len = 0;
}
void AbNordic::dump_config() {
  ESP_LOGCONFIG(TAG, "Nordic passive receiver: RX32 TX33, native encrypted Bluetooth API");
}
}  // namespace esphome::ab_nordic

extern "C" esp_err_t __real_esp_ble_gattc_open(esp_gatt_if_t, esp_bd_addr_t, esp_ble_addr_type_t, bool);
extern "C" esp_err_t __wrap_esp_ble_gattc_open(esp_gatt_if_t interface, esp_bd_addr_t address,
                                             esp_ble_addr_type_t type, bool direct) {
  using namespace esphome::ab_nordic;
  if (!address) return ESP_ERR_INVALID_ARG;
  if (static_cast<unsigned>(type) > 3) {
    // The native HA API preserves our unknown type. A connection may proceed
    // only after the ESP32 independently learned the real type. Rejection uses
    // upstream ESPHome's open-error path, which frees the slot and reports it.
    const uint8_t observed = resolve_address_type(static_cast<unsigned>(type),
        gateway ? gateway->address_type(address_from_bytes(address)) : UNKNOWN_ADDRESS_TYPE);
    if (observed == UNKNOWN_ADDRESS_TYPE) return ESP_ERR_INVALID_ARG;
    type = static_cast<esp_ble_addr_type_t>(observed);
  }
  return __real_esp_ble_gattc_open(interface, address, type, direct);
}
