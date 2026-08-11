#include <Arduino.h>
#include <Adafruit_BME280.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <Wire.h>
#include <math.h>
#include <time.h>

#include "config.h"

namespace {
constexpr uint8_t SDA_PIN = 21;
constexpr uint8_t SCL_PIN = 22;
constexpr uint16_t MQTT_BUFFER_SIZE = 512;
constexpr unsigned long WIFI_RETRY_MS = 10000;
constexpr unsigned long MQTT_RETRY_MS = 5000;

Adafruit_BME280 bme;
Adafruit_MPU6050 mpu;
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

unsigned long lastPublish = 0;
unsigned long lastWifiAttempt = 0;
unsigned long lastMqttAttempt = 0;
bool sensorsReady = false;

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  const unsigned long now = millis();
  if (lastWifiAttempt != 0 && now - lastWifiAttempt < WIFI_RETRY_MS) return;
  lastWifiAttempt = now;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.println("Wi-Fi connection requested");
}

void publishStatus(const char* status, bool retained = true) {
  JsonDocument document;
  document["schema_version"] = "1.0";
  document["device_id"] = DEVICE_ID;
  document["status"] = status;
  char payload[192];
  const size_t length = serializeJson(document, payload, sizeof(payload));
  mqtt.publish(STATUS_TOPIC, reinterpret_cast<const uint8_t*>(payload), length, retained);
}

void connectMqtt() {
  if (mqtt.connected() || WiFi.status() != WL_CONNECTED) return;
  const unsigned long now = millis();
  if (lastMqttAttempt != 0 && now - lastMqttAttempt < MQTT_RETRY_MS) return;
  lastMqttAttempt = now;

  const String clientId = String("edgesense-") + DEVICE_ID + "-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  const char* willPayload = "{\"schema_version\":\"1.0\",\"device_id\":\"" DEVICE_ID "\",\"status\":\"offline\"}";
  const bool connected = strlen(MQTT_USER) > 0
      ? mqtt.connect(clientId.c_str(), MQTT_USER, MQTT_PASSWORD, STATUS_TOPIC, 0, true, willPayload)
      : mqtt.connect(clientId.c_str(), STATUS_TOPIC, 0, true, willPayload);
  if (connected) {
    Serial.println("MQTT connected");
    publishStatus("online");
  }
}

float sampleAccelerationRms() {
  constexpr int sampleCount = 20;
  double sumSquares = 0.0;
  for (int index = 0; index < sampleCount; ++index) {
    sensors_event_t acceleration;
    sensors_event_t gyro;
    sensors_event_t temperature;
    mpu.getEvent(&acceleration, &gyro, &temperature);
    const double magnitude = sqrt(
        acceleration.acceleration.x * acceleration.acceleration.x +
        acceleration.acceleration.y * acceleration.acceleration.y +
        acceleration.acceleration.z * acceleration.acceleration.z);
    const double dynamicG = (magnitude / SENSORS_GRAVITY_STANDARD) - 1.0;
    sumSquares += dynamicG * dynamicG;
    delayMicroseconds(1000000UL / SAMPLE_RATE_HZ);
  }
  return static_cast<float>(sqrt(sumSquares / sampleCount));
}

String isoTimestamp() {
  struct tm timeInfo;
  if (!getLocalTime(&timeInfo, 50)) return "1970-01-01T00:00:00Z";
  char buffer[25];
  strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &timeInfo);
  return String(buffer);
}

void publishTelemetry() {
  if (!sensorsReady || !mqtt.connected()) return;
  const float temperature = bme.readTemperature();
  const float vibrationRms = sampleAccelerationRms();
  if (isnan(temperature) || isnan(vibrationRms)) {
    Serial.println("Sensor reading invalid");
    return;
  }

  JsonDocument document;
  document["schema_version"] = "1.0";
  document["device_id"] = DEVICE_ID;
  document["ts"] = isoTimestamp();
  document["temperature_c"] = serialized(String(temperature, 2));
  document["accel_rms_g"] = serialized(String(vibrationRms, 4));
  document["sample_rate_hz"] = SAMPLE_RATE_HZ;

  char payload[MQTT_BUFFER_SIZE];
  const size_t length = serializeJson(document, payload, sizeof(payload));
  if (mqtt.publish(TELEMETRY_TOPIC, reinterpret_cast<const uint8_t*>(payload), length, false)) {
    Serial.printf("Published %s\n", payload);
  } else {
    Serial.println("MQTT publish failed");
  }
}
}  // namespace

void setup() {
  Serial.begin(115200);
  Wire.begin(SDA_PIN, SCL_PIN);

  const bool bmeReady = bme.begin(0x76) || bme.begin(0x77);
  const bool mpuReady = mpu.begin();
  sensorsReady = bmeReady && mpuReady;
  if (!sensorsReady) {
    Serial.printf("Sensor init failed: BME280=%d MPU6050=%d\n", bmeReady, mpuReady);
  }

  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(MQTT_BUFFER_SIZE);
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  connectWifi();
}

void loop() {
  connectWifi();
  connectMqtt();
  mqtt.loop();

  const unsigned long now = millis();
  if (now - lastPublish >= PUBLISH_INTERVAL_MS) {
    lastPublish = now;
    publishTelemetry();
  }
  delay(5);
}
