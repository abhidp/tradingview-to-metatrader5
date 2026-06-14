const $ = (id) => document.getElementById(id);
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
      `<li>${t.created_at ? t.created_at.slice(11, 19) : ''} ${t.side || ''} ${t.instrument || ''} x${t.quantity || ''} — ${t.status || ''}</li>`
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
      <td>${t.side || ''}</td>
      <td>${t.instrument || ''}</td>
      <td>${t.quantity || ''}</td>
      <td>${t.status || ''}</td>
      <td>${t.mt5_ticket || ''}</td>
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
  div.innerHTML = `<input class="map-tv" placeholder="BTCUSD" value="${tv}" />
    <span>→</span>
    <input class="map-mt5" placeholder="BTCUSD.r" value="${mt5}" />
    <button class="btn ghost map-del">✕</button>`;
  div.querySelector('.map-del').addEventListener('click', () => div.remove());
  return div;
}

async function loadSymbols() {
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
