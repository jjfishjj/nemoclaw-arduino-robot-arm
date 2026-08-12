const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const state = { paired: false, status: null, poll: null, scenes: [], scene: null, plan: null, planConfirmed: false, rgbd: null, rgbdFrame: null, livePoll: null, liveFrame: null, depthView: 'raw' };
const pairingPanel = $('#pairingPanel');
const consolePanel = $('#consolePanel');
const toast = $('#toast');

function notify(message, error = false) {
  toast.textContent = message;
  toast.className = `show${error ? ' error' : ''}`;
  window.clearTimeout(notify.timer);
  notify.timer = window.setTimeout(() => { toast.className = ''; }, 3200);
}

function metricValue(value, unit) {
  return unit === '%' ? `${value.toFixed(2)}%` : `${value.toFixed(unit === 'ms' ? 3 : 1)} ${unit}`;
}

function renderBenchmark(report) {
  const health = $('#benchmarkHealth');
  health.textContent = report.health;
  health.className = `health-badge ${report.health === 'HEALTHY' ? 'healthy' : (report.health === 'DEGRADED' ? 'degraded' : 'blocked')}`;
  $('#benchmarkGate').textContent = report.gate_status.replace('_', ' ');
  $('#benchmarkNative').textContent = report.verified_native ? 'VERIFIED' : 'UNVERIFIED';
  $('#benchmarkRecording').textContent = report.recording_sha256 ? report.recording_sha256.slice(0, 12) : '—';
  const hasMetrics = report.metrics.length > 0;
  $('#benchmarkEmpty').classList.toggle('hidden', hasMetrics);
  $('#benchmarkContent').classList.toggle('hidden', !hasMetrics);
  if (!hasMetrics) $('#benchmarkEmpty').textContent = report.failures.join(' · ');
  $('#benchmarkRows').replaceChildren(...report.metrics.map((metric) => {
    const row = document.createElement('tr');
    const deltaClass = metric.delta > 0 && metric.key !== 'fps' ? 'bad' : (metric.delta < 0 && metric.key === 'fps' ? 'bad' : 'good');
    row.innerHTML = '<th></th><td></td><td></td><td></td>';
    row.children[0].textContent = metric.label;
    row.children[1].textContent = metricValue(metric.baseline, metric.unit);
    row.children[2].textContent = metricValue(metric.current, metric.unit);
    row.children[3].textContent = `${metric.delta >= 0 ? '+' : ''}${metricValue(metric.delta, metric.unit)} (${metric.delta_percent >= 0 ? '+' : ''}${metric.delta_percent.toFixed(2)}%)`;
    row.children[3].className = deltaClass;
    return row;
  }));
  const failures = report.failures.length ? report.failures : ['No failures · all reviewed limits passed'];
  $('#benchmarkFailures').replaceChildren(...failures.map((failure) => {
    const item = document.createElement('li'); item.textContent = failure; return item;
  }));
}

async function loadBenchmark() {
  try {
    renderBenchmark(await api('/api/realsense/benchmark-dashboard'));
  } catch (error) {
    renderBenchmark({ health: 'BLOCKED', gate_status: 'INVALID', verified_native: false, recording_sha256: '', metrics: [], failures: [error.message] });
    notify(error.message, true);
  }
}

function renderLiveStatus(status) {
  const health = status.frame_health;
  $('#liveConnection').textContent = status.connected ? 'CONNECTED' : (status.running ? 'RECONNECTING' : 'STOPPED');
  $('#liveDot').classList.toggle('online', status.connected);
  $('#liveMode').textContent = status.filter_backend === 'pending' ? status.mode : status.filter_backend;
  $('#liveRawFps').textContent = status.raw_fps.toFixed(1);
  $('#liveFilteredFps').textContent = status.filtered_fps.toFixed(1);
  $('#liveFilterLatency').textContent = status.filter_latency_ms === null ? '—' : `${status.filter_latency_ms.toFixed(3)} ms`;
  $('#liveAge').textContent = status.frame_age_ms === null ? '—' : `${status.frame_age_ms.toFixed(0)} ms`;
  $('#liveReconnects').textContent = status.reconnect_count;
  $('#liveHealth').textContent = health.state;
  $('#liveHealth').className = `health-badge ${health.state.toLowerCase()}`;
  $('#liveHealthReason').textContent = `${health.reasons.join(' · ').toUpperCase()} · motion remains disabled`;
  $('#liveFreshBadge').textContent = status.fresh ? 'FRESH RGB-D' : (status.frame_age_ms === null ? 'NO FRAME' : 'STALE FRAME');
  $('#liveStartButton').disabled = status.running;
  $('#liveStopButton').disabled = !status.running;
  $('#liveError').textContent = status.last_error || (status.running ? 'Aligned color + depth stream active.' : '串流尚未啟動。');
  $('#liveError').classList.toggle('error', Boolean(status.last_error));
  $('#liveFilterVerification').textContent = `${status.filters.join(' → ').toUpperCase()} · ${status.verified_native ? 'NATIVE SDK VERIFIED' : 'CONTRACT FIXTURE — NOT NATIVE'} · NO MOTION`;
}

function renderDepthVisual() {
  const filtered = state.depthView === 'filtered';
  $('#depthRawButton').classList.toggle('active', !filtered);
  $('#depthFilteredButton').classList.toggle('active', filtered);
  $('#depthRawButton').setAttribute('aria-pressed', String(!filtered));
  $('#depthFilteredButton').setAttribute('aria-pressed', String(filtered));
  $('#depthViewTitle').textContent = filtered ? 'FILTERED DEPTH HEATMAP' : 'RAW DEPTH HEATMAP';
  $('#depthVisualImage').alt = `${filtered ? 'Filtered' : 'Raw'} depth heatmap${$('#depthMaskToggle').checked ? ' with invalid depth mask' : ''}`;
  if (!state.liveFrame) return;
  const mask = $('#depthMaskToggle').checked ? '1' : '0';
  $('#depthVisualImage').src = `/api/realsense/live/depth.png?view=${state.depthView}&mask=${mask}&frame=${state.liveFrame.index}`;
  $('#depthVisualEmpty').classList.add('hidden');
}

async function startLive() {
  try {
    renderLiveStatus(await api('/api/realsense/live/start', { method: 'POST', body: '{}' }));
    window.clearInterval(state.livePoll);
    state.livePoll = window.setInterval(pollLive, 500);
    await pollLive();
    logEvent('LIVE START', 'RGB-D stream');
  } catch (error) { notify(error.message, true); }
}

async function pollLive() {
  try {
    const result = await api('/api/realsense/live/poll', { method: 'POST', body: '{}' });
    state.liveFrame = result.frame;
    $('#liveImage').src = `${result.frame.color_asset}?frame=${result.frame.index}`;
    renderDepthVisual();
    renderLiveStatus(result.status);
  } catch (error) {
    try { renderLiveStatus(await api('/api/realsense/live/status')); } catch (_) { /* bridge status handles session loss */ }
  }
}

async function stopLive() {
  window.clearInterval(state.livePoll); state.livePoll = null;
  try {
    renderLiveStatus(await api('/api/realsense/live/stop', { method: 'POST', body: '{}' }));
    logEvent('LIVE STOP', 'RGB-D stream');
  } catch (error) { notify(error.message, true); }
}

$('#depthRawButton').addEventListener('click', () => { state.depthView = 'raw'; renderDepthVisual(); });
$('#depthFilteredButton').addEventListener('click', () => { state.depthView = 'filtered'; renderDepthVisual(); });
$('#depthMaskToggle').addEventListener('change', renderDepthVisual);

async function applyFilterGraph() {
  const config = {
    decimation: { magnitude: Number($('#decimationMagnitude').value) },
    spatial: { alpha: Number($('#spatialAlpha').value), iterations: Number($('#spatialIterations').value) },
    temporal: { alpha: Number($('#temporalAlpha').value) },
    hole_filling: { passes: Number($('#holePasses').value) },
  };
  try {
    const result = await api('/api/realsense/filters/apply', { method: 'POST', body: JSON.stringify({ index: Number($('#filterFrame').value), config }) });
    $('#filterSummary').textContent = `OUTPUT ${result.output.width}×${result.output.height} · invalid ${(result.output.invalid_ratio * 100).toFixed(1)}% · roughness ${result.output.roughness_m.toFixed(5)}m · ${result.processing_ms.toFixed(3)}ms · ${result.output.fingerprint}`;
    $('#filterStages').replaceChildren(...result.stages.map((stage, index) => {
      const item = document.createElement('li');
      const title = document.createElement('strong'); title.textContent = `${index + 1} · ${stage.name.toUpperCase()}`;
      const detail = document.createElement('span'); detail.textContent = `${stage.width}×${stage.height} · invalid ${(stage.invalid_ratio * 100).toFixed(1)}% · rough ${stage.roughness_m.toFixed(5)}m`;
      item.append(title, detail); return item;
    }));
    logEvent('FILTER GRAPH', result.output.fingerprint);
  } catch (error) {
    $('#filterSummary').textContent = `REJECTED · ${error.message}`;
    notify(error.message, true); logEvent('FILTER REJECT', error.message);
  }
}

function filterConfig() {
  return {
    decimation: { magnitude: Number($('#decimationMagnitude').value) },
    spatial: { alpha: Number($('#spatialAlpha').value), iterations: Number($('#spatialIterations').value) },
    temporal: { alpha: Number($('#temporalAlpha').value) },
    hole_filling: { passes: Number($('#holePasses').value) },
  };
}

async function compareNativeFilters() {
  const panel = $('#nativeComparison');
  try {
    const result = await api('/api/realsense/filters/native-compare', { method: 'POST', body: JSON.stringify({ index: Number($('#filterFrame').value), config: filterConfig() }) });
    const d = result.deltas;
    const verification = result.verified_native ? 'NATIVE VERIFIED' : 'SDK CONTRACT FIXTURE · NOT NATIVE VERIFIED';
    panel.textContent = `${verification}\n${result.native.backend}\ninvalid Δ ${(d.invalid_ratio_delta * 100).toFixed(2)}% · mean depth Δ ${d.mean_depth_delta_m.toFixed(4)}m · roughness Δ ${d.roughness_delta_m.toFixed(4)}m\n${result.within_limits ? 'WITHIN PARITY LIMITS' : 'OUTSIDE PARITY LIMITS'}`;
    panel.className = `native-comparison ${result.within_limits ? (result.verified_native ? 'pass' : 'warn') : 'warn'}`;
    logEvent('SDK PARITY', verification);
  } catch (error) {
    panel.textContent = `REJECTED · ${error.message}`; panel.className = 'native-comparison warn';
    notify(error.message, true); logEvent('SDK REJECT', error.message);
  }
}

function logEvent(action, detail = '完成') {
  const item = document.createElement('li');
  const now = new Date().toLocaleTimeString('zh-TW', { hour12: false });
  item.innerHTML = `<span>${now}</span><strong></strong><span></span>`;
  item.children[1].textContent = action;
  item.children[2].textContent = detail;
  $('#eventLog').prepend(item);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: 'same-origin',
    headers: options.body ? { 'Content-Type': 'application/json' } : {},
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function setPaired(paired) {
  state.paired = paired;
  pairingPanel.classList.toggle('hidden', paired);
  consolePanel.classList.toggle('hidden', !paired);
  $('#connectionDot').classList.toggle('online', paired);
  $('#connectionText').textContent = paired ? 'Local session' : '尚未配對';
  if (paired) {
    refreshStatus();
    loadVisionScenes();
    loadRGBDRecording();
    loadBenchmark();
    window.clearInterval(state.poll);
    state.poll = window.setInterval(refreshStatus, 1500);
  }
}

async function loadRGBDRecording() {
  try {
    const result = await api('/api/realsense/recording');
    state.rgbd = result;
    $('#rgbdRecording').textContent = `${result.recording} · ${result.bag_name}`;
    $('#rgbdResolution').textContent = `${result.intrinsics.width} × ${result.intrinsics.height}`;
    $('#rgbdFocal').textContent = `${result.intrinsics.fx} / ${result.intrinsics.fy}`;
    $('#pixelX').max = result.intrinsics.width - 1;
    $('#pixelY').max = result.intrinsics.height - 1;
    $('#rgbdFrameSlider').max = result.frame_count - 1;
    $('#rgbdFrameSlider').disabled = false;
    $('#deprojectButton').disabled = false;
    await loadRGBDFrame(0);
  } catch (error) { notify(error.message, true); }
}

async function loadRGBDFrame(index) {
  try {
    const result = await api('/api/realsense/frame', { method: 'POST', body: JSON.stringify({ index }) });
    state.rgbdFrame = result.frame;
    $('#rgbdImage').src = result.frame.color_asset;
    $('#rgbdTimestamp').textContent = `${result.frame.timestamp_ms.toFixed(1)} ms`;
    $('#rgbdIndex').textContent = `${result.frame.index + 1} / ${state.rgbd.frame_count}`;
    $('#rgbdFrameLabel').textContent = `#${result.frame.index} · ${result.frame.timestamp_ms.toFixed(1)} ms`;
    $('#coordinateResult').textContent = '選擇像素以讀取深度。';
  } catch (error) { notify(error.message, true); }
}

function positionDepthProbe(x, y) {
  $('#rgbdProbe').style.left = `${((x + .5) / state.rgbd.intrinsics.width) * 100}%`;
  $('#rgbdProbe').style.top = `${((y + .5) / state.rgbd.intrinsics.height) * 100}%`;
}

async function deprojectPixel() {
  const x = Number($('#pixelX').value); const y = Number($('#pixelY').value);
  try {
    const result = await api('/api/realsense/deproject', { method: 'POST', body: JSON.stringify({ index: state.rgbdFrame.index, x, y }) });
    positionDepthProbe(x, y);
    const point = result.camera_m;
    $('#coordinateResult').textContent = `X ${point.x.toFixed(4)} m\nY ${point.y.toFixed(4)} m\nZ ${point.z.toFixed(4)} m\n${result.frame}`;
    logEvent('RGB-D POINT', `px(${x},${y}) → Z ${point.z.toFixed(3)}m`);
  } catch (error) {
    $('#coordinateResult').textContent = `REJECTED · ${error.message}`;
    notify(error.message, true); logEvent('RGB-D REJECT', error.message);
  }
}

function buildJoints(status) {
  const container = $('#jointControls');
  const limits = status.limits || {};
  const current = status.state || {};
  const existing = new Set($$('.joint-row').map((row) => row.dataset.joint));
  if (Object.keys(limits).every((joint) => existing.has(joint))) return;
  container.replaceChildren();
  Object.entries(limits).forEach(([joint, range]) => {
    const row = document.createElement('div');
    row.className = 'joint-row';
    row.dataset.joint = joint;
    const value = current[joint] ?? Math.round((range[0] + range[1]) / 2);
    const label = document.createElement('label');
    label.htmlFor = `joint-${joint}`;
    label.textContent = joint.replaceAll('_', ' ');
    const input = document.createElement('input');
    input.type = 'range'; input.id = `joint-${joint}`; input.min = range[0]; input.max = range[1];
    input.step = Number.isInteger(range[0]) && Number.isInteger(range[1]) ? '1' : '0.1'; input.value = value;
    const output = document.createElement('output'); output.textContent = input.value;
    input.addEventListener('input', () => { output.textContent = input.value; });
    row.append(label, input, output);
    container.append(row);
  });
}

function renderStatus(status) {
  state.status = status;
  $('#profile').textContent = status.profile || '—';
  $('#armed').textContent = status.armed ? 'ARMED' : 'SAFE';
  $('#estop').textContent = status.estop_latched ? 'LATCHED' : 'READY';
  $('#watchdog').textContent = status.watchdog_tripped ? 'TRIPPED' : `${status.watchdog_timeout_s || 0}s`;
  $('#interlock').textContent = status.physical_estop || '—';
  $('#startup').textContent = status.startup_ready ? 'CONFIRMED' : 'REQUIRED';
  $('#armButton').disabled = !status.startup_ready || status.estop_latched || status.armed;
  $('#homeButton').disabled = !status.armed;
  $('#moveButton').disabled = !status.armed;
  updateVisionExecutionGate();
  buildJoints(status);
}

async function loadVisionScenes() {
  try {
    const result = await api('/api/vision/scenes');
    state.scenes = result.scenes;
    $('#sceneSelect').replaceChildren(...result.scenes.map((scene) => {
      const option = document.createElement('option');
      option.value = scene.id; option.textContent = scene.name; return option;
    }));
    showScene(result.scenes[0]);
  } catch (error) { notify(error.message, true); }
}

function showScene(scene) {
  state.scene = scene;
  state.plan = null; state.planConfirmed = false;
  $('#sceneImage').src = scene.image;
  $('#sceneImage').alt = scene.name;
  $('#planEmpty').classList.remove('hidden');
  $('#planDetails').classList.add('hidden');
  const layer = $('#detectionLayer');
  layer.replaceChildren(...scene.objects.map((object) => {
    const box = document.createElement('button');
    box.type = 'button'; box.className = `detection${object.confidence < .8 ? ' low' : ''}`;
    box.style.left = `${object.bbox.x}%`; box.style.top = `${object.bbox.y}%`;
    box.style.width = `${object.bbox.w}%`; box.style.height = `${object.bbox.h}%`;
    box.dataset.objectId = object.id;
    box.setAttribute('aria-label', `選取 ${object.label}，信心 ${(object.confidence * 100).toFixed(0)}%`);
    const label = document.createElement('span');
    label.textContent = `${object.label} ${(object.confidence * 100).toFixed(0)}%`;
    box.append(label);
    box.addEventListener('click', () => selectVisionObject(scene.id, object.id, box));
    return box;
  }));
}

async function selectVisionObject(sceneId, objectId, box) {
  try {
    const result = await api('/api/vision/select', { method: 'POST', body: JSON.stringify({ scene_id: sceneId, object_id: objectId }) });
    state.plan = result.plan; state.planConfirmed = false;
    $$('.detection').forEach((item) => item.classList.remove('selected'));
    box.classList.add('selected');
    renderVisionPlan(result.plan);
    logEvent('VISION SELECT', result.plan.object.label);
  } catch (error) { notify(error.message, true); logEvent('VISION REJECT', error.message); }
}

function renderVisionPlan(plan) {
  $('#planEmpty').classList.add('hidden');
  $('#planDetails').classList.remove('hidden');
  $('#planObject').textContent = plan.object.label;
  $('#planConfidence').textContent = `${(plan.object.confidence * 100).toFixed(0)}%`;
  $('#planRecipe').textContent = `${plan.recipe.name} · ${plan.recipe.destination}`;
  $('#planId').textContent = plan.plan_id.slice(0, 10);
  $('#planSteps').replaceChildren(...plan.recipe.steps.map((step) => {
    const item = document.createElement('li');
    const label = document.createElement('strong'); label.textContent = step.label;
    const detail = document.createElement('span');
    detail.textContent = `${Object.entries(step.joints).map(([joint, value]) => `${joint}:${value}`).join(' · ')} · ${step.duration_ms}ms`;
    item.append(label, detail); return item;
  }));
  $('#confirmPlanCheck').checked = false;
  $('#confirmPlanCheck').disabled = false;
  $('#confirmPlanButton').disabled = true;
  updateVisionExecutionGate();
}

function updateVisionExecutionGate() {
  $('#executePlanButton').disabled = !state.planConfirmed || !state.status?.armed || !state.status?.startup_ready;
}

async function refreshStatus() {
  try {
    renderStatus(await api('/api/status'));
    $('#connectionDot').classList.add('online');
    $('#connectionText').textContent = 'Bridge online';
  } catch (error) {
    $('#connectionDot').classList.remove('online');
    $('#connectionText').textContent = 'Bridge unavailable';
    if (error.message === 'pairing required') setPaired(false);
  }
}

async function command(payload, label) {
  try {
    const result = await api('/api/command', { method: 'POST', body: JSON.stringify(payload) });
    logEvent(label, JSON.stringify(result));
    notify(`${label} 完成`);
    await refreshStatus();
    return result;
  } catch (error) {
    logEvent(label, error.message);
    notify(error.message, true);
    throw error;
  }
}

$('#pairingForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    await api('/api/pair', { method: 'POST', body: JSON.stringify({ code: $('#pairingCode').value }) });
    $('#pairingCode').value = '';
    setPaired(true);
    notify('本機安全配對完成');
  } catch (error) { notify(error.message, true); }
});

$$('[data-check]').forEach((input) => input.addEventListener('change', () => {
  $('#confirmChecklist').disabled = !$$('[data-check]').every((item) => item.checked);
}));

$('#confirmChecklist').addEventListener('click', () => command({
  command: 'startup_check',
  checks: Object.fromEntries($$('[data-check]').map((item) => [item.dataset.check, item.checked])),
}, 'Startup check'));
$('#armButton').addEventListener('click', () => command({ command: 'arm' }, 'ARM'));
$('#homeButton').addEventListener('click', () => command({ command: 'home' }, 'HOME'));
$('#disarmButton').addEventListener('click', () => command({ command: 'disarm' }, 'DISARM'));
$('#stopButton').addEventListener('click', () => command({ command: 'stop' }, 'STOP'));
$('#resetButton').addEventListener('click', () => {
  if (!window.confirm('已再次確認工作範圍安全，並要解除 E-STOP 鎖定嗎？')) return;
  command({ command: 'reset_estop', workspace_confirmed: true }, 'Reset E-STOP');
});
$('#moveButton').addEventListener('click', () => {
  const joints = Object.fromEntries($$('.joint-row').map((row) => {
    const input = row.querySelector('input');
    return [row.dataset.joint, Number(input.value)];
  }));
  command({ command: 'move', joints, duration_ms: Number($('#duration').value) }, 'MOVE');
});
$('#duration').addEventListener('input', () => { $('#durationValue').textContent = `${$('#duration').value} ms`; });
$('#refreshButton').addEventListener('click', refreshStatus);
$('#clearLog').addEventListener('click', () => $('#eventLog').replaceChildren());
$('#sceneSelect').addEventListener('change', () => showScene(state.scenes.find((scene) => scene.id === $('#sceneSelect').value)));
$('#rgbdFrameSlider').addEventListener('input', () => loadRGBDFrame(Number($('#rgbdFrameSlider').value)));
$('#deprojectButton').addEventListener('click', deprojectPixel);
$('#liveStartButton').addEventListener('click', startLive);
$('#liveStopButton').addEventListener('click', stopLive);
$('#applyFiltersButton').addEventListener('click', applyFilterGraph);
$('#compareNativeButton').addEventListener('click', compareNativeFilters);
$('#benchmarkRefresh').addEventListener('click', loadBenchmark);
$('#rgbdFrame').addEventListener('click', (event) => {
  if (!state.rgbd) return;
  const rect = $('#rgbdFrame').getBoundingClientRect();
  $('#pixelX').value = Math.min(state.rgbd.intrinsics.width - 1, Math.max(0, Math.floor((event.clientX - rect.left) / rect.width * state.rgbd.intrinsics.width)));
  $('#pixelY').value = Math.min(state.rgbd.intrinsics.height - 1, Math.max(0, Math.floor((event.clientY - rect.top) / rect.height * state.rgbd.intrinsics.height)));
  deprojectPixel();
});
$('#confirmPlanCheck').addEventListener('change', () => { $('#confirmPlanButton').disabled = !$('#confirmPlanCheck').checked || !state.plan; });
$('#confirmPlanButton').addEventListener('click', async () => {
  try {
    const result = await api('/api/vision/confirm', { method: 'POST', body: JSON.stringify({ plan_id: state.plan.plan_id, human_confirmed: true }) });
    state.plan = result.plan; state.planConfirmed = true;
    $('#confirmPlanButton').disabled = true;
    $('#confirmPlanCheck').disabled = true;
    updateVisionExecutionGate();
    notify('視覺計畫已由人工確認'); logEvent('VISION CONFIRM', state.plan.recipe.name);
  } catch (error) { notify(error.message, true); }
});
$('#executePlanButton').addEventListener('click', async () => {
  try {
    const result = await api('/api/vision/execute', { method: 'POST', body: JSON.stringify({ plan_id: state.plan.plan_id }) });
    notify('Mock 命名動作執行完成'); logEvent('VISION EXECUTE', `${result.recipe} · ${result.steps.length} steps`);
    state.planConfirmed = false; updateVisionExecutionGate(); await refreshStatus();
  } catch (error) { notify(error.message, true); logEvent('VISION ERROR', error.message); }
});

api('/api/session').then((result) => setPaired(result.paired)).catch(() => setPaired(false));
