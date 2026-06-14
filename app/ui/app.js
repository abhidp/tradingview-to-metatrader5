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

document.querySelectorAll('.nav-item[data-view]').forEach(el => {
  el.addEventListener('click', () => {
    document.querySelectorAll('.nav-item[data-view]').forEach(n => n.classList.remove('active'));
    el.classList.add('active');
    const view = el.getAttribute('data-view');
    $('view-dashboard').classList.toggle('hidden', view !== 'dashboard');
    $('view-logs').classList.toggle('hidden', view !== 'logs');
  });
});

setInterval(refreshStatus, 1500);
setInterval(refreshTrades, 3000);
setInterval(refreshLogs, 1500);
refreshStatus(); refreshTrades(); refreshLogs();
