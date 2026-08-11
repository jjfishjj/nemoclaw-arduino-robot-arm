import test from "node:test";
import assert from "node:assert/strict";
import {
  DEFAULT_REQUIREMENT,
  buildProjectSpec,
  createSimulator,
  evaluateTelemetry,
  sanitizeDeviceId,
  validateRequirement
} from "../model.mjs";

test("valid requirement produces the supported project spec", () => {
  const spec = buildProjectSpec(DEFAULT_REQUIREMENT, { deviceId: "Motor A/01", sampleRate: 120 });
  assert.equal(spec.device.id, "motor-a-01");
  assert.equal(spec.device.sample_rate_hz, 120);
  assert.deepEqual(spec.device.sensors, ["BME280", "MPU6050"]);
  assert.equal(spec.transport.telemetry_topic, "edgesense/v1/motor-a-01/telemetry");
});

test("empty and short requirements remain invalid", () => {
  assert.equal(validateRequirement(" ").valid, false);
  assert.equal(validateRequirement("監測馬達").valid, false);
});

test("unsupported hardware is not silently replaced", () => {
  const result = validateRequirement("使用 Arduino Uno 與 DHT11 監測工廠馬達溫度，異常時發出警報。".repeat(2));
  assert.equal(result.valid, false);
  assert.match(result.message, /尚未支援/);
});

test("the simulator is reproducible for the same seed", () => {
  const spec = buildProjectSpec(DEFAULT_REQUIREMENT);
  const first = createSimulator("normal", 9);
  const second = createSimulator("normal", 9);
  const timestamp = new Date("2026-07-30T00:00:00.000Z");
  assert.deepEqual(first.next(spec, timestamp), second.next(spec, timestamp));
});

test("each built-in scenario produces the expected decision", () => {
  const spec = buildProjectSpec(DEFAULT_REQUIREMENT);
  const now = new Date("2026-07-30T00:00:00.000Z");
  const normal = createSimulator("normal", 42).next(spec, now);
  const overheat = createSimulator("overheat", 42).next(spec, now);
  const vibration = createSimulator("vibration", 42).next(spec, now);
  assert.equal(normal.inference.is_anomaly, false);
  assert.ok(overheat.inference.reason_codes.includes("TEMP_HIGH"));
  assert.ok(vibration.inference.reason_codes.includes("VIBRATION_HIGH"));
});

test("invalid payload never enters inference", () => {
  const spec = buildProjectSpec(DEFAULT_REQUIREMENT);
  const result = evaluateTelemetry({ temperature_c: 44 }, spec);
  assert.equal(result.valid, false);
  assert.equal(result.inference, null);
  assert.ok(result.errors.includes("missing:device_id"));
});

test("device id sanitization always returns a usable id", () => {
  assert.equal(sanitizeDeviceId(" 工廠 Motor #7 "), "motor-7");
  assert.equal(sanitizeDeviceId("---"), "motor-01");
});
