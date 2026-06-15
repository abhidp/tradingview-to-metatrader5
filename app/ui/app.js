const $ = (id) => document.getElementById(id);
function esc(s) { return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
let logCursor = 0;

function dot(on) { return on ? '<span class="dot-on">●</span>' : '<span class="dot-off">○</span>'; }

async function refreshStatus() {
  try {
    const s = await (await fetch('/api/status')).json();
    const pill = $('state-pill'), btn = $('toggle-btn'), banner = $('banner');
    pill.className = 'pill ' + (s.engine === 'running' ? 'run' : (s.engine === 'error' ? 'stop' : (s.engine === 'starting' || s.engine === 'stopping' ? 'busy' : 'stop')));
    pill.textContent = '● ' + s.engine.charAt(0).toUpperCase() + s.engine.slice(1);
    const running = s.engine === 'running';
    window._engineRunning = running;
    btn.textContent = running ? '■ Stop' : '▶ Start Copying';
    btn.className = 'btn ' + (running ? 'stop' : 'start');
    btn.disabled = (s.engine === 'starting' || s.engine === 'stopping');
    $('tv-val').innerHTML = dot(s.tv.connected) + ' ' + (s.tv.account || '—');
    $('mt5-val').innerHTML = dot(s.mt5.connected) + ' ' + (s.mt5.account || '—');
    $('proxy-val').innerHTML = dot(s.proxy.listening) + ' :' + s.proxy.port;
    if (s.error) { banner.textContent = s.error; banner.classList.remove('hidden'); }
    else { banner.classList.add('hidden'); }
  } catch (e) { /* server momentarily unavailable */ }
}

async function refreshTrades() {
  try {
    const d = await (await fetch('/api/trades?limit=10')).json();
    $('recent').innerHTML = (d.trades || []).map(t =>
      `<li>${t.created_at ? t.created_at.slice(11, 19) : ''} ${esc(t.side)} ${esc(t.instrument)} x${esc(t.quantity)} — ${esc(t.status)}</li>`
    ).join('') || '<li>No trades yet</li>';
  } catch (e) {}
}

async function refreshLogs() {
  try {
    const d = await (await fetch('/api/logs?after=' + logCursor)).json();
    if (d.lines && d.lines.length) {
      const box = $('logbox');
      box.textContent += (box.textContent ? '\n' : '') + d.lines.join('\n');
      box.scrollTop = box.scrollHeight;
    }
    logCursor = d.cursor;
  } catch (e) {}
}

$('logs-bottom').addEventListener('click', () => {
  const box = $('logbox');
  box.scrollTop = box.scrollHeight;
});

$('toggle-btn').addEventListener('click', async () => {
  const running = $('toggle-btn').className.includes('stop');
  const url = running ? '/api/engine/stop' : '/api/engine/start';
  const r = await fetch(url, { method: 'POST' });
  if (!r.ok) {
    const j = await r.json().catch(() => ({}));
    const banner = $('banner');
    banner.textContent = j.detail || 'Action failed';
    banner.classList.remove('hidden');
  }
  refreshStatus();
});

const VIEWS = ['dashboard', 'trades', 'symbols', 'settings', 'logs'];

function showView(view) {
  VIEWS.forEach(v => $('view-' + v).classList.toggle('hidden', v !== view));
  document.querySelectorAll('.nav-item[data-view]').forEach(n =>
    n.classList.toggle('active', n.getAttribute('data-view') === view));
  if (view === 'trades') loadTrades();
  if (view === 'symbols' && typeof loadSymbols === 'function') loadSymbols();
  if (view === 'settings' && typeof loadSettings === 'function') loadSettings();
}

document.querySelectorAll('.nav-item[data-view]').forEach(el => {
  el.addEventListener('click', () => showView(el.getAttribute('data-view')));
});

setInterval(refreshStatus, 1500);
setInterval(refreshTrades, 3000);
setInterval(refreshLogs, 1500);
refreshStatus(); refreshTrades(); refreshLogs();

// --- Trades tab ---
let tradesOffset = 0;
const TRADES_PAGE = 50;

async function loadTrades() {
  const status = $('trades-status').value;
  const url = `/api/trades?limit=${TRADES_PAGE}&offset=${tradesOffset}&status=${encodeURIComponent(status)}`;
  try {
    const d = await (await fetch(url)).json();
    const rows = d.trades || [];
    $('trades-body').innerHTML = rows.map(t => `<tr>
      <td>${t.created_at ? t.created_at.replace('T', ' ').slice(0, 19) : ''}</td>
      <td>${esc(t.side)}</td>
      <td>${esc(t.instrument)}</td>
      <td>${esc(t.quantity)}</td>
      <td>${esc(t.status)}</td>
      <td>${esc(t.mt5_ticket)}</td>
    </tr>`).join('') || '<tr><td colspan="6">No trades</td></tr>';
    const total = d.total || 0;
    const from = total ? tradesOffset + 1 : 0;
    const to = Math.min(tradesOffset + TRADES_PAGE, total);
    $('trades-range').textContent = `${from}–${to} of ${total}`;
    $('trades-prev').disabled = tradesOffset === 0;
    $('trades-next').disabled = tradesOffset + TRADES_PAGE >= total;
  } catch (e) {}
}

$('trades-status').addEventListener('change', () => { tradesOffset = 0; loadTrades(); });
$('trades-prev').addEventListener('click', () => { tradesOffset = Math.max(0, tradesOffset - TRADES_PAGE); loadTrades(); });
$('trades-next').addEventListener('click', () => { tradesOffset += TRADES_PAGE; loadTrades(); });

// --- Symbols tab ---
function symbolRow(tv = '', mt5 = '') {
  const div = document.createElement('div');
  div.className = 'map-row';
  div.innerHTML = `<input class="map-tv" placeholder="BTCUSD" />
    <span>→</span>
    <input class="map-mt5" placeholder="BTCUSD.r" />
    <button class="btn ghost map-del">✕</button>`;
  div.querySelector('.map-tv').value = tv;
  div.querySelector('.map-mt5').value = mt5;
  div.querySelector('.map-del').addEventListener('click', () => div.remove());
  return div;
}

async function loadSymbols() {
  $('symbols-banner').classList.add('hidden');
  try {
    const d = await (await fetch('/api/symbols')).json();
    $('sym-suffix').value = d.default_suffix || '';
    const box = $('sym-map');
    box.innerHTML = '';
    Object.entries(d.map || {}).forEach(([tv, mt5]) => box.appendChild(symbolRow(tv, mt5)));
  } catch (e) {}
}

$('sym-add').addEventListener('click', () => $('sym-map').appendChild(symbolRow()));

$('sym-save').addEventListener('click', async () => {
  const map = {};
  document.querySelectorAll('#sym-map .map-row').forEach(r => {
    const tv = r.querySelector('.map-tv').value.trim();
    const mt5 = r.querySelector('.map-mt5').value.trim();
    if (tv) map[tv] = mt5;
  });
  const body = { default_suffix: $('sym-suffix').value.trim(), map };
  const r = await fetch('/api/symbols', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  showSaveResult($('symbols-banner'), r);
});

// --- Settings tab ---
async function loadSettings() {
  $('settings-banner').classList.add('hidden');
  try {
    const d = await (await fetch('/api/settings')).json();
    $('set-account').value = d.mt5.account ?? '';
    $('set-server').value = d.mt5.server || '';
    $('set-terminal').value = d.mt5.terminal_path || '';
    $('set-password').value = '';
    $('set-password').placeholder = d.mt5.password_set ? '•••••• (unchanged)' : 'not set';
    $('set-tv-broker').value = d.tv.broker_url || '';
    $('set-tv-account').value = d.tv.account_id || '';
  } catch (e) {}
}

$('set-save').addEventListener('click', async () => {
  const mt5 = {
    account: $('set-account').value.trim(),
    server: $('set-server').value.trim(),
    terminal_path: $('set-terminal').value.trim(),
  };
  const pw = $('set-password').value;
  if (pw) mt5.password = pw;
  const r = await fetch('/api/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mt5 }) });
  showSaveResult($('settings-banner'), r, true);
});

// --- shared save-result + restart banner ---
async function showSaveResult(banner, resp, reload) {
  if (!resp.ok) {
    const j = await resp.json().catch(() => ({}));
    banner.textContent = j.detail || 'Save failed';
    banner.className = 'banner';
    return;
  }
  if (reload) loadSettings();
  if (window._engineRunning) {
    banner.innerHTML = 'Saved — restart the engine to apply. <button id="restart-now" class="btn start">Restart engine</button>';
    banner.className = 'banner ok';
    $('restart-now').addEventListener('click', async () => {
      banner.textContent = 'Restarting…';
      await fetch('/api/engine/restart', { method: 'POST' });
      refreshStatus();
      banner.textContent = 'Engine restarted.';
    });
  } else {
    banner.textContent = 'Saved.';
    banner.className = 'banner ok';
  }
}

// --- Onboarding wizard (Plan 4a) ---
let wizStep = 1;
const WIZ_LAST = 6;
let certPoll = null;
let tvPoll = null;
let engineStartedForDetection = false;

function wizBanner(msg, ok) {
  const b = $('wiz-banner');
  b.textContent = msg;
  b.className = 'banner' + (ok ? ' ok' : '');
}

function enterWizard() {
  document.body.classList.add('onboarding');
  VIEWS.forEach(v => $('view-' + v).classList.add('hidden'));
  $('view-wizard').classList.remove('hidden');
  gotoStep(wizStep);
}

function exitWizard() {
  document.body.classList.remove('onboarding');
  clearInterval(certPoll); clearInterval(tvPoll);
  $('view-wizard').classList.add('hidden');
  showView('dashboard');
}

function gotoStep(step) {
  wizStep = Math.max(1, Math.min(WIZ_LAST, step));
  document.querySelectorAll('.wiz-step').forEach(li =>
    li.classList.toggle('active', Number(li.getAttribute('data-step')) === wizStep));
  document.querySelectorAll('.wiz-pane').forEach(p =>
    p.classList.toggle('hidden', Number(p.getAttribute('data-pane')) !== wizStep));
  $('wiz-back').disabled = wizStep === 1;
  $('wiz-next').textContent = wizStep === WIZ_LAST ? 'Start Copying' : 'Next';
  $('wiz-banner').classList.add('hidden');
  $('wiz-next').disabled = false;
  fetch('/api/wizard/step', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ step: wizStep }),
  }).catch(() => {});
  wizStopCertPoll();
  if (wizStep !== 4) wizStopTvDetection();
  if (wizStep === 2) wizLoadCert();
  if (wizStep === 3) wizLoadMt5();
  if (wizStep === 4) wizStartTvDetection();
  if (wizStep === 5) wizLoadSuffix();
}

async function wizLoadCert() {
  $('wiz-next').disabled = true;
  try {
    const d = await (await fetch('/api/wizard/cert/status')).json();
    setCertUi(d.trusted);
  } catch (e) {}
}

function setCertUi(trusted) {
  $('wiz-cert-status').textContent = trusted ? '✓ Certificate installed' : 'Not installed yet';
  $('wiz-cert-install').classList.toggle('hidden', trusted);
  if (wizStep === 2) $('wiz-next').disabled = !trusted;
}

$('wiz-cert-install').addEventListener('click', async () => {
  $('wiz-cert-status').textContent = 'Requesting administrator access…';
  let r;
  try { r = await (await fetch('/api/wizard/cert/install', { method: 'POST' })).json(); }
  catch (e) { wizBanner('Install failed', false); return; }
  if (r.ok) { setCertUi(true); return; }
  if (r.error) { wizBanner(r.error, false); $('wiz-cert-status').textContent = 'Not installed yet'; return; }
  $('wiz-cert-status').textContent = 'Installing… approve the Windows prompt.';
  clearInterval(certPoll);
  certPoll = setInterval(async () => {
    try {
      const d = await (await fetch('/api/wizard/cert/status')).json();
      if (d.trusted) { clearInterval(certPoll); setCertUi(true); }
    } catch (e) {}
  }, 1500);
});

async function wizLoadMt5() {
  $('wiz-next').disabled = true; // require a successful test first
  try {
    const d = await (await fetch('/api/wizard/mt5/detect')).json();
    const t = $('wiz-mt5-terminal');
    if (!t.value) t.value = d.current || (d.terminals && d.terminals[0]) || '';
  } catch (e) {}
}

$('wiz-mt5-test').addEventListener('click', async () => {
  $('wiz-mt5-result').textContent = 'Testing…';
  const mt5 = {
    account: $('wiz-mt5-account').value.trim(),
    password: $('wiz-mt5-password').value,
    server: $('wiz-mt5-server').value.trim(),
    terminal_path: $('wiz-mt5-terminal').value.trim(),
  };
  let r;
  try {
    r = await (await fetch('/api/wizard/mt5/test', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mt5 }),
    })).json();
  } catch (e) { wizBanner('Test failed', false); return; }
  if (r.ok) {
    $('wiz-mt5-result').textContent = `✓ ${r.account} — ${r.balance} ${r.currency} (${r.server})`;
    $('wiz-next').disabled = false;
  } else {
    $('wiz-mt5-result').textContent = '';
    wizBanner(r.error || 'Connection failed', false);
  }
});

async function wizStartTvDetection() {
  $('wiz-next').disabled = true;
  await fetch('/api/engine/start', { method: 'POST' }).catch(() => {});
  engineStartedForDetection = true;
  clearInterval(tvPoll);
  tvPoll = setInterval(async () => {
    try {
      const d = await (await fetch('/api/wizard/tv/detection')).json();
      if (d.detected) {
        $('wiz-tv-status').textContent = `✓ Detected account ${d.account_id}`;
        $('wiz-next').disabled = false;
      }
    } catch (e) {}
  }, 2000);
}

function wizStopCertPoll() { clearInterval(certPoll); certPoll = null; }

function wizStopTvDetection() {
  clearInterval(tvPoll); tvPoll = null;
  if (engineStartedForDetection) {
    engineStartedForDetection = false;
    fetch('/api/engine/stop', { method: 'POST' }).catch(() => {});
  }
}

async function wizLoadSuffix() {
  try {
    const d = await (await fetch('/api/wizard/symbols/suggest')).json();
    if (!$('wiz-suffix').value) $('wiz-suffix').value = d.suffix || '.r';
  } catch (e) {}
}

$('wiz-back').addEventListener('click', () => gotoStep(wizStep - 1));

$('wiz-next').addEventListener('click', async () => {
  if (wizStep === 5) {
    let cur = { map: {} };
    try { cur = await (await fetch('/api/symbols')).json(); } catch (e) {}
    await fetch('/api/symbols', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ default_suffix: $('wiz-suffix').value.trim(), map: cur.map || {} }),
    }).catch(() => {});
  }
  if (wizStep === WIZ_LAST) {
    await fetch('/api/wizard/complete', { method: 'POST' }).catch(() => {});
    exitWizard();
    await fetch('/api/engine/start', { method: 'POST' }).catch(() => {});
    refreshStatus();
    return;
  }
  gotoStep(wizStep + 1);
});

$('set-rerun').addEventListener('click', () => { wizStep = 1; enterWizard(); });

async function initOnboarding() {
  try {
    const d = await (await fetch('/api/wizard/state')).json();
    if (!d.onboarding_complete) { wizStep = d.step || 1; enterWizard(); }
  } catch (e) {}
}
initOnboarding();
