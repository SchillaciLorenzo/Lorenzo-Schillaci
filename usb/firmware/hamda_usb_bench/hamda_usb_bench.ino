// EXPERIMENTAL BENCH ONLY: no flash or electrical validation is implied.
#include <Arduino.h>
#include <driver/gpio.h>
#include <esp_mac.h>
#include <string.h>

#include "src/bench_core.h"

#if !defined(CONFIG_IDF_TARGET_ESP32C3)
#error "This bench adapter requires ESP32-C3."
#endif
#if !defined(ARDUINO_USB_MODE) || ARDUINO_USB_MODE != 1 || \
    !defined(ARDUINO_USB_CDC_ON_BOOT) || ARDUINO_USB_CDC_ON_BOOT != 1
#error "Use native C3 HWCDC: USB mode 1 and CDCOnBoot=cdc."
#endif

namespace {

class EspClock : public hamda::Clock {
 public:
  uint32_t now_ms() const override { return millis(); }
};

class EspGpio : public hamda::Gpio {
 public:
  bool prepare_low(uint8_t pin) override {
    // Use IDF's latch API: Arduino digitalWrite before pinMode is not assumed
    // to initialize a previously unowned GPIO in Arduino-ESP32 3.x.
    const gpio_num_t gpio = static_cast<gpio_num_t>(pin);
    if (gpio_set_level(gpio, 0) != ESP_OK) return false;
    return gpio_set_direction(gpio, GPIO_MODE_OUTPUT) == ESP_OK;
  }
  bool write(uint8_t pin, bool high) override {
    return gpio_set_level(static_cast<gpio_num_t>(pin), high ? 1 : 0) == ESP_OK;
  }
};

EspClock bench_clock;
EspGpio bench_gpio;
hamda::Controller* controller = nullptr;
constexpr size_t kRxBudget = 64;

}  // namespace

void setup() {
  uint8_t mac[6] = {0};
  // eFuse base MAC; no Wi-Fi initialization, network access or guessed ID.
  if (esp_efuse_mac_get_default(mac) != ESP_OK) memset(mac, 0, sizeof(mac));
  static hamda::Controller instance(mac, bench_clock, bench_gpio);
  controller = &instance;
  controller->begin();  // Known-profile LOW latches/directions BEFORE Serial.

  Serial.begin(115200);  // Native USB ignores this value for USB line speed.
  // Required core-3.x HWCDC API. If unavailable, compilation must fail rather
  // than silently introduce an unbounded write. Real 3.3.13 build still needed.
  Serial.setTxTimeoutMs(0);
  // No while (!Serial), print, flush, delay or automatic motor activation.
}

void loop() {
  controller->tick();
  hamda::pump_rx(*controller, Serial, kRxBudget);
  controller->tick();
  hamda::pump_tx_when_off(*controller, Serial);
  controller->tick();
}
