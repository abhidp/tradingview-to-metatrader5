# TV2MT5 Plan 7b — Broker Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users save named broker profiles (MT5 connection + symbols) and switch between them in one click, auto-restarting the engine to apply.

**Architecture:** Profiles live in the existing SQLite settings store (`profiles.list` JSON + per-profile secret password + `profiles.active`). A pure `app/storage/profiles.py` module does CRUD and "activate" — where activate **copies** the profile's values into the existing live config keys the engine already reads (`mt5.*`, `symbols.*`), so the engine/`mt5_service` need no changes. API routes expose CRUD + activate; the activate route restarts the engine when running. The Settings tab gets a profiles section reusing 7a's terminal picker.

**Tech Stack:** Python 3.11, FastAPI, SQLite settings store; vanilla JS frontend.

**Spec:** `docs/superpowers/specs/2026-06-15-tv2mt5-mt5-agnostic-onboarding-design.md` (Phase 7b)
**Prerequisite:** Plan 7a merged (terminal picker reused by the profiles form).

> Test commands use the repo venv. Do NOT run git checkout/switch/branch/reset during tasks; commit on the current branch.

---

## File Structure

- Modify `app/storage/settings_store.py` — add a `delete(key)` method (to drop a profile's secret password on delete).
- Create `app/storage/profiles.py` — pure CRUD + `activate_profile` over an injected `SettingsStore`.
- Create `app/api/profiles_api.py` — `add_profile_routes(app, controller)`: CRUD + activate (restart on activate when running).
- Modify `app/api/server.py` — call `add_profile_routes(app, controller)`.
- Modify `app/api/wizard.py` — on `wizard/complete`, auto-create a "Default" profile if none exist.
- Modify `app/ui/index.html` + `app/ui/app.js` — "Broker profiles" section in the Settings tab.
- Tests: `tests/unit/test_profiles.py`, `tests/unit/test_profiles_api.py`.

---

## Task 1: `SettingsStore.delete()`

**Files:**
- Modify: `app/storage/settings_store.py`
- Test: `tests/unit/test_settings_delete.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_settings_delete.py
from app.storage.settings_store import SettingsStore


def test_delete_removes_key(temp_db_path):
    # temp_db_path (conftest fixture) points the app at a throwaway SQLite file
    # and resets the engine singletons, so SettingsStore() binds to it.
    s = SettingsStore()
    s.set("foo", "bar")
    assert s.get("foo") == "bar"
    s.delete("foo")
    assert s.get("foo") is None
    s.delete("foo")  # idempotent — no error on missing key
```

> Uses the existing `temp_db_path` fixture from `tests/conftest.py` (it sets `TV2MT5_DB_PATH` and resets `src.config.database._engine`/`_SessionFactory`). Do NOT hand-reset DB globals — the fixture is the supported way to get an isolated DB.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_settings_delete.py -v`
Expected: FAIL (`SettingsStore` has no attribute `delete`).

- [ ] **Step 3: Implement** — add to `SettingsStore` (after `set`):

```python
    def delete(self, key: str) -> None:
        """Remove a key if present (idempotent)."""
        session = self._Session()
        try:
            row = session.get(Settings, key)
            if row is not None:
                session.delete(row)
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_settings_delete.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/storage/settings_store.py tests/unit/test_settings_delete.py
git commit -m "feat(settings): add SettingsStore.delete()"
```

---

## Task 2: Profiles module (CRUD + activate)

**Files:**
- Create: `app/storage/profiles.py`
- Test: `tests/unit/test_profiles.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_profiles.py
import json

from app.storage.settings_store import SettingsStore
import app.storage.profiles as profiles


# All tests take the conftest `temp_db_path` fixture for an isolated DB, then
# construct SettingsStore() (which binds to it).
def _data(name="Fusion"):
    return {
        "name": name,
        "mt5": {"terminal_path": r"C:\Fusion\terminal64.exe", "account": "384569",
                "server": "FusionMarketsAU-Demo", "password": "secret-pw"},
        "symbols": {"default_suffix": ".r", "map": {"USTEC": "NAS100"}},
    }


def test_create_stores_profile_and_secret_password(temp_db_path):
    s = SettingsStore()
    p = profiles.create_profile(_data(), store=s)
    assert p["id"] and p["name"] == "Fusion" and p["password_set"] is True
    # Password must NOT be in the plaintext profiles.list JSON.
    raw_list = s.get("profiles.list")
    assert "secret-pw" not in raw_list
    # It is retrievable via the secret store.
    assert s.get_secret(f"profiles.{p['id']}.password") == "secret-pw"


def test_list_redacts_passwords_and_flags_active(temp_db_path):
    s = SettingsStore()
    p = profiles.create_profile(_data(), store=s)
    profiles.activate_profile(p["id"], store=s)
    out = profiles.list_profiles(store=s)
    assert out["active"] == p["id"]
    assert out["profiles"][0]["password_set"] is True
    assert "password" not in out["profiles"][0]["mt5"]


def test_activate_copies_values_into_live_keys(temp_db_path):
    s = SettingsStore()
    p = profiles.create_profile(_data(), store=s)
    profiles.activate_profile(p["id"], store=s)
    assert s.get("mt5.terminal_path") == r"C:\Fusion\terminal64.exe"
    assert s.get("mt5.account") == "384569"
    assert s.get("mt5.server") == "FusionMarketsAU-Demo"
    assert s.get_secret("mt5.password") == "secret-pw"
    assert s.get("symbols.default_suffix") == ".r"
    assert json.loads(s.get("symbols.map")) == {"USTEC": "NAS100"}
    assert s.get("profiles.active") == p["id"]


def test_update_and_delete(temp_db_path):
    s = SettingsStore()
    p = profiles.create_profile(_data(), store=s)
    profiles.update_profile(p["id"], {"name": "Renamed"}, store=s)
    assert profiles.list_profiles(store=s)["profiles"][0]["name"] == "Renamed"
    profiles.delete_profile(p["id"], store=s)
    assert profiles.list_profiles(store=s)["profiles"] == []
    assert s.get_secret(f"profiles.{p['id']}.password") is None


def test_activate_unknown_raises(temp_db_path):
    s = SettingsStore()
    try:
        profiles.activate_profile("nope", store=s)
        assert False, "expected KeyError"
    except KeyError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_profiles.py -v`
Expected: FAIL (`app.storage.profiles` does not exist).

- [ ] **Step 3: Implement**

```python
# app/storage/profiles.py
"""Broker profiles: named MT5-connection + symbols presets in the settings store.

A profile is saved config. Activating it COPIES its values into the live keys the
engine already reads (mt5.*, symbols.*) — so the engine needs no knowledge of
profiles. Passwords are stored via the store's secret mechanism, never in the
plaintext profiles.list JSON.
"""
import json
import uuid
from typing import Optional

from app.storage.settings_store import SettingsStore

LIST_KEY = "profiles.list"
ACTIVE_KEY = "profiles.active"


def _pw_key(pid: str) -> str:
    return f"profiles.{pid}.password"


def _load(store: SettingsStore) -> list:
    return store.get_json(LIST_KEY, []) or []


def _save(store: SettingsStore, items: list) -> None:
    store.set(LIST_KEY, json.dumps(items))


def _shape(data: dict) -> dict:
    mt5 = data.get("mt5") or {}
    sym = data.get("symbols") or {}
    return {
        "name": data.get("name") or "Unnamed",
        "mt5": {
            "terminal_path": mt5.get("terminal_path", "") or "",
            "account": str(mt5.get("account", "") or ""),
            "server": mt5.get("server", "") or "",
        },
        "symbols": {
            "default_suffix": sym.get("default_suffix", "") or "",
            "map": sym.get("map", {}) or {},
        },
    }


def list_profiles(store: Optional[SettingsStore] = None) -> dict:
    store = store or SettingsStore()
    items = _load(store)
    out = []
    for p in items:
        out.append({**p, "password_set": bool(store.get_secret(_pw_key(p["id"])))})
    return {"profiles": out, "active": store.get(ACTIVE_KEY) or ""}


def create_profile(data: dict, store: Optional[SettingsStore] = None) -> dict:
    store = store or SettingsStore()
    items = _load(store)
    pid = uuid.uuid4().hex[:8]
    profile = {"id": pid, **_shape(data)}
    password = (data.get("mt5") or {}).get("password")
    if password:
        store.set_secret(_pw_key(pid), password)
    items.append(profile)
    _save(store, items)
    return {**profile, "password_set": bool(password)}


def update_profile(pid: str, data: dict, store: Optional[SettingsStore] = None) -> dict:
    store = store or SettingsStore()
    items = _load(store)
    for i, p in enumerate(items):
        if p["id"] == pid:
            merged = {**p, **_shape({**p, **data,
                                     "mt5": {**p["mt5"], **(data.get("mt5") or {})},
                                     "symbols": {**p["symbols"], **(data.get("symbols") or {})}})}
            merged["id"] = pid
            items[i] = merged
            password = (data.get("mt5") or {}).get("password")
            if password:
                store.set_secret(_pw_key(pid), password)
            _save(store, items)
            return {**merged, "password_set": bool(store.get_secret(_pw_key(pid)))}
    raise KeyError(pid)


def delete_profile(pid: str, store: Optional[SettingsStore] = None) -> None:
    store = store or SettingsStore()
    items = [p for p in _load(store) if p["id"] != pid]
    _save(store, items)
    store.delete(_pw_key(pid))
    if store.get(ACTIVE_KEY) == pid:
        store.delete(ACTIVE_KEY)


def activate_profile(pid: str, store: Optional[SettingsStore] = None) -> dict:
    """Copy the profile's values into the live config keys and mark it active."""
    store = store or SettingsStore()
    profile = next((p for p in _load(store) if p["id"] == pid), None)
    if profile is None:
        raise KeyError(pid)
    mt5, sym = profile["mt5"], profile["symbols"]
    store.set("mt5.terminal_path", mt5.get("terminal_path", ""))
    store.set("mt5.account", mt5.get("account", ""))
    store.set("mt5.server", mt5.get("server", ""))
    pw = store.get_secret(_pw_key(pid))
    if pw:
        store.set_secret("mt5.password", pw)
    store.set("symbols.default_suffix", sym.get("default_suffix", ""))
    store.set("symbols.map", json.dumps(sym.get("map", {})))
    store.set(ACTIVE_KEY, pid)
    return profile
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_profiles.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add app/storage/profiles.py tests/unit/test_profiles.py
git commit -m "feat(profiles): broker profile CRUD + activate (copy into live keys)"
```

---

## Task 3: Profiles API

**Files:**
- Create: `app/api/profiles_api.py`
- Test: `tests/unit/test_profiles_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_profiles_api.py
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.profiles_api as papi


class FakeController:
    def __init__(self, running):
        self._running = running
        self.restarted = False

    def status(self):
        class S:
            def to_dict(self_inner):
                return {"engine": "running" if self._running else "stopped"}
        return S()

    async def restart(self):
        self.restarted = True


def _client(controller, monkeypatch, store):
    # Route the module's profile functions at an in-memory fake store.
    monkeypatch.setattr(papi.profiles, "SettingsStore", lambda: store)
    app = FastAPI()
    papi.add_profile_routes(app, controller)
    return TestClient(app)


def test_create_list_activate_restarts_when_running(temp_db_path, monkeypatch):
    from app.storage.settings_store import SettingsStore
    store = SettingsStore()

    ctrl = FakeController(running=True)
    c = _client(ctrl, monkeypatch, store)

    r = c.post("/api/profiles", json={"name": "A", "mt5": {"account": "1", "server": "S",
               "password": "pw", "terminal_path": "C:/t.exe"}, "symbols": {"default_suffix": ".r"}})
    assert r.status_code == 200
    pid = r.json()["id"]

    assert c.get("/api/profiles").json()["profiles"][0]["name"] == "A"

    r = c.post(f"/api/profiles/{pid}/activate")
    assert r.status_code == 200
    assert ctrl.restarted is True
    assert c.get("/api/profiles").json()["active"] == pid


def test_activate_unknown_404(temp_db_path, monkeypatch):
    from app.storage.settings_store import SettingsStore
    store = SettingsStore()
    ctrl = FakeController(running=False)
    c = _client(ctrl, monkeypatch, store)
    assert c.post("/api/profiles/nope/activate").status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_profiles_api.py -v`
Expected: FAIL (`app.api.profiles_api` does not exist).

- [ ] **Step 3: Implement**

```python
# app/api/profiles_api.py
"""Broker-profile CRUD + activate routes. Activate restarts the engine if running."""
from fastapi import Body, FastAPI, HTTPException

from app.storage import profiles
from app.engine_controller import EngineController


def add_profile_routes(app: FastAPI, controller: EngineController) -> None:
    @app.get("/api/profiles")
    def get_profiles():
        return profiles.list_profiles()

    @app.post("/api/profiles")
    def create(payload: dict = Body(...)):
        return profiles.create_profile(payload)

    @app.put("/api/profiles/{pid}")
    def update(pid: str, payload: dict = Body(...)):
        try:
            return profiles.update_profile(pid, payload)
        except KeyError:
            raise HTTPException(status_code=404, detail="Profile not found")

    @app.delete("/api/profiles/{pid}")
    def delete(pid: str):
        profiles.delete_profile(pid)
        return {"ok": True}

    @app.post("/api/profiles/{pid}/activate")
    async def activate(pid: str):
        try:
            profiles.activate_profile(pid)
        except KeyError:
            raise HTTPException(status_code=404, detail="Profile not found")
        if controller.status().to_dict()["engine"] == "running":
            await controller.restart()
        return {"ok": True, "status": controller.status().to_dict()}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_profiles_api.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/api/profiles_api.py tests/unit/test_profiles_api.py
git commit -m "feat(profiles): CRUD + activate API (restart engine on activate when running)"
```

---

## Task 4: Wire routes + auto-create Default profile on wizard completion

**Files:**
- Modify: `app/api/server.py`
- Modify: `app/api/wizard.py`
- Test: `tests/unit/test_wizard_default_profile.py`

- [ ] **Step 1: Wire the routes**

In `app/api/server.py`, add the import near the others:
```python
from app.api.profiles_api import add_profile_routes
```
And after the `add_mt5_routes(app, pick_file=pick_file)` line (from Plan 7a), add:
```python
    add_profile_routes(app, controller)
```

- [ ] **Step 2: Write the failing test for the wizard auto-create**

```python
# tests/unit/test_wizard_default_profile.py
import app.wizard.state as state
import app.storage.profiles as profiles


def test_complete_creates_default_profile_when_none(temp_db_path):
    from app.storage.settings_store import SettingsStore
    s = SettingsStore()
    # Seed live settings as if the wizard filled them in:
    s.set("mt5.account", "111"); s.set("mt5.server", "Srv")
    s.set("mt5.terminal_path", "C:/t.exe"); s.set("symbols.default_suffix", ".r")

    state.complete_onboarding()  # the new helper called by the API route

    out = profiles.list_profiles(store=s)
    assert len(out["profiles"]) == 1
    assert out["profiles"][0]["name"] == "Default"
    assert out["active"] == out["profiles"][0]["id"]


def test_complete_does_not_duplicate_default(temp_db_path):
    from app.storage.settings_store import SettingsStore
    s = SettingsStore()
    profiles.create_profile({"name": "Existing", "mt5": {}, "symbols": {}}, store=s)
    state.complete_onboarding()
    assert len(profiles.list_profiles(store=s)["profiles"]) == 1  # no Default added
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_wizard_default_profile.py -v`
Expected: FAIL (`state.complete_onboarding` not defined).

- [ ] **Step 4: Implement the helper + call it from the API**

In `app/wizard/state.py`, add (it already imports `SettingsStore`):
```python
def complete_onboarding(store: Optional[SettingsStore] = None) -> None:
    """Mark onboarding complete and seed a 'Default' broker profile if none exist."""
    from app.config_accessors import get_mt5_config, get_symbol_settings
    from app.storage import profiles
    s = store or SettingsStore()
    set_onboarding_complete(True, store=s)
    if profiles.list_profiles(store=s)["profiles"]:
        return
    cfg = get_mt5_config()
    suffix, mapping = get_symbol_settings()
    created = profiles.create_profile({
        "name": "Default",
        "mt5": {"terminal_path": cfg.get("terminal_path") or "",
                "account": cfg.get("account") or "",
                "server": cfg.get("server") or "",
                "password": cfg.get("password") or ""},
        "symbols": {"default_suffix": suffix or "", "map": mapping or {}},
    }, store=s)
    profiles.activate_profile(created["id"], store=s)
```
Then in `app/api/wizard.py`, change the `wizard_complete` route to call it:
```python
    @app.post("/api/wizard/complete")
    def wizard_complete():
        state.complete_onboarding()
        return {"ok": True}
```

- [ ] **Step 5: Run tests + commit**

Run: `pytest tests/unit/test_wizard_default_profile.py tests/unit -q` (expect all pass).
```bash
git add app/api/server.py app/api/wizard.py app/wizard/state.py tests/unit/test_wizard_default_profile.py
git commit -m "feat(profiles): wire routes + auto-create Default profile on onboarding complete"
```

---

## Task 5: Profiles UI in the Settings tab

**Files:**
- Modify: `app/ui/index.html` (Settings tab)
- Modify: `app/ui/app.js`

- [ ] **Step 1: Add the profiles section markup**

In `app/ui/index.html`, at the top of the Settings tab content (above the existing MT5 fields), add:
```html
          <div class="lab">Broker profiles</div>
          <ul id="profiles-list" class="profiles"></ul>
          <button id="profile-add" type="button" class="btn">Save current settings as a profile…</button>
          <div id="profile-form" class="hidden">
            <label class="field">Profile name <input id="profile-name" type="text" /></label>
            <div id="profile-form-banner" class="lab"></div>
            <button id="profile-save" type="button" class="btn start">Save profile</button>
            <button id="profile-cancel" type="button" class="btn">Cancel</button>
          </div>
          <div id="profiles-banner" class="banner hidden"></div>
```

- [ ] **Step 2: Add the JS to render + operate profiles**

In `app/ui/app.js`, add:
```javascript
// --- Broker profiles (Settings tab) ---
async function loadProfiles() {
  let data = { profiles: [], active: '' };
  try { data = await (await fetch('/api/profiles')).json(); } catch (e) {}
  const ul = $('profiles-list');
  ul.innerHTML = '';
  for (const p of data.profiles) {
    const li = document.createElement('li');
    const active = p.id === data.active;
    li.innerHTML = `<span>${p.name}${active ? ' <em>(active)</em>' : ''}</span>`;
    const act = document.createElement('button');
    act.className = 'btn'; act.textContent = active ? 'Active' : 'Activate';
    act.disabled = active;
    act.addEventListener('click', () => activateProfile(p.id));
    const del = document.createElement('button');
    del.className = 'btn'; del.textContent = 'Delete';
    del.addEventListener('click', () => deleteProfile(p.id, p.name));
    li.appendChild(act); li.appendChild(del);
    ul.appendChild(li);
  }
}

async function activateProfile(id) {
  const banner = $('profiles-banner');
  banner.className = 'banner ok'; banner.textContent = 'Activating…';
  try {
    await fetch(`/api/profiles/${id}/activate`, { method: 'POST' });
    banner.textContent = 'Profile activated.';
    loadSettings(); loadProfiles(); refreshStatus();
  } catch (e) { banner.className = 'banner'; banner.textContent = 'Activation failed'; }
}

async function deleteProfile(id, name) {
  const banner = $('profiles-banner');
  if (!confirm(`Delete profile "${name}"?`)) return;
  await fetch(`/api/profiles/${id}`, { method: 'DELETE' });
  banner.className = 'banner ok'; banner.textContent = 'Profile deleted.';
  loadProfiles();
}

$('profile-add').addEventListener('click', () => {
  $('profile-form').classList.remove('hidden');
  $('profile-name').value = '';
});
$('profile-cancel').addEventListener('click', () => $('profile-form').classList.add('hidden'));
$('profile-save').addEventListener('click', async () => {
  // Save the CURRENT Settings-form values as a new profile.
  const body = {
    name: $('profile-name').value.trim() || 'Profile',
    mt5: {
      terminal_path: $('set-terminal').value.trim(),
      account: $('set-account').value.trim(),
      server: $('set-server').value.trim(),
    },
    symbols: { default_suffix: $('sym-suffix') ? $('sym-suffix').value.trim() : '' },
  };
  const pw = $('set-password').value;
  if (pw) body.mt5.password = pw;
  const r = await fetch('/api/profiles', { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const banner = $('profile-form-banner');
  if (r.ok) { $('profile-form').classList.add('hidden'); loadProfiles(); }
  else { banner.textContent = 'Could not save profile'; }
});
```

- [ ] **Step 3: Load profiles when the Settings tab opens**

Find where `loadSettings()` is called when the Settings tab is shown in `app/ui/app.js` (the tab/nav switch handler) and add a `loadProfiles();` call alongside it. If `loadSettings()` is the single entry point for showing Settings, add `loadProfiles();` at the end of `loadSettings()`.

- [ ] **Step 4: Manual verification (needs the desktop app)**

Run: `venv\Scripts\python -m app.desktop`
- Settings tab shows "Broker profiles" (after first run it has a "Default (active)" entry from the wizard tie-in, if you onboarded fresh; otherwise empty).
- "Save current settings as a profile…" creates a profile from the current fields (use the 7a terminal picker to set the terminal).
- Create a second profile (different broker), click **Activate** → the engine restarts and the Settings fields update to that profile.
Quit from the tray.

- [ ] **Step 5: Commit**

```bash
git add app/ui/index.html app/ui/app.js
git commit -m "feat(profiles): Broker profiles section in Settings (list/add/activate/delete)"
```

---

## Task 6: Acceptance (manual)

- [ ] **Step 1:** With two profiles for two different brokers, activate each in turn and confirm: the engine restarts, MT5 connects to the right terminal, and a test trade copies on the active broker.
- [ ] **Step 2:** Restart the app; confirm the active profile persists and the Settings fields reflect it.
- [ ] **Step 3:** Delete a non-active profile; confirm it disappears and its stored password secret is gone (`profiles.<id>.password` absent).
- [ ] **Step 4:** Record results in the PR description.

---

## Self-Review notes (addressed)

- **Spec coverage (7b):** data model + secret password (T2), CRUD + activate copying into live keys (T2), `SettingsStore.delete` (T1), API incl. activate-restart (T3), route wiring (T4), wizard Default tie-in (T4), Settings UI (T5), acceptance (T6). All 7b spec items covered.
- **Engine untouched:** activate only writes the existing live keys; `mt5_service`/engine are not modified — consistent with the spec's "no engine changes" decision.
- **Type consistency:** profile shape `{id,name,mt5:{terminal_path,account,server},symbols:{default_suffix,map}}` + secret `profiles.<id>.password` + `profiles.active` used identically across module, API, wizard tie-in, and UI. `list_profiles()` returns `{profiles:[...with password_set...], active}`.
- **DB isolation in tests:** all DB-touching tests use the existing `temp_db_path` fixture from `tests/conftest.py` (which sets `TV2MT5_DB_PATH` and resets `_engine`/`_SessionFactory`) — no hand-rolled global resets.
- **No placeholders:** every code step is complete; run steps state expected output.
