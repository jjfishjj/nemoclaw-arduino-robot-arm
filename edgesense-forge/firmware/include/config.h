#pragma once

// Prototype placeholders only. Do not commit production credentials.
#define WIFI_SSID "CHANGE_ME_WIFI"
#define WIFI_PASSWORD "CHANGE_ME_PASSWORD"

#define MQTT_HOST "192.168.1.10"
#define MQTT_PORT 1883
#define MQTT_USER ""
#define MQTT_PASSWORD ""

#define DEVICE_ID "motor-01"
#define TELEMETRY_TOPIC "edgesense/v1/" DEVICE_ID "/telemetry"
#define STATUS_TOPIC "edgesense/v1/" DEVICE_ID "/status"

#define SAMPLE_RATE_HZ 100
#define PUBLISH_INTERVAL_MS 1000
