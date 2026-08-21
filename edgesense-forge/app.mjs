import {
  DEFAULT_REQUIREMENT,
  SCENARIOS,
  buildProjectSpec,
  createSimulator,
  validateRequirement
} from "./model.mjs";

const $ = (selector) => document.querySelector(selector);
const state = {
  spec: null,
  simulator: createSimulator("normal", 42),
  scenario: "normal",
  running: false,
  backendReady: false,
  mqttConnected: false,
  socket: null,
  reconnectTimer: null,
  history: [],
  latest: null
  ,apiKey: ""
};

const els = {
  form: $("#project-form"),
  requirement: $("#requirement"),
  requirementError: $("#requirement-error"),
  deviceId: $("#device-id"),
  sampleRate: $("#sample-rate"),
  threshold: $("#threshold"),
  apiKey: $("#api-key"),
  generate: $("#generate-button"),
  loadExample: $("#load-example"),
  emptyState: $("#empty-state"),
  workspace: $("#workspace"),
  projectName: $("#project-name"),
  connection: $("#connection-status"),
  simulationStatus: $("#simulation-status"),
  start: $("#start-simulation"),
  reset: $("#reset-simulation"),
  temperature: $("#temperature-value"),
  vibration: $("#vibration-value"),
  score: $("#score-value"),
  latency: $("#latency-value"),
  engine: $("#engine-value"),
  scoreBar: $("#score-bar"),
  alertCard: $("#alert-card"),
  alertLabel: $("#alert-label"),
  alertReason: $("#alert-reason"),
  timeline: $("#event-timeline"),
  pipeline: $("#pipeline"),
  tabPanel: $("#tab-panel"),
  liveDot: $("#live-dot"),
  exportButton: $("#export-button"),
  runBenchmark: $("#run-benchmark"),
  engineCards: $("#engine-cards"),
  benchmarkResult: $("#benchmark-result")
  ,historySummary: $("#history-summary")
  ,historyChart: $("#history-chart")
  ,anomalyHistory: $("#anomaly-history")
  ,benchmarkHistory: $("#benchmark-history")
  ,refreshHistory: $("#refresh-history")
  ,alertWorklist: $("#alert-worklist")
  ,loadMoreAlerts: $("#load-more-alerts")
  ,ruleForm: $("#rule-form")
  ,exportAlerts: $("#export-alerts")
};
let alertCursor = null;
let alertFilter = "open";

els.requirement.value = DEFAULT_REQUIREMENT;

els.form.addEventListener("submit", (event) => {
  event.preventDefault();
  generateProject();
});

els.loadExample.addEventListener("click", () => {
  els.requirement.value = DEFAULT_REQUIREMENT;
  els.deviceId.value = "motor-01";
  els.sampleRate.value = "100";
  els.threshold.value = "0.70";
  clearValidation();
  els.requirement.focus();
});

document.querySelectorAll("[data-scenario]").forEach((button) => {
  button.addEventListener("click", () => selectScenario(button.dataset.scenario));
});

document.querySelectorAll("[data-tab]").forEach((button) => {
  button.addEventListener("click", () => selectTab(button.dataset.tab));
});

els.start.addEventListener("click", toggleSimulation);
els.reset.addEventListener("click", resetSimulation);
els.exportButton.addEventListener("click", exportSpec);
els.runBenchmark.addEventListener("click", runBenchmark);
els.refreshHistory.addEventListener("click", loadHistory);
els.loadMoreAlerts.addEventListener("click", () => loadAlerts(true));
els.alertWorklist.addEventListener("click", handleAlertAction);
els.ruleForm.addEventListener("submit", saveRule);
els.exportAlerts.addEventListener("click", exportAlertsCsv);
els.apiKey.addEventListener("input", async () => {
  state.apiKey = els.apiKey.value.trim();
  const previousSocket = state.socket;
  state.socket = null;
  if (previousSocket && previousSocket.readyState < 2) previousSocket.close();
  await authenticateSession();
  connectBackend();
});
document.querySelectorAll("[data-alert-filter]").forEach((button) => button.addEventListener("click", () => {
  alertFilter = button.dataset.alertFilter;
  document.querySelectorAll("[data-alert-filter]").forEach((item) => item.classList.toggle("is-active", item === button));
  loadAlerts(false);
}));
connectBackend();

function generateProject() {
  const result = validateRequirement(els.requirement.value);
  if (!result.valid) {
    els.requirementError.textContent = result.message;
    els.requirement.setAttribute("aria-invalid", "true");
    els.requirement.focus();
    return;
  }

  stopSimulation();
  clearValidation();
  state.spec = buildProjectSpec(els.requirement.value, {
    deviceId: els.deviceId.value,
    sampleRate: els.sampleRate.value,
    anomalyThreshold: els.threshold.value
  });
  state.history = [];
  state.latest = null;
  state.simulator = createSimulator(state.scenario, 42);
  els.emptyState.hidden = true;
  els.workspace.hidden = false;
  els.projectName.textContent = `${state.spec.device.id} · MOTOR CONDITION MONITOR`;
  els.connection.textContent = state.mqttConnected ? "MQTT READY" : "MQTT OFFLINE";
  els.connection.dataset.state = state.mqttConnected ? "ready" : "offline";
  renderSpec();
  renderBlankMetrics();
  renderTimeline();
  selectTab("overview");
  announce("方案已建立，可啟動 Live Lab。", "success");
}

function selectScenario(name) {
  if (!SCENARIOS[name]) return;
  stopSimulation();
  state.scenario = name;
  state.simulator.setScenario(name);
  state.history = [];
  state.latest = null;
  document.querySelectorAll("[data-scenario]").forEach((button) => {
    const selected = button.dataset.scenario === name;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  $("#scenario-description").textContent = SCENARIOS[name].description;
  renderBlankMetrics();
  renderTimeline();
  announce(`已選擇「${SCENARIOS[name].label}」，按下開始以執行。`, "neutral");
}

async function toggleSimulation() {
  if (!state.spec) return;
  if (!state.backendReady || !state.mqttConnected) {
    announce("Edge service 或 MQTT 尚未就緒。請先啟動 Mosquitto 與 FastAPI。", "error");
    return;
  }
  if (state.running) {
    await stopSimulation();
    announce("模擬已暫停，最後一筆資料仍保留。", "neutral");
    return;
  }
  try {
    const response = await apiFetch("/api/simulator/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scenario: state.scenario,
        device_id: state.spec.device.id,
        sample_rate_hz: state.spec.device.sample_rate_hz,
        anomaly_threshold: state.spec.alert.anomaly_score,
        temperature_threshold_c: state.spec.alert.temperature_c
      })
    });
    if (!response.ok) throw new Error(await response.text());
    state.running = true;
    setRunningUI(true);
    announce("MQTT simulator 已啟動，等待 broker telemetry。", "success");
  } catch (error) {
    state.running = false;
    setRunningUI(false);
    announce(`無法啟動 MQTT simulator：${error.message}`, "error");
  }
}

async function stopSimulation() {
  if (state.running && state.backendReady) {
    try {
      await apiFetch("/api/simulator/stop", { method: "POST" });
    } catch {
      // Connection state is handled centrally by the WebSocket reconnect loop.
    }
  }
  state.running = false;
  setRunningUI(false);
}

async function resetSimulation() {
  if (!state.spec) return;
  await stopSimulation();
  if (state.backendReady) {
    try { await apiFetch("/api/simulator/reset", { method: "POST" }); } catch { /* status handles it */ }
  }
  state.simulator.reset();
  state.history = [];
  state.latest = null;
  els.connection.textContent = "READY";
  renderBlankMetrics();
  renderTimeline();
  announce("模擬資料已重設。", "neutral");
}

function consumeEdgeEvent(result) {
  state.latest = result;
  state.history.unshift(result);
  state.history = state.history.slice(0, 6);
  renderMetrics(result);
  renderTimeline();
}

function setRunningUI(running) {
  els.start.textContent = running ? "暫停模擬" : "開始模擬";
  els.start.dataset.running = String(running);
  els.simulationStatus.textContent = running ? "LIVE" : (state.latest ? "PAUSED" : "IDLE");
  els.simulationStatus.dataset.state = running ? "live" : "idle";
  els.liveDot.classList.toggle("is-live", running);
  if (state.backendReady) {
    els.connection.textContent = running ? "MQTT STREAMING" : (state.mqttConnected ? "MQTT READY" : "MQTT OFFLINE");
    els.connection.dataset.state = state.mqttConnected ? "ready" : "offline";
  }
}

async function connectBackend() {
  window.clearTimeout(state.reconnectTimer);
  try {
    const [statusResponse, authResponse] = await Promise.all([
      fetch("/api/status", { cache: "no-store" }), fetch("/api/auth/status", { cache: "no-store" })
    ]);
    if (!statusResponse.ok) throw new Error("status endpoint unavailable");
    const status = await statusResponse.json();
    const auth = await authResponse.json();
    if (auth.required && !state.apiKey) {
      state.backendReady = false; state.mqttConnected = status.mqtt_connected; updateBackendBadge();
      announce("此部署需要 API Key；輸入後才會建立安全 session。", "error");
      return;
    }
    state.backendReady = true;
    state.mqttConnected = status.mqtt_connected;
    updateBackendBadge();
    await loadModelMetadata();
    openEventSocket();
  } catch {
    state.backendReady = false;
    state.mqttConnected = false;
    state.running = false;
    updateBackendBadge();
    state.reconnectTimer = window.setTimeout(connectBackend, 2500);
  }
}

async function loadModelMetadata() {
  try {
    const response = await fetch("/api/models", { cache: "no-store" });
    if (!response.ok) throw new Error("model endpoint unavailable");
    const payload = await response.json();
    els.engineCards.innerHTML = payload.engines.map((engine) => `
      <div class="benchmark-card ${engine.available ? "available" : "unavailable"}">
        <span>${engine.engine.toUpperCase()}${engine.engine === "tensorrt" ? " · JETSON" : ""}</span>
        <strong>${engine.available ? "AVAILABLE" : "UNAVAILABLE"}</strong>
        <p>${engine.available
          ? `${engine.model_version} · ${engine.runtime_version} · ${(engine.providers || []).join(", ")}`
          : engine.reason}</p>
      </div>`).join("");
  } catch (error) {
    els.engineCards.innerHTML = `<div class="benchmark-card unavailable"><span>MODEL RUNTIME</span><strong>ERROR</strong><p>${error.message}</p></div>`;
  }
}

async function runBenchmark() {
  if (!state.backendReady) {
    announce("Edge service 尚未連線，無法執行 benchmark。", "error");
    return;
  }
  els.runBenchmark.disabled = true;
  els.runBenchmark.textContent = "測量中…";
  els.benchmarkResult.hidden = true;
  try {
    const response = await apiFetch("/api/benchmark", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        warmup_runs: Number($("#warmup-runs").value),
        measured_runs: Number($("#measured-runs").value)
      })
    });
    if (!response.ok) throw new Error(await response.text());
    const result = await response.json();
    els.benchmarkResult.innerHTML = `
      <div><span>ENGINE</span><strong>${result.engine.toUpperCase()}</strong></div>
      <div><span>MEAN</span><strong>${result.mean_ms.toFixed(4)} ms</strong></div>
      <div><span>P50</span><strong>${result.p50_ms.toFixed(4)} ms</strong></div>
      <div><span>P95</span><strong>${result.p95_ms.toFixed(4)} ms</strong></div>
      <p>${result.measured_runs} measured · ${result.warmup_runs} warm-up · ${result.device} · ${result.evidence.toUpperCase()}</p>`;
    els.benchmarkResult.hidden = false;
    await loadBenchmarkHistory();
    announce("ONNX Runtime benchmark 已完成，結果為本機實測。", "success");
  } catch (error) {
    announce(`Benchmark 失敗：${error.message}`, "error");
  } finally {
    els.runBenchmark.disabled = false;
    els.runBenchmark.textContent = "執行 Benchmark";
  }
}

async function loadHistory() {
  if (!state.backendReady) return;
  const device = state.spec?.device?.id;
  const query = device ? `?device_id=${encodeURIComponent(device)}&limit=120` : "?limit=120";
  try {
    const [historyResponse, anomalyResponse, summaryResponse] = await Promise.all([
      apiFetch(`/api/history${query}`, { cache: "no-store" }),
      apiFetch(`/api/anomalies${device ? `?device_id=${encodeURIComponent(device)}&limit=30` : "?limit=30"}`, { cache: "no-store" }),
      apiFetch("/api/history/summary", { cache: "no-store" })
    ]);
    if (!historyResponse.ok || !anomalyResponse.ok || !summaryResponse.ok) throw new Error("history endpoint unavailable");
    const history = (await historyResponse.json()).items.reverse();
    const anomalies = (await anomalyResponse.json()).items;
    const summary = await summaryResponse.json();
    renderHistorySummary(summary);
    renderHistoryChart(history);
    renderAnomalyHistory(anomalies);
  } catch (error) {
    els.historyChart.innerHTML = `<p class="timeline-empty">歷史資料讀取失敗：${escapeHtml(error.message)}</p>`;
  }
}

function renderHistorySummary(summary) {
  els.historySummary.innerHTML = [
    ["SAMPLES", summary.samples], ["ANOMALIES", summary.anomalies],
    ["DEVICES", summary.devices], ["LATEST", summary.latest_at ? new Date(summary.latest_at).toLocaleTimeString("zh-TW") : "—"]
  ].map(([label, value]) => `<div><span>${label}</span><strong>${value}</strong></div>`).join("");
}

function renderHistoryChart(items) {
  if (!items.length) {
    els.historyChart.innerHTML = '<p class="timeline-empty">尚無持久化資料；啟動 Live Lab 後會自動保存。</p>';
    return;
  }
  const width = 900, height = 230, pad = 28;
  const point = (value, index, min, max) => {
    const x = pad + (index / Math.max(items.length - 1, 1)) * (width - pad * 2);
    const y = height - pad - ((value - min) / Math.max(max - min, 0.001)) * (height - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  };
  const temperatures = items.map((item) => Number(item.temperature_c));
  const scores = items.map((item) => Number(item.anomaly_score) * 100);
  const tempPoints = temperatures.map((value, index) => point(value, index, 0, 100)).join(" ");
  const scorePoints = scores.map((value, index) => point(value, index, 0, 100)).join(" ");
  const alertDots = items.map((item, index) => item.is_anomaly
    ? `<circle cx="${point(100, index, 0, 100).split(',')[0]}" cy="15" r="4" class="chart-alert"><title>${escapeHtml(item.reason_codes.join(", "))}</title></circle>` : "").join("");
  els.historyChart.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="溫度與異常分數歷史趨勢">
    <line x1="${pad}" y1="${height-pad}" x2="${width-pad}" y2="${height-pad}" class="chart-axis"/>
    <polyline points="${tempPoints}" class="chart-line temperature"/>
    <polyline points="${scorePoints}" class="chart-line score"/>${alertDots}
    <text x="${pad}" y="18" class="chart-label">TEMP °C</text><text x="110" y="18" class="chart-label score-label">SCORE ×100</text>
  </svg>`;
}

function renderAnomalyHistory(items) {
  if (!items.length) {
    els.anomalyHistory.innerHTML = '<p class="timeline-empty">目前沒有異常事件。</p>';
    return;
  }
  els.anomalyHistory.innerHTML = items.map((item) => `<div class="history-row anomaly">
    <time>${new Date(item.measured_at).toLocaleString("zh-TW")}</time><strong>${escapeHtml(item.device_id)}</strong>
    <span>${item.temperature_c.toFixed(1)}°C · ${item.accel_rms_g.toFixed(2)}g</span><b>${item.anomaly_score.toFixed(3)}</b>
    <small>${escapeHtml(item.reason_codes.join(" · "))}</small></div>`).join("");
}

async function loadBenchmarkHistory() {
  try {
    const response = await apiFetch("/api/benchmarks?limit=12", { cache: "no-store" });
    if (!response.ok) throw new Error("benchmark history unavailable");
    const items = (await response.json()).items;
    els.benchmarkHistory.innerHTML = items.length ? items.map((item) => `<div class="history-row">
      <time>${new Date(item.measured_at).toLocaleString("zh-TW")}</time><strong>${escapeHtml(item.engine.toUpperCase())}</strong>
      <span>P50 ${item.p50_ms.toFixed(4)} ms</span><b>P95 ${item.p95_ms.toFixed(4)} ms</b><small>${escapeHtml(item.device)}</small></div>`).join("")
      : '<p class="timeline-empty">尚無 Benchmark 紀錄。</p>';
  } catch (error) {
    els.benchmarkHistory.innerHTML = `<p class="timeline-empty">${escapeHtml(error.message)}</p>`;
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[character]);
}

async function loadAlerts(append = false) {
  const params = new URLSearchParams({ limit: "20" });
  if (alertFilter) params.set("status", alertFilter);
  if (append && alertCursor) params.set("cursor", alertCursor);
  try {
    const response = await apiFetch(`/api/alerts?${params}`, { cache: "no-store" });
    if (!response.ok) throw new Error(await response.text());
    const payload = await response.json();
    const html = payload.items.length ? payload.items.map((item) => `<article class="alert-work-item" data-alert-id="${item.alert_id}">
      <div><span class="alert-state ${item.status}">${item.status.toUpperCase()}</span><strong>${escapeHtml(item.device_id)} · ${Number(item.anomaly_score).toFixed(3)}</strong><time>${new Date(item.measured_at).toLocaleString("zh-TW")}</time></div>
      <p>${escapeHtml(item.reason_codes.join(" · "))} · ${Number(item.temperature_c).toFixed(1)}°C · ${Number(item.accel_rms_g).toFixed(2)}g</p>
      <textarea class="alert-note" rows="2" maxlength="1000" placeholder="處理備註">${escapeHtml(item.note || "")}</textarea>
      <div class="alert-actions"><button class="secondary-button" data-next-status="acknowledged">確認</button><button class="secondary-button" data-next-status="resolved">完成</button></div>
    </article>`).join("") : '<p class="timeline-empty">此狀態目前沒有告警。</p>';
    els.alertWorklist.innerHTML = append ? els.alertWorklist.innerHTML + html : html;
    alertCursor = payload.next_cursor;
    els.loadMoreAlerts.hidden = !alertCursor;
  } catch (error) { els.alertWorklist.innerHTML = `<p class="timeline-empty">${escapeHtml(error.message)}</p>`; }
}

async function handleAlertAction(event) {
  const button = event.target.closest("[data-next-status]");
  if (!button) return;
  const card = button.closest("[data-alert-id]");
  button.disabled = true;
  try {
    const response = await apiFetch(`/api/alerts/${card.dataset.alertId}`, {
      method: "PATCH", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({status: button.dataset.nextStatus, note: card.querySelector(".alert-note").value, actor: "dashboard-operator"})
    });
    if (!response.ok) throw new Error(await response.text());
    await loadAlerts(false); announce("告警狀態與備註已保存。", "success");
  } catch (error) { announce(`告警更新失敗：${error.message}`, "error"); button.disabled = false; }
}

async function loadRule() {
  const device = state.spec?.device?.id || "motor-01";
  const response = await apiFetch(`/api/rules/${encodeURIComponent(device)}`, {cache:"no-store"});
  if (!response.ok) return;
  const rule = await response.json();
  $("#rule-score").value = rule.anomaly_threshold; $("#rule-temperature").value = rule.temperature_threshold_c;
  $("#rule-retention").value = rule.retention_days; $("#rule-enabled").checked = Boolean(rule.enabled);
}

async function saveRule(event) {
  event.preventDefault(); const device = state.spec?.device?.id || "motor-01";
  const response = await apiFetch(`/api/rules/${encodeURIComponent(device)}`, {method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({
    enabled:$("#rule-enabled").checked, anomaly_threshold:Number($("#rule-score").value),
    temperature_threshold_c:Number($("#rule-temperature").value), retention_days:Number($("#rule-retention").value)
  })});
  if (response.ok) announce("告警規則已保存並套用至目前裝置。", "success"); else announce(`規則保存失敗：${await response.text()}`, "error");
}

function openEventSocket() {
  if (state.socket && state.socket.readyState < 2) return;
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(`${protocol}//${location.host}/ws/events`, ["edgesense"]);
  state.socket = socket;
  socket.addEventListener("open", () => {
    state.backendReady = true;
    updateBackendBadge();
  });
  socket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === "telemetry") {
      consumeEdgeEvent({ telemetry: payload.telemetry, inference: payload.inference });
    } else if (payload.type === "validation_error") {
      announce(`MQTT payload 驗證失敗：${payload.errors.join(" · ")}`, "error");
    }
  });
  socket.addEventListener("close", () => {
    if (state.socket !== socket) return;
    state.backendReady = false;
    state.running = false;
    setRunningUI(false);
    updateBackendBadge();
    state.reconnectTimer = window.setTimeout(connectBackend, 2000);
  });
}

function updateBackendBadge() {
  const badge = document.querySelector(".status-pill");
  if (state.backendReady && state.mqttConnected) {
    badge.innerHTML = "<i></i> EDGE SERVICE + MQTT";
    badge.dataset.state = "online";
    if (!state.running) els.connection.textContent = "MQTT READY";
    announce("Edge service、MQTT 與 WebSocket 已連線。", "success");
  } else if (state.backendReady) {
    badge.innerHTML = "<i></i> EDGE SERVICE / MQTT WAIT";
    badge.dataset.state = "degraded";
    els.connection.textContent = "MQTT OFFLINE";
    announce("Edge service 已啟動，正在等待 Mosquitto。", "error");
  } else {
    badge.innerHTML = "<i></i> BACKEND OFFLINE";
    badge.dataset.state = "offline";
    els.connection.textContent = "BACKEND OFFLINE";
  }
}

function renderBlankMetrics() {
  els.temperature.textContent = "—";
  els.vibration.textContent = "—";
  els.score.textContent = "—";
  els.latency.textContent = "—";
  els.engine.textContent = "ENGINE WAITING";
  els.scoreBar.style.width = "0%";
  els.alertCard.dataset.alert = "none";
  els.alertLabel.textContent = "等待資料";
  els.alertReason.textContent = "啟動情境後，推論結果會顯示在這裡。";
  els.pipeline.querySelectorAll(".pipeline-node").forEach((node) => node.classList.remove("is-active"));
}

function renderMetrics(result) {
  const { telemetry, inference } = result;
  els.temperature.textContent = `${Number(telemetry.temperature_c).toFixed(1)} °C`;
  els.vibration.textContent = `${Number(telemetry.accel_rms_g).toFixed(2)} g`;
  els.score.textContent = Number(inference.score).toFixed(2);
  els.latency.textContent = `${Number(inference.latency_ms).toFixed(3)} ms`;
  els.engine.textContent = `${String(inference.engine).toUpperCase()} · ${inference.model_version}`;
  els.scoreBar.style.width = `${Math.round(inference.score * 100)}%`;
  els.scoreBar.dataset.alert = String(inference.is_anomaly);
  els.alertCard.dataset.alert = inference.is_anomaly ? "true" : "false";
  els.alertLabel.textContent = inference.is_anomaly ? "需要注意" : "設備狀態正常";
  els.alertReason.textContent = formatReasons(inference.reason_codes);
  els.pipeline.querySelectorAll(".pipeline-node").forEach((node, index) => {
    window.setTimeout(() => node.classList.add("is-active"), index * 80);
  });
}

function renderSpec() {
  const spec = state.spec;
  $("#device-summary").innerHTML = `
    <div><span>控制板</span><strong>${spec.device.board}</strong></div>
    <div><span>感測器</span><strong>${spec.device.sensors.join(" + ")}</strong></div>
    <div><span>資料匯流排</span><strong>${spec.device.bus} · ${spec.device.pins.sda} / ${spec.device.pins.scl}</strong></div>
    <div><span>Edge target</span><strong>${spec.edge.target}</strong></div>`;
  $("#telemetry-topic").textContent = spec.transport.telemetry_topic;
  $("#schema-preview").textContent = JSON.stringify({
    schema_version: "1.0",
    device_id: spec.device.id,
    ts: "ISO-8601",
    temperature_c: "number",
    accel_rms_g: "number",
    sample_rate_hz: spec.device.sample_rate_hz
  }, null, 2);
  $("#checks-list").innerHTML = spec.checks.map((check) => `
    <li class="check-item" data-level="${check.level}">
      <span aria-hidden="true">${check.level === "pass" ? "✓" : "!"}</span>
      <p>${check.text}</p>
    </li>`).join("");
  $("#spec-preview").textContent = JSON.stringify(spec, null, 2);
}

function renderTimeline() {
  if (!state.history.length) {
    els.timeline.innerHTML = '<li class="timeline-empty">尚無事件。啟動模擬後會保留最近 6 筆推論。</li>';
    return;
  }
  els.timeline.innerHTML = state.history.map(({ telemetry, inference }) => `
    <li class="event-row" data-alert="${inference.is_anomaly}">
      <span class="event-time">${new Date(telemetry.ts).toLocaleTimeString("zh-TW", { hour12: false })}</span>
      <span class="event-mark" aria-hidden="true"></span>
      <span class="event-name">${inference.is_anomaly ? "ANOMALY" : "NORMAL"}</span>
      <span class="event-detail">${inference.reason_codes.join(" · ")}</span>
      <strong>${Number(inference.score).toFixed(2)}</strong>
    </li>`).join("");
}

function selectTab(name) {
  document.querySelectorAll("[data-tab]").forEach((button) => {
    const selected = button.dataset.tab === name;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
  });
  document.querySelectorAll("[data-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.panel !== name;
  });
  if (name === "history") loadHistory();
  if (name === "benchmark") loadBenchmarkHistory();
  if (name === "alerts") { loadAlerts(false); loadRule(); }
}

function exportSpec() {
  if (!state.spec) return;
  const blob = new Blob([JSON.stringify(state.spec, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${state.spec.project_id}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
  announce("Project Spec 已匯出，內容不包含任何連線密碼。", "success");
}

function clearValidation() {
  els.requirementError.textContent = "";
  els.requirement.removeAttribute("aria-invalid");
}

function announce(message, tone) {
  const region = $("#announcement");
  region.textContent = message;
  region.dataset.tone = tone;
}

function formatReasons(reasons) {
  const labels = {
    WITHIN_RANGE: "所有訊號都在設定範圍內。",
    TEMP_HIGH: "溫度已超過 70°C 安全門檻。",
    VIBRATION_HIGH: "震動 RMS 高於 0.8 g 門檻。"
  };
  return reasons.map((reason) => labels[reason] || reason).join(" ");
}

function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.apiKey) headers.set("X-API-Key", state.apiKey);
  return fetch(url, {...options, headers});
}

async function authenticateSession() {
  if (!state.apiKey) return false;
  const response = await fetch("/api/auth/session", {method:"POST",headers:{"X-API-Key":state.apiKey}});
  if (!response.ok) { announce("API Key 驗證失敗。", "error"); return false; }
  return true;
}

async function exportAlertsCsv() {
  try {
    const response = await apiFetch("/api/alerts/export.csv");
    if (!response.ok) throw new Error(await response.text());
    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "edgesense-alerts.csv";
    anchor.click(); URL.revokeObjectURL(url); announce("告警 CSV 已匯出。", "success");
  } catch (error) { announce(`CSV 匯出失敗：${error.message}`, "error"); }
}
