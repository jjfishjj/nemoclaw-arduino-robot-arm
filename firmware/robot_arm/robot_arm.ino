#include <ArduinoJson.h>
#include <Servo.h>

Servo servos[4];
const uint8_t PINS[4] = {3, 5, 6, 9};
const char* NAMES[4] = {"base", "shoulder", "elbow", "gripper"};
const int LOW_LIMITS[4] = {10, 20, 15, 20};
const int HIGH_LIMITS[4] = {170, 150, 165, 100};
const int HOME[4] = {90, 90, 90, 60};
int positions[4] = {90, 90, 90, 60};

void writeState(JsonDocument& response) {
  JsonObject state = response["state"].to<JsonObject>();
  for (int i = 0; i < 4; i++) state[NAMES[i]] = positions[i];
}

void moveSmoothly(int targets[4], unsigned long durationMs) {
  int starts[4];
  for (int i = 0; i < 4; i++) starts[i] = positions[i];
  const int steps = max(1, (int)(durationMs / 20));
  for (int step = 1; step <= steps; step++) {
    for (int i = 0; i < 4; i++) {
      positions[i] = starts[i] + ((targets[i] - starts[i]) * step / steps);
      servos[i].write(positions[i]);
    }
    delay(20);
  }
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(1000);
  for (int i = 0; i < 4; i++) {
    servos[i].attach(PINS[i]);
    servos[i].write(HOME[i]);
  }
}

void loop() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n');
  StaticJsonDocument<384> request;
  StaticJsonDocument<256> response;
  if (deserializeJson(request, line)) {
    response["ok"] = false;
    response["error"] = "invalid JSON";
    serializeJson(response, Serial); Serial.println(); return;
  }

  const char* command = request["command"] | "";
  if (!strcmp(command, "move")) {
    int targets[4];
    for (int i = 0; i < 4; i++) {
      targets[i] = request["joints"][NAMES[i]] | positions[i];
      if (targets[i] < LOW_LIMITS[i] || targets[i] > HIGH_LIMITS[i]) {
        response["ok"] = false; response["error"] = "joint out of range";
        serializeJson(response, Serial); Serial.println(); return;
      }
    }
    moveSmoothly(targets, request["duration_ms"] | 800);
  } else if (!strcmp(command, "home")) {
    int targets[4]; for (int i = 0; i < 4; i++) targets[i] = HOME[i];
    moveSmoothly(targets, 1000);
  } else if (strcmp(command, "stop")) {
    response["ok"] = false; response["error"] = "unknown command";
    serializeJson(response, Serial); Serial.println(); return;
  }
  response["ok"] = true;
  writeState(response);
  serializeJson(response, Serial); Serial.println();
}

