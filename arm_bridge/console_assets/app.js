const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const state = { paired: false, status: null, poll: null };
const pairingPanel = $('#pairingPanel');
const consolePanel = $('#consolePanel');
const toast = $('#toast');

function notify(message, error = false) {
  toast.textContent = message;
  toast.className = `show${error ? ' error' : ''}`;
  window.clearTimeout(notify.timer);
  notify.timer = window.setTimeout(() => { toast.className = ''; }, 3200);
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
    window.clearInterval(state.poll);
    state.poll = window.setInterval(refreshStatus, 1500);
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
  buildJoints(status);
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

api('/api/session').then((result) => setPaired(result.paired)).catch(() => setPaired(false));
