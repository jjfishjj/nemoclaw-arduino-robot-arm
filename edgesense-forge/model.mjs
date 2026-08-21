export const DEFAULT_REQUIREMENT =
  "使用 ESP32 收集設備溫度與三軸震動，透過 MQTT 傳給 Jetson。Jetson 在本地判斷設備是否異常，超過門檻時顯示告警。";

export const SCENARIOS = Object.freeze({
  normal: {
    label: "正常運轉",
    description: "設備穩定，溫度與震動都在安全範圍。",
    temperatureBase: 42.2,
    vibrationBase: 0.18,
    scoreBase: 0.18
  },
  overheat: {
    label: "設備過熱",
    description: "模擬散熱異常，溫度逐步超過 70°C。",
    temperatureBase: 76.4,
    vibrationBase: 0.24,
    scoreBase: 0.82
  },
  vibration: {
    label: "異常震動",
    description: "模擬軸承磨損，震動 RMS 顯著上升。",
    temperatureBase: 48.6,
    vibrationBase: 1.42,
    scoreBase: 0.91
  }
});

const unsupportedTerms = [
  ["arduino uno", "ESP32 DevKit V1"],
  ["raspberry pi pico", "ESP32 DevKit V1"],
  ["dht11", "BME280"],
  ["ultrasonic", "MPU6050"],
  ["超音波", "MPU6050"]
];

export function validateRequirement(value) {
  const text = value.trim();
  if (!text) {
    return { valid: false, message: "請描述監測對象、感測資料，以及異常時要採取的動作。" };
  }
  if (text.length < 20) {
    return { valid: false, message: "需求還不夠完整。請至少補上感測器資料與告警行為。" };
  }
  if (text.length > 500) {
    return { valid: false, message: "需求請控制在 500 字內，先聚焦一個設備監測情境。" };
  }
  const lower = text.toLowerCase();
  const unsupported = unsupportedTerms.find(([term]) => lower.includes(term));
  if (unsupported) {
    return {
      valid: false,
      message: `MVP 尚未支援 ${unsupported[0]}。建議改用 ${unsupported[1]}，原始需求已保留。`
    };
  }
  return { valid: true, message: "需求可由目前的支援矩陣建立。" };
}

export function buildProjectSpec(requirement, options = {}) {
  const validation = validateRequirement(requirement);
  if (!validation.valid) throw new Error(validation.message);

  const deviceId = sanitizeDeviceId(options.deviceId || "motor-01");
  const sampleRate = clamp(Number(options.sampleRate) || 100, 10, 400);
  const anomalyThreshold = clamp(Number(options.anomalyThreshold) || 0.7, 0.1, 0.99);

  return {
    spec_version: "0.1",
    project_id: "motor-monitor-demo",
    requirement: requirement.trim(),
    template: "motor-condition-monitoring",
    device: {
      id: deviceId,
      board: "ESP32 DevKit V1",
      sensors: ["BME280", "MPU6050"],
      bus: "I²C",
      pins: { sda: "GPIO 21", scl: "GPIO 22", power: "3V3", ground: "GND" },
      sample_rate_hz: sampleRate
    },
    transport: {
      protocol: "MQTT",
      telemetry_topic: `edgesense/v1/${deviceId}/telemetry`,
      status_topic: `edgesense/v1/${deviceId}/status`,
      alert_topic: `edgesense/v1/${deviceId}/alert`
    },
    edge: {
      target: "NVIDIA Jetson",
      active_engine: "baseline",
      engines: ["baseline", "onnxruntime", "tensorrt"]
    },
    alert: { temperature_c: 70, anomaly_score: anomalyThreshold },
    checks: [
      { level: "pass", text: "I²C 感測器共用 GPIO 21 / 22，未發現 pin 衝突" },
      { level: "pass", text: "BME280 與 MPU6050 使用 3.3V 邏輯電壓" },
      { level: "warning", text: "實體上電前仍須核對模組板型、I²C 位址與資料表" },
      { level: "warning", text: "本機 prototype 使用記憶體資料流；正式 MQTT 部署應啟用 TLS" }
    ]
  };
}

export function createSeededRandom(seed = 42) {
  let state = seed >>> 0;
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

export function createSimulator(scenarioName = "normal", seed = 42) {
  let step = 0;
  let scenario = SCENARIOS[scenarioName] ? scenarioName : "normal";
  let random = createSeededRandom(seed);

  return {
    setScenario(next) {
      if (!SCENARIOS[next]) throw new Error(`Unknown scenario: ${next}`);
      scenario = next;
      step = 0;
      random = createSeededRandom(seed + Object.keys(SCENARIOS).indexOf(next) * 101);
    },
    reset() {
      step = 0;
      random = createSeededRandom(seed + Object.keys(SCENARIOS).indexOf(scenario) * 101);
    },
    next(spec, now = new Date()) {
      const config = SCENARIOS[scenario];
      const wave = Math.sin(step / 2.3);
      const noise = (random() - 0.5) * 2;
      const temperature = config.temperatureBase + wave * 0.8 + noise * 0.35;
      const vibration = Math.max(0, config.vibrationBase + wave * 0.05 + noise * 0.035);
      const score = clamp(config.scoreBase + wave * 0.025 + noise * 0.018, 0, 0.99);
      step += 1;
      return evaluateTelemetry({
        schema_version: "1.0",
        device_id: spec.device.id,
        ts: now.toISOString(),
        temperature_c: round(temperature, 1),
        accel_rms_g: round(vibration, 2),
        sample_rate_hz: spec.device.sample_rate_hz,
        anomaly_score: round(score, 2)
      }, spec);
    }
  };
}

export function evaluateTelemetry(telemetry, spec) {
  const required = ["schema_version", "device_id", "ts", "temperature_c", "accel_rms_g", "sample_rate_hz"];
  const missing = required.filter((field) => telemetry[field] === undefined || telemetry[field] === "");
  if (missing.length) {
    return { valid: false, errors: missing.map((field) => `missing:${field}`), telemetry, inference: null };
  }

  const reasons = [];
  if (telemetry.temperature_c >= spec.alert.temperature_c) reasons.push("TEMP_HIGH");
  if (telemetry.accel_rms_g >= 0.8) reasons.push("VIBRATION_HIGH");
  const score = Number(telemetry.anomaly_score ?? 0);
  const isAnomaly = reasons.length > 0 || score >= spec.alert.anomaly_score;

  return {
    valid: true,
    errors: [],
    telemetry,
    inference: {
      score,
      is_anomaly: isAnomaly,
      reason_codes: reasons.length ? reasons : ["WITHIN_RANGE"],
      engine: "baseline",
      latency_ms: round(1.4 + score * 0.8, 2),
      model_version: "motor-anomaly-0.1"
    }
  };
}

export function sanitizeDeviceId(value) {
  const result = String(value).trim().toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "");
  return result || "motor-01";
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function round(value, digits) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}
